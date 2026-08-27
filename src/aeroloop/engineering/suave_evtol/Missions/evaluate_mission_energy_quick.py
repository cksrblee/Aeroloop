# =========================== QUICK MISSION ENERGY (MODULAR) ===========================
# 입력: Excel_Reader(mission_input_new.xlsx 전용)에서 읽은 mission_profile
#  - altitude_*_ft, air_speed_*_knots, distance_miles, climb/descent_rate_fpm, duration_s, angle_deg
# 출력: SUAVE.Core.Data results (segments[i].conditions.frames.inertial.time, ...battery_power_draw)

import math as _math
import numpy as _np
from SUAVE.Core import Data as _Data

# ────────────────────────────────────────────────────────────────────────────
# HELPERS  (단위/공통 유틸/참조값/지속시간)
# ────────────────────────────────────────────────────────────────────────────

# 단위 상수
_FT    = 0.3048
_KTS   = 0.5144444444444444
_MILE  = 1609.344
_FPM   = 0.00508
_DEG2R = _math.pi/180.0
_g0    = 9.80665

def _f(x, default=_np.nan):
    """float 캐스팅 + NaN 안전 처리"""
    try:
        v = float(x)
        return v if _np.isfinite(v) else default
    except Exception:
        return default

def _rho_at(h_m):
    """간단 ISA(대략)"""
    rho0, T0, L, R, g0 = 1.225, 288.15, -0.0065, 287.058, 9.80665
    h = max(float(h_m), 0.0)
    if h < 11000.0:
        T = T0 + L*h
        return max(0.2, rho0*(T/T0)**(g0/(R*L)-1.0))
    return 0.3

def _get_ref_area(vehicle):
    """윙 reference area S 추출(없으면 보수 최소값)"""
    S = float(getattr(vehicle, 'reference_area', 0.0))
  
    return S

def _get_total_lift_disk_area(params, vehicle):
    """총 리프트 디스크 면적 A_tot (없으면 DL 기반 추정)"""
    DL = float(getattr(params, 'diskloading', 0.0))  # [kg/m^2]
    MTOW_kg = float(getattr(vehicle.mass_properties, 'max_takeoff', 0.0))
    A = MTOW_kg / DL

    return A

def _collect_globals(params, vehicle, requirements):
    """자주 쓰는 전역 파라미터 묶기(3.6 호환: Data 사용)"""
    G = _Data()

    # 공기역학/형상
    G.S   = _get_ref_area(vehicle)
    G.AR  = float(getattr(params, 'aspect_ratio', 10.0))
    G.e   = float(getattr(params, 'oswald_e', 0.70))
    # 공기역학/형상
    G.S   = _get_ref_area(vehicle)
    G.AR  = float(getattr(params, 'aspect_ratio', 10.0))
    G.e   = float(getattr(params, 'oswald_e', 0.70))

    # --- CD0 참조 조건(사용자가 지정) ---
    Vref_mps = float(getattr(params,'CD0_ref_speed_mps',  float(getattr(params,'V_cruise_mps',50.0))))
    Href_m   = float(getattr(params,'CD0_ref_altitude_m', float(getattr(requirements,'design_altitude',0.0))))
    G.CD0    = _estimate_CD0_quick(vehicle, params, Vref_mps, Href_m)

    G.CLmax_clean  = max(float(getattr(params, 'CLmax_clean', 1.4)), 0.3)
    G.stall_margin = float(getattr(params, 'stall_margin', 0.80))

    # 항력 가산/전환 페널티
    G.delta_CD0_rotors = float(getattr(params, 'delta_CD0_rotors', 0.001))
    G.delta_CD0_gear   = float(getattr(params, 'delta_CD0_gear',   0.001))
    G.conversion_CD0_factor = float(getattr(params, 'conversion_CD0_factor', 1.05))

    # 추진 효율
    eta_prop_aero = max(float(getattr(params,'prop_eta_guess',0.82)), 1e-3)
    eta_prop_elec = max(float(getattr(params,'prop_motor_efficiency',0.90)) *
                        float(getattr(params,'prop_esc_efficiency', 0.95)), 1e-3)
    G.eta_prop_total = min(0.85, eta_prop_aero * eta_prop_elec)

    # 호버 효율/프로파일
    FM_hover       = max(float(getattr(params,'lift_rotor_FM',0.68)), 1e-3)
    eta_hover_elec = max(float(getattr(params,'lift_motor_efficiency',0.90)) *
                         float(getattr(params,'lift_esc_efficiency', 0.95)), 1e-3)
    G.eta_hover_total = min(0.98, FM_hover * eta_hover_elec)
    G.beta_hover      = float(getattr(params,'beta_hover', 0.20))

    # 전진 하강 아이들/재생
    G.P_idle_prop_W      = float(getattr(params, 'prop_idle_power_W', 0.0))
    G.P_idle_prop_W_desc = float(getattr(params, 'P_idle_prop_W_desc', 5000.0))
    G.allow_regen        = bool(getattr(params,'allow_regen', False))
    G.eta_regen          = float(getattr(params,'regen_efficiency', 0.60))
    G.k_vdes             = float(getattr(params, 'vertical_descent_power_ratio', 1.8)) # 수직하강시 에너지 소모 가산

    # 호텔 부하
    P_hotel = float(getattr(requirements, 'avionics_power_W', 0.0)) + \
              float(getattr(requirements, 'payload_power_W',  0.0))

    G.P_hotel = max(P_hotel, 100.0)  # 안전 하한

    # 중량/디스크
    G.MTOW_kg = max(float(getattr(vehicle.mass_properties,'max_takeoff',0.0)), 1e-6)
    G.W_N     = G.MTOW_kg * _g0
    G.A_tot   = _get_total_lift_disk_area(params, vehicle)

    # 기본 전진속도 (fallback)
    G.V_cruise_mps_default = float(getattr(params,'V_cruise_mps', 50.0))
    
    # 천이 관련 파라미터
    G.drag_mult_start   = float(getattr(params,'transition_drag_mult_start', 1.05))
    G.drag_mult_end     = float(getattr(params,'transition_drag_mult_end',   1.00))
    G.rot_lift_start    = float(getattr(params,'transition_rotor_lift_frac_start', 1.00))
    G.rot_lift_end      = float(getattr(params,'transition_rotor_lift_frac_end',   0.00))
    G.extra_lift_gain   = float(getattr(params,'transition_extra_lift_gain', 0.0))
    
    # wing climb/descent 보정 (캘리브레이션용)
    G.forward_climb_cd0_mult        = float(getattr(params,'forward_climb_cd0_mult',       1.25))
    G.forward_desc_cd0_mult         = float(getattr(params,'forward_desc_cd0_mult',        1.05))
    G.forward_climb_delta_cd0_rotors= float(getattr(params,'forward_climb_delta_cd0_rotors',0.005))
    G.forward_desc_delta_cd0_rotors = float(getattr(params,'forward_desc_delta_cd0_rotors', 0.0))
    G.forward_climb_delta_cd0_gear  = float(getattr(params,'forward_climb_delta_cd0_gear',  0.0))
    G.forward_desc_delta_cd0_gear   = float(getattr(params,'forward_desc_delta_cd0_gear',   0.0))
    G.forward_climb_eta_prop_scale  = float(getattr(params,'forward_climb_eta_prop_scale',  0.90))
    G.forward_desc_eta_prop_scale   = float(getattr(params,'forward_desc_eta_prop_scale',   1.00))
    G.forward_climb_trim_power_frac = float(getattr(params,'forward_climb_trim_power_frac', 0.10))
    G.forward_desc_trim_power_frac  = float(getattr(params,'forward_desc_trim_power_frac',  0.00))


    return G




def _estimate_CD0_quick(vehicle, params, V_mps, h_m):
    """
    기존 방식 유지 + 리프트 로터/외부 돌출물에 근거한 추가 CD0 예측 추가

    params에서 사용 가능한 추가 필드(옵션):
      - params.k_rotor_coeff (float): 로터 스케일 계수 k_r (default 3.0)
      - params.rotor_exponent (float): 로터 수 지수 p_r (default 1.5)
      - params.k_protrusion_coeff (float): 돌출물 계수 k_p (default 20.0)
      - params.protrusion_area_scale_A0 (float): A0 (m2) 기준값 (default 1.0)
      - params.use_wetted_protrusion (bool): 돌출물에 젖은면적 사용할지 여부 (default False)
      - params.return_breakdown (bool): 계산 분해 결과를 vehicle._last_cd0_breakdown에 저장
      - params.num_lift_props, params.prop_diameter, params.lift_rotor_area: 로터 관련 대체 입력
      - params.protrusion_area: 외부 돌출물 총 전면 또는 젖은면적 대체 입력
    """
    import math as _m

    # --- 대기 물성 (간단 ISA) ---
    rho0, T0, L, R, g0 = 1.225, 288.15, -0.0065, 287.058, 9.80665
    h   = max(float(h_m), 0.0)
    if h < 11000.0:
        T = T0 + L*h
        rho = max(0.2, rho0*(T/T0)**(g0/(R*L)-1.0))
        a   = (1.4*R*T)**0.5
        mu  = 1.7894e-5 * (T/288.15)**1.5 * (288.15+110.4)/(T+110.4)
    else:
        T = 216.65
        rho = 0.3
        a   = (1.4*R*T)**0.5
        mu  = 1.46e-5

    V   = max(float(V_mps), 1e-3)
    Sref = float(getattr(vehicle, 'reference_area', 0.0)) or 1.0

    # --- 젖은면적 합 (날개 + 동체 + tails 기존 동작) ---
    Swet = 0.0
    for w in getattr(vehicle, 'wings', []):
        Swet += float(getattr(getattr(w,'areas',object()), 'wetted', 0.0))
    # fuselage
    try:
        Swet += float(vehicle.fuselages['fuselage'].areas.wetted)
    except Exception:
        Swet += float(getattr(getattr(vehicle, 'fuselage', object()), 'areas', object()).wetted or 0.0)
    Swet = max(Swet, 1e-6)

    # --- 특성 길이/레이놀즈/마하 ---
    try:
        L_char = float(getattr(getattr(vehicle, 'wings', {}).get('main_wing', object()), 'chords').MAC)
    except Exception:
        L_char = 1.0
    Re = max(rho*V*L_char/max(mu,1e-9), 1e3)
    M  = V/max(a,1e-9)

    # Cf (turbulent compressible correction)
    Cf = 0.455 / (_m.log10(Re)**2.58) / ((1.0 + 0.144*M*M)**0.65)

    # 기본 형상/간섭 계수 (간이)
    FF = 1.0
    Q  = 1.0

    # CD0 core
    CD0_core = Cf * FF * Q * (Swet / Sref)

    # --- 공통: 3D base-drag 계수 (논문 유사식) ---
    CDB = 0.029 * _m.sqrt(max(Cf, 1e-12))

    # -------------------------
    # 1) 리프트 로터 관련 입력 추출
    # -------------------------
    # 우선 vehicle 내부 정보 시도
    takeoff_mass  = getattr(getattr(vehicle, 'mass_properties', None), 'max_takeoff', None)
    N_rot = params.number_of_rotors
    A_rot_tot = (takeoff_mass / params.diskloading)


    # -------------------------
    # 2) 외부 돌출물(파일런, 프로브 등) 면적 추출
    # -------------------------
    A_prot = params.excrescence_area_fac * Sref


    # -------------------------
    # 3) 경험식에 의한 추가 CD0 계산
    # -------------------------
    # 튜닝 파라미터 (params에서 덮어쓰기 가능)
    k_r = float(getattr(params, 'k_rotor_coeff', 0.62))             # 로터 수 계수
    p_r = float(getattr(params, 'rotor_exponent', 1.0))             # 로터 수 지수
    k_p = float(getattr(params, 'k_protrusion_coeff', 37.0))        # 돌출물 계수
    A0  = float(getattr(params, 'protrusion_area_scale_A0', 1.0))

    # 로터 스케일 (기하/간섭/허브/가드 등 복합효과를 근사)
    rotor_scale = 1.0 + k_r * (N_rot**p_r) if N_rot>0 else 1.0
    CD0_rotors = CDB * (A_rot_tot / Sref) * rotor_scale

    # 돌출물 스케일 (면적에 비례하는 추가 효과)
    prot_scale = 1.0 + k_p * (A_prot / max(A0, 1e-6))
    CD0_protrusions = CDB * (A_prot / Sref) * prot_scale

    # 최종
    CD0_total = float(CD0_core + CD0_rotors + CD0_protrusions)

    return CD0_total




def _duration_hover(dh, ROC, dur_in, default_hover=30.0):
    if _np.isfinite(dh) and _np.isfinite(ROC) and abs(ROC) > 1e-6 and abs(dh) > 0:
        return abs(dh)/abs(ROC)
    if _np.isfinite(dur_in) and dur_in > 0:
        return dur_in
    return default_hover

def _duration_forward(dh, ROC, dist_m, V, dur_in, default_fwd=60.0):
    if _np.isfinite(dh) and _np.isfinite(ROC) and abs(ROC) > 1e-6 and abs(dh) > 0:
        return abs(dh)/abs(ROC)
    if _np.isfinite(dist_m) and _np.isfinite(V) and dist_m > 0 and V > 0:
        return dist_m/V
    if _np.isfinite(dur_in) and dur_in > 0:
        return dur_in
    return default_fwd

def _duration_cruise(dist_m, V, dur_in, default_fwd=60.0):
    if _np.isfinite(dist_m) and _np.isfinite(V) and dist_m > 0 and V > 0:
        return dist_m/V
    if _np.isfinite(dur_in) and dur_in > 0:
        return dur_in
    return default_fwd

def _pack_segment(tag, dur, P):
    """SUAVE Data 포맷으로 한 세그먼트 결과 포장"""
    out = _Data(); out.tag = tag
    out.conditions = _Data()
    out.conditions.frames = _Data(); out.conditions.frames.inertial = _Data()
    out.conditions.frames.inertial.time = _np.array([0.0, dur], dtype=float)
    out.conditions.propulsion = _Data()
    out.conditions.propulsion.battery_power_draw = _np.array([P, P], dtype=float)
    return out, dur * P  # [J]

# ────────────────────────────────────────────────────────────────────────────
# MODELS  (항력 블록, 호버 전력 등)
# ────────────────────────────────────────────────────────────────────────────

def _drag_block(W, V_cmd, rho, S, AR, e, CD0, CLmax_clean, stall_margin,
                cd0_extra=0.0, cd0_mult=1.0):
    """
    항력/스톨-가드 블록
      - 속도는 스톨여유(stall_margin*CLmax)로부터 Vmin 보정
      - CD0 -> (CD0 + cd0_extra) * cd0_mult
    """
    CL_allow = stall_margin * CLmax_clean
    Vmin = _np.sqrt(W / max(1e-9, 0.5*rho*S*CL_allow))
    V = max(float(V_cmd), Vmin, 1e-3)
    q = 0.5*rho*V*V
    CL = W/(q*S)
    CDi = CL*CL/(_np.pi*AR*e)
    CD0_eff = (CD0 + cd0_extra) * cd0_mult
    CD = CD0_eff + CDi
    D  = q*S*CD
    return D, V, CL, CD, CD0_eff, Vmin

def _hover_power(W, rho, A_tot, ROC, beta_hover, eta_hover_total):
    """호버 전력(모멘텀 + 프로파일 근사)"""
    vi   = _np.sqrt(max(W,1e-3) / (2.0*rho*max(A_tot,1e-6)))
    Pind = W*vi + W*max(0.0, ROC)   # 상승률 항은 상승시에만 가산
    return (1.0 + beta_hover) * Pind / max(1e-3, eta_hover_total)

# ────────────────────────────────────────────────────────────────────────────
# SEGMENT ENERGY  (타입별 계산 함수)
# ────────────────────────────────────────────────────────────────────────────

def seg_energy_hover(row, G, prev_alt_m):
    """
    Hover.Hover / Hover.Climb / Hover.Descent
    입력 row: altitude_*_ft, climb/descent_rate_fpm, duration_s ...
    """
    tag = str(getattr(row,'tag','hover') or "")
    # 고도
    h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
    h1_m = _f(getattr(row,'altitude_end_ft',None), h0_m/_FT) * _FT
    dh   = h1_m - h0_m
    rho  = _rho_at(0.5*(h0_m+h1_m))

    # 상승/하강률
    ROCc = _f(getattr(row,'climb_rate_fpm',None),   _np.nan) * _FPM
    ROCd = _f(getattr(row,'descent_rate_fpm',None), _np.nan) * _FPM
    ROC  = 0.0
    cls  = (row.segment_class or "")
    if 'Climb' in cls and _np.isfinite(ROCc):   ROC =  abs(ROCc)
    if 'Descent' in cls and _np.isfinite(ROCd): ROC = -abs(ROCd)

    # 지속시간
    dur = _duration_hover(dh, ROC, _f(getattr(row,'duration_s',None), _np.nan), default_hover=30.0)

    # 전력
    if ROC < 0.0:  # 수직 하강 페널티
        P = G.k_vdes * _hover_power(G.W_N, rho, G.A_tot, 0.0, G.beta_hover, G.eta_hover_total) + G.P_hotel
    else:
        P = _hover_power(G.W_N, rho, G.A_tot, ROC, G.beta_hover, G.eta_hover_total) + G.P_hotel

    out, E = _pack_segment(tag, dur, P)

    

    return out, E, h1_m

def seg_energy_cruise_loiter(row, G, prev_alt_m):
    """
    Cruise.Constant_Speed_Constant_Altitude
    Cruise.Constant_Speed_Constant_Altitude_Loiter
    """
    tag = str(getattr(row,'tag','cruise') or "")
    # 고도/밀도
    h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
    h1_m = _f(getattr(row,'altitude_end_ft',None), h0_m/_FT) * _FT
    rho  = _rho_at(0.5*(h0_m+h1_m))

    # 속도
    V0 = _f(getattr(row,'air_speed_start_knots',None), _np.nan) * _KTS
    V1 = _f(getattr(row,'air_speed_end_knots',None),   _np.nan) * _KTS
    V_fixed = _f(getattr(row,'air_speed_knots',None),  _np.nan) * _KTS
    if _np.isfinite(V_fixed):
        V_cmd = V_fixed
    elif _np.isfinite(V0) and _np.isfinite(V1):
        V_cmd = 0.5*(V0+V1)
    else:
        V_cmd = V0 if _np.isfinite(V0) else (V1 if _np.isfinite(V1) else G.V_cruise_mps_default)

    # 거리/시간
    dist_m = _f(getattr(row,'distance_miles',None), _np.nan) * _MILE
    dur_in = _f(getattr(row,'duration_s',None), _np.nan)

    # 항력/전력
    cd0_extra = 0
    D, V, *_  = _drag_block(G.W_N, V_cmd, rho, G.S, G.AR, G.e, G.CD0, G.CLmax_clean, G.stall_margin,
                            cd0_extra=cd0_extra, cd0_mult=1.0)
    P = (D*V)/max(1e-3, G.eta_prop_total) + G.P_hotel

    dur = _duration_cruise(dist_m, V, dur_in, default_fwd=60.0)
    out, E = _pack_segment(tag, dur, P)
    return out, E, h1_m


def seg_energy_forward_rate(row, G, prev_alt_m):
    """
    Climb/Descent ... Constant_Rate (전진)
    - 크루즈 항력 + 등률 항 + 부족양력 보전 + (옵션) 아이들/트림/효율 보정
    - 본 블록은 '전진 등률' 구간(wing_climb / wing_descent)에 대한 보수적 보정 손잡이 포함
      * params에서 전달된 전용 가중치로 CD0/추가드래그/추진효율/트림손실을 조절
        - forward_climb_cd0_mult / forward_desc_cd0_mult
        - forward_climb_delta_cd0_rotors / forward_desc_delta_cd0_rotors
        - forward_climb_delta_cd0_gear   / forward_desc_delta_cd0_gear
        - forward_climb_eta_prop_scale   / forward_desc_eta_prop_scale
        - forward_climb_trim_power_frac  / forward_desc_trim_power_frac
    """
    tag = str(getattr(row,'tag','forward') or "")

    # ── 고도/밀도
    h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
    h1_m = _f(getattr(row,'altitude_end_ft',None), h0_m/_FT) * _FT
    dh   = h1_m - h0_m
    rho  = _rho_at(0.5*(h0_m+h1_m))

    # ── 속도(평균값 사용)
    V0 = _f(getattr(row,'air_speed_start_knots',None), _np.nan) * _KTS
    V1 = _f(getattr(row,'air_speed_end_knots',None),   _np.nan) * _KTS
    if _np.isfinite(V0) and _np.isfinite(V1):
        V_cmd = 0.5*(V0+V1)
    else:
        V_cmd = V0 if _np.isfinite(V0) else (V1 if _np.isfinite(V1) else G.V_cruise_mps_default)

    # ── 등률(상승/하강 판정)
    ROCc = _f(getattr(row,'climb_rate_fpm',None),   _np.nan) * _FPM
    ROCd = _f(getattr(row,'descent_rate_fpm',None), _np.nan) * _FPM
    ROC  = 0.0
    cls  = (row.segment_class or "")
    if 'Climb' in cls and _np.isfinite(ROCc):   ROC =  abs(ROCc)
    if 'Descent' in cls and _np.isfinite(ROCd): ROC = -abs(ROCd)

    is_climb   = (ROC >  1e-9)
    is_descent = (ROC < -1e-9)

    # ── 항력 보정 손잡이 설정
    base_extra = G.delta_CD0_rotors + G.delta_CD0_gear
    if is_climb:
        cd0_extra = base_extra + G.forward_climb_delta_cd0_rotors + G.forward_climb_delta_cd0_gear
        cd0_mult  = G.forward_climb_cd0_mult
        eta_scale = G.forward_climb_eta_prop_scale
        trim_frac = G.forward_climb_trim_power_frac
    elif is_descent:
        cd0_extra = base_extra + G.forward_desc_delta_cd0_rotors + G.forward_desc_delta_cd0_gear
        cd0_mult  = G.forward_desc_cd0_mult
        eta_scale = G.forward_desc_eta_prop_scale
        trim_frac = G.forward_desc_trim_power_frac
    else:
        cd0_extra = base_extra
        cd0_mult  = 1.0
        eta_scale = 1.0
        trim_frac = 0.0

    # ── 항력/속도(스톨 가드 포함)
    D, V, *_  = _drag_block(G.W_N, V_cmd, rho, G.S, G.AR, G.e, G.CD0, G.CLmax_clean, G.stall_margin,
                            cd0_extra=cd0_extra, cd0_mult=cd0_mult)

    # ── 부족양력 보전(로터 유사 전력)
    CL_allow = G.stall_margin * G.CLmax_clean
    L_avail  = 0.5*rho*V*V*G.S*CL_allow
    L_def    = max(0.0, G.W_N - L_avail)
    P_add    = 0.0
    if L_def > 0.0:
        vi_def = _np.sqrt(L_def / max(2.0*rho*G.A_tot, 1e-6))
        P_add  = (L_def * vi_def)/max(1e-3, G.eta_hover_total)

    # ── 추진 전력 (효율 보정 + 트림 손실)
    T_req   = D + (G.W_N*ROC/max(1e-6, V))
    eta_eff = max(1e-3, G.eta_prop_total * eta_scale)
    P_prop  = (max(0.0, T_req) * V) / eta_eff
    P_trim  = trim_frac * P_prop

    # ── 디센트 아이들 손실(하강에서만 추가)
    P_idle = G.P_idle_prop_W + (G.P_idle_prop_W_desc if is_descent else 0.0)

    # ── 총 전력
    P = P_idle + P_prop + P_trim + P_add + G.P_hotel

    # ── 지속시간 산정
    dist_m = _f(getattr(row,'distance_miles',None), _np.nan) * _MILE
    dur_in = _f(getattr(row,'duration_s',None), _np.nan)
    dur    = _duration_forward(dh, ROC, dist_m, V, dur_in, default_fwd=60.0)

    # ── 결과 패키징
    out, E = _pack_segment(tag, dur, P)
    return out, E, h1_m




def seg_energy_transition(row, G, prev_alt_m):
    """
    Transition.Constant_Acceleration_Constant_Angle_Linear_Climb (re-transition 포함)
    - 속도: V0 -> V1 선형 변화(가속), 시간 등분 적분으로 에너지 산출
    - 드래그: 전환 페널티 반영 (ΔCD0 + 배율)
    - 부족양력: 각 속도점에서 보전(hover 효율), 10% 가산
    - 추진: 프로펠러 전력 + (보전 전력) + 호텔부하
    """
    tag = str(getattr(row,'tag','transition') or "")

    # -------- 고도/밀도 --------
    h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
    h1_m = _f(getattr(row,'altitude_end_ft',None),   h0_m/_FT) * _FT
    dh   = h1_m - h0_m
    rho  = _rho_at(0.5*(h0_m+h1_m))

    # -------- 속도 (knots -> m/s) --------
    V0 = _f(getattr(row,'air_speed_start_knots',None), _np.nan) * _KTS
    V1 = _f(getattr(row,'air_speed_end_knots',None),   _np.nan) * _KTS
    V_fixed = _f(getattr(row,'air_speed_knots',None), _np.nan) * _KTS

    # V 명세가 없을 때의 fallback
    if _np.isfinite(V_fixed):
        V0 = V1 = V_fixed
    else:
        if not _np.isfinite(V0) and _np.isfinite(V1):
            V0 = V1
        if _np.isfinite(V0) and not _np.isfinite(V1):
            V1 = V0
        if not _np.isfinite(V0) and not _np.isfinite(V1):
            V0 = V1 = G.V_cruise_mps_default

    # -------- 등률 --------
    ROCc = _f(getattr(row,'climb_rate_fpm',None),   _np.nan) * _FPM
    ROCd = _f(getattr(row,'descent_rate_fpm',None), _np.nan) * _FPM
    ROC  = 0.0
    if _np.isfinite(ROCc): ROC =  abs(ROCc)
    if _np.isfinite(ROCd): ROC = -abs(ROCd)

    # -------- 거리/시간 --------
    dist_m = _f(getattr(row,'distance_miles',None), _np.nan) * _MILE
    dur_in = _f(getattr(row,'duration_s',None), _np.nan)

    # 평균속도(선형 가속 가정)로 일단 전체 지속시간 산정
    V_avg_for_dur = 0.5*(V0+V1)
    dur = _duration_forward(dh, ROC, dist_m, V_avg_for_dur, dur_in, default_fwd=30.0)
    dur = max(dur, 1e-3)

    # -------- 전환 페널티 파라미터 --------
    cd0_extra = G.delta_CD0_rotors + G.delta_CD0_gear
    cd0_mult  = G.conversion_CD0_factor

    # -------- 속도 구간 적분 (시간 등분, V 선형 변화) --------
    N = int(getattr(G, 'transition_integration_steps', getattr(G, 'N_transition_steps', 20)) or 20)
    N = max(5, min(N, 200))
    dt = dur / N

    E_sum = 0.0
    P_peak = 0.0

    for k in range(N):
        tau = (k + 0.5) / N
        V   = max(V0 + (V1 - V0) * tau, 1e-3)

        # --- 전환 램프: 드래그 배율/부족양력 보전비율 ---
        drag_mult_eff = G.drag_mult_start + (G.drag_mult_end - G.drag_mult_start) * tau
        rotor_frac    = G.rot_lift_start  + (G.rot_lift_end  - G.rot_lift_start)  * tau
        rotor_frac    = min(max(rotor_frac, 0.0), 1.0)

        # 항력(전환 페널티: ΔCD0는 동일, 배율만 램프)
        D, V_eff, CL, CD, CD0_eff, Vmin = _drag_block(
            G.W_N, V, rho, G.S, G.AR, G.e, G.CD0, G.CLmax_clean, G.stall_margin,
            cd0_extra=cd0_extra, cd0_mult=drag_mult_eff
        )

        # 부족양력 보전 (전환 중 가용양력에 약간 이득 옵션)
        CL_allow = G.stall_margin * (G.CLmax_clean + G.extra_lift_gain)
        L_avail  = 0.5*rho*V*V*G.S*CL_allow
        L_def    = max(0.0, G.W_N - L_avail)

        P_add = 0.0
        if L_def > 0.0:
            vi_def = _np.sqrt(L_def / max(2.0*rho*G.A_tot, 1e-6))
            # ← 10% 가산 제거, 그리고 로터 보전 비율만큼만 사용
            P_add  = rotor_frac * (L_def * vi_def) / max(1e-3, G.eta_hover_total)

        # 추진 전력
        T_req  = max(0.0, D + (G.W_N*ROC / max(V,1e-6)))
        P_prop = (T_req * V) / max(1e-3, G.eta_prop_total)

        P_total = G.P_idle_prop_W + P_prop + P_add + G.P_hotel
        E_sum  += P_total * dt
        P_peak  = max(P_peak, P_total)

    # 평균 전력으로 세그먼트 패킹
    P_avg = E_sum / dur
    out = _Data(); out.tag = tag
    out.conditions = _Data()
    out.conditions.frames = _Data(); out.conditions.frames.inertial = _Data()
    out.conditions.frames.inertial.time = _np.array([0.0, dur], dtype=float)
    out.conditions.propulsion = _Data()
    out.conditions.propulsion.battery_power_draw = _np.array([P_avg, P_avg], dtype=float)

    return out, E_sum, h1_m



# ────────────────────────────────────────────────────────────────────────────
# MAIN  (기존 인터페이스 유지)
# ────────────────────────────────────────────────────────────────────────────

def evaluate_mission_energy_quick(params, vehicle, requirements, mission_profile):
    """
    수식 기반 빠른 미션 에너지 추정(모듈화 버전).
    - 엑셀: mission_input_new.xlsx 포맷(단위 유지)
    - 세그먼트 분류: Hover / Cruise·Loiter / Forward Constant-Rate(Climb/Descent) / Transition
    - 출력: 각 세그먼트의 time, battery_power_draw 포함한 SUAVE Data
    """
    G = _collect_globals(params, vehicle, requirements)

    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)
            
    results  = _Data(); results.segments = []
    seg_rows = []
    prev_alt_m = None

    for row in mission_profile.segments:
        cls = (row.segment_class or "")
        tag = str(getattr(row,'tag','seg') or "")

        # 분기
        if cls.startswith('Hover'):
            out, E, prev_alt_m = seg_energy_hover(row, G, prev_alt_m)
        elif ('Cruise' in cls and 'Constant_Speed' in cls) or ('Loiter' in cls):
            out, E, prev_alt_m = seg_energy_cruise_loiter(row, G, prev_alt_m)
        elif (('Climb' in cls) or ('Descent' in cls)) and ('Constant_Rate' in cls):
            out, E, prev_alt_m = seg_energy_forward_rate(row, G, prev_alt_m)
        elif cls.startswith('Transition.'):
            out, E, prev_alt_m = seg_energy_transition(row, G, prev_alt_m)
        else:
            # 미지원 → 건너뛰기
            prev_alt_m = _f(getattr(row,'altitude_end_ft',None), 0.0)*_FT
            continue

        # 결과 누적/로그
        results.segments.append(out)
        dur = float(out.conditions.frames.inertial.time[-1] - out.conditions.frames.inertial.time[0])
        Pk  = float(out.conditions.propulsion.battery_power_draw.max())
        seg_rows.append((tag, dur, E/1e6, Pk/1000.0))

    # 표 출력
    if seg_rows:
        _log("\n======================mission======================")
        _log(f"{'segment':<28s} | {'dur[s]':>7s} | {'energy[MJ]':>12s} | {'peak[kW]':>9s}")
        _log("-"*62)
        for tag, dur, Emj, Pk in seg_rows:
            _log(f"{tag:<28s} | {dur:7.0f} | {Emj:12.2f} | {Pk:9.2f}")
        _log("-"*62)
        total_dur = sum(r[1] for r in seg_rows)
        total_Emj = sum(r[2] for r in seg_rows)
        total_Pk  = sum(r[3] for r in seg_rows)
        _log(f"{'TOTAL':<28s} | {total_dur:7.0f} | {total_Emj:12.2f} | {total_Pk:9.2f}")
    _log()

    # 안전망: 비어있으면 1초 호텔부하 더미
    if not results.segments:
        out, _E = _pack_segment("dummy", 1.0, G.P_hotel)
        results.segments.append(out)

    return results

# ========================= /QUICK MISSION ENERGY (MODULAR) ===========================








## 수직 이착륙 파워, 크루징 에너지 정합본
# # =========================== QUICK MISSION ENERGY (MODULAR) ===========================
# # 입력: Excel_Reader(mission_input_new.xlsx 전용)에서 읽은 mission_profile
# #  - altitude_*_ft, air_speed_*_knots, distance_miles, climb/descent_rate_fpm, duration_s, angle_deg
# # 출력: SUAVE.Core.Data results (segments[i].conditions.frames.inertial.time, ...battery_power_draw)

# import math as _math
# import numpy as _np
# from SUAVE.Core import Data as _Data

# # ────────────────────────────────────────────────────────────────────────────
# # HELPERS  (단위/공통 유틸/참조값/지속시간)
# # ────────────────────────────────────────────────────────────────────────────

# # 단위 상수
# _FT    = 0.3048
# _KTS   = 0.5144444444444444
# _MILE  = 1609.344
# _FPM   = 0.00508
# _DEG2R = _math.pi/180.0
# _g0    = 9.80665

# def _f(x, default=_np.nan):
#     """float 캐스팅 + NaN 안전 처리"""
#     try:
#         v = float(x)
#         return v if _np.isfinite(v) else default
#     except Exception:
#         return default

# def _rho_at(h_m):
#     """간단 ISA(대략)"""
#     rho0, T0, L, R, g0 = 1.225, 288.15, -0.0065, 287.058, 9.80665
#     h = max(float(h_m), 0.0)
#     if h < 11000.0:
#         T = T0 + L*h
#         return max(0.2, rho0*(T/T0)**(g0/(R*L)-1.0))
#     return 0.3

# def _get_ref_area(vehicle):
#     """윙 reference area S 추출(없으면 보수 최소값)"""
#     S = float(getattr(vehicle, 'reference_area', 0.0))
  
#     return S

# def _get_total_lift_disk_area(params, vehicle):
#     """총 리프트 디스크 면적 A_tot (없으면 DL 기반 추정)"""
#     DL = float(getattr(params, 'diskloading', 0.0))  # [kg/m^2]
#     MTOW_kg = float(getattr(vehicle.mass_properties, 'max_takeoff', 0.0))
#     A = MTOW_kg / DL

#     return A

# def _collect_globals(params, vehicle, requirements):
#     """자주 쓰는 전역 파라미터 묶기(3.6 호환: Data 사용)"""
#     G = _Data()

#     # 공기역학/형상
#     G.S   = _get_ref_area(vehicle)
#     G.AR  = float(getattr(params, 'aspect_ratio', 10.0))
#     G.e   = float(getattr(params, 'oswald_e', 0.70))
#     # 공기역학/형상
#     G.S   = _get_ref_area(vehicle) * 1.08
#     G.AR  = float(getattr(params, 'aspect_ratio', 10.0))
#     G.e   = float(getattr(params, 'oswald_e', 0.70))

#     # --- CD0 참조 조건(사용자가 지정) ---
#     Vref_mps = float(getattr(params,'CD0_ref_speed_mps',  float(getattr(params,'V_cruise_mps',50.0))))
#     Href_m   = float(getattr(params,'CD0_ref_altitude_m', float(getattr(requirements,'design_altitude',0.0))))
#     G.CD0    = _estimate_CD0_quick(vehicle, params, Vref_mps, Href_m)

#     G.CLmax_clean  = max(float(getattr(params, 'CLmax_clean', 1.4)), 0.3)
#     G.stall_margin = float(getattr(params, 'stall_margin', 0.80))

#     # 항력 가산/전환 페널티
#     G.delta_CD0_rotors = float(getattr(params, 'delta_CD0_rotors', 0.001))
#     G.delta_CD0_gear   = float(getattr(params, 'delta_CD0_gear',   0.001))
#     G.conversion_CD0_factor = float(getattr(params, 'conversion_CD0_factor', 1.05))

#     # 추진 효율
#     eta_prop_aero = max(float(getattr(params,'prop_eta_guess',0.82)), 1e-3)
#     eta_prop_elec = max(float(getattr(params,'prop_motor_efficiency',0.80)) *
#                         float(getattr(params,'prop_esc_efficiency', 0.8)), 1e-3)
#     G.eta_prop_total = min(0.85, eta_prop_aero * eta_prop_elec)

#     # 호버 효율/프로파일
#     FM_hover       = max(float(getattr(params,'lift_rotor_FM',0.68)), 1e-3)
#     eta_hover_elec = max(float(getattr(params,'lift_motor_efficiency',0.90)) *
#                          float(getattr(params,'lift_esc_efficiency', 0.95)), 1e-3)
#     G.eta_hover_total = min(0.98, FM_hover * eta_hover_elec)
#     G.beta_hover      = float(getattr(params,'beta_hover', 0.20))

#     # 전진 하강 아이들/재생
#     G.P_idle_prop_W      = float(getattr(params, 'prop_idle_power_W', 0.0))
#     G.P_idle_prop_W_desc = float(getattr(params, 'P_idle_prop_W_desc', 5000.0))
#     G.allow_regen        = bool(getattr(params,'allow_regen', False))
#     G.eta_regen          = float(getattr(params,'regen_efficiency', 0.60))
#     G.k_vdes             = float(getattr(params, 'vertical_descent_power_ratio', 1.8)) # 수직하강시 에너지 소모 가산
#     G.k_climb            = float(getattr(params, 'climb_power_ratio', 2)) # 상승시 에너지 소모 가산   

#     # 호텔 부하
#     P_hotel = float(getattr(requirements, 'avionics_power_W', 0.0)) + \
#               float(getattr(requirements, 'payload_power_W',  0.0))

#     G.P_hotel = max(P_hotel, 100.0)  # 안전 하한

#     # 중량/디스크
#     G.MTOW_kg = max(float(getattr(vehicle.mass_properties,'max_takeoff',0.0)), 1e-6)
#     G.W_N     = G.MTOW_kg * _g0
#     G.A_tot   = _get_total_lift_disk_area(params, vehicle)

#     # 기본 전진속도 (fallback)
#     G.V_cruise_mps_default = float(getattr(params,'V_cruise_mps', 50.0))
    
#     # 천이 관련 파라미터
#     G.drag_mult_start   = float(getattr(params,'transition_drag_mult_start', 1.05))
#     G.drag_mult_end     = float(getattr(params,'transition_drag_mult_end',   1.00))
#     G.rot_lift_start    = float(getattr(params,'transition_rotor_lift_frac_start', 1.00))
#     G.rot_lift_end      = float(getattr(params,'transition_rotor_lift_frac_end',   0.00))
#     G.extra_lift_gain   = float(getattr(params,'transition_extra_lift_gain', 0.0))
    
#     # wing climb/descent 보정 (캘리브레이션용)
#     G.forward_climb_cd0_mult        = float(getattr(params,'forward_climb_cd0_mult',       1.25))
#     G.forward_desc_cd0_mult         = float(getattr(params,'forward_desc_cd0_mult',        1.05))
#     G.forward_climb_delta_cd0_rotors= float(getattr(params,'forward_climb_delta_cd0_rotors',0.005))
#     G.forward_desc_delta_cd0_rotors = float(getattr(params,'forward_desc_delta_cd0_rotors', 0.0))
#     G.forward_climb_delta_cd0_gear  = float(getattr(params,'forward_climb_delta_cd0_gear',  0.0))
#     G.forward_desc_delta_cd0_gear   = float(getattr(params,'forward_desc_delta_cd0_gear',   0.0))
#     G.forward_climb_eta_prop_scale  = float(getattr(params,'forward_climb_eta_prop_scale',  0.90))
#     G.forward_desc_eta_prop_scale   = float(getattr(params,'forward_desc_eta_prop_scale',   1.00))
#     G.forward_climb_trim_power_frac = float(getattr(params,'forward_climb_trim_power_frac', 0.10))
#     G.forward_desc_trim_power_frac  = float(getattr(params,'forward_desc_trim_power_frac',  0.00))


#     return G




# def _estimate_CD0_quick(vehicle, params, V_mps, h_m):
#     """
#     기존 방식 유지 + 리프트 로터/외부 돌출물에 근거한 추가 CD0 예측 추가

#     params에서 사용 가능한 추가 필드(옵션):
#       - params.k_rotor_coeff (float): 로터 스케일 계수 k_r (default 3.0)
#       - params.rotor_exponent (float): 로터 수 지수 p_r (default 1.5)
#       - params.k_protrusion_coeff (float): 돌출물 계수 k_p (default 20.0)
#       - params.protrusion_area_scale_A0 (float): A0 (m2) 기준값 (default 1.0)
#       - params.use_wetted_protrusion (bool): 돌출물에 젖은면적 사용할지 여부 (default False)
#       - params.return_breakdown (bool): 계산 분해 결과를 vehicle._last_cd0_breakdown에 저장
#       - params.num_lift_props, params.prop_diameter, params.lift_rotor_area: 로터 관련 대체 입력
#       - params.protrusion_area: 외부 돌출물 총 전면 또는 젖은면적 대체 입력
#     """
#     import math as _m

#     # --- 대기 물성 (간단 ISA) ---
#     rho0, T0, L, R, g0 = 1.225, 288.15, -0.0065, 287.058, 9.80665
#     h   = max(float(h_m), 0.0)
#     if h < 11000.0:
#         T = T0 + L*h
#         rho = max(0.2, rho0*(T/T0)**(g0/(R*L)-1.0))
#         a   = (1.4*R*T)**0.5
#         mu  = 1.7894e-5 * (T/288.15)**1.5 * (288.15+110.4)/(T+110.4)
#     else:
#         T = 216.65
#         rho = 0.3
#         a   = (1.4*R*T)**0.5
#         mu  = 1.46e-5

#     V   = max(float(V_mps), 1e-3)
#     Sref = float(getattr(vehicle, 'reference_area', 0.0)) or 1.0

#     # --- 젖은면적 합 (날개 + 동체 + tails 기존 동작) ---
#     Swet = 0.0
#     for w in getattr(vehicle, 'wings', []):
#         Swet += float(getattr(getattr(w,'areas',object()), 'wetted', 0.0))
#     # fuselage
#     try:
#         Swet += float(vehicle.fuselages['fuselage'].areas.wetted)
#     except Exception:
#         Swet += float(getattr(getattr(vehicle, 'fuselage', object()), 'areas', object()).wetted or 0.0)
#     Swet = max(Swet, 1e-6)

#     # --- 특성 길이/레이놀즈/마하 ---
#     try:
#         L_char = float(getattr(getattr(vehicle, 'wings', {}).get('main_wing', object()), 'chords').MAC)
#     except Exception:
#         L_char = 1.0
#     Re = max(rho*V*L_char/max(mu,1e-9), 1e3)
#     M  = V/max(a,1e-9)

#     # Cf (turbulent compressible correction)
#     Cf = 0.455 / (_m.log10(Re)**2.58) / ((1.0 + 0.144*M*M)**0.65)

#     # 기본 형상/간섭 계수 (간이)
#     FF = 1.0
#     Q  = 1.0

#     # CD0 core
#     CD0_core = Cf * FF * Q * (Swet / Sref)

#     # --- 공통: 3D base-drag 계수 (논문 유사식) ---
#     CDB = 0.029 * _m.sqrt(max(Cf, 1e-12))

#     # -------------------------
#     # 1) 리프트 로터 관련 입력 추출
#     # -------------------------
#     # 우선 vehicle 내부 정보 시도
#     takeoff_mass  = getattr(getattr(vehicle, 'mass_properties', None), 'max_takeoff', None)
#     N_rot = params.number_of_rotors
#     A_rot_tot = (takeoff_mass / params.diskloading)


#     # -------------------------
#     # 2) 외부 돌출물(파일런, 프로브 등) 면적 추출
#     # -------------------------
#     A_prot = params.excrescence_area_fac * Sref


#     # -------------------------
#     # 3) 경험식에 의한 추가 CD0 계산
#     # -------------------------
#     # 튜닝 파라미터 (params에서 덮어쓰기 가능)
#     k_r = float(getattr(params, 'k_rotor_coeff', 0.62))             # 로터 수 계수
#     p_r = float(getattr(params, 'rotor_exponent', 1.0))             # 로터 수 지수
#     k_p = float(getattr(params, 'k_protrusion_coeff', 37.0))        # 돌출물 계수
#     A0  = float(getattr(params, 'protrusion_area_scale_A0', 1.0))

#     # 로터 스케일 (기하/간섭/허브/가드 등 복합효과를 근사)
#     rotor_scale = 1.0 + k_r * (N_rot**p_r) if N_rot>0 else 1.0
#     CD0_rotors = CDB * (A_rot_tot / Sref) * rotor_scale

#     # 돌출물 스케일 (면적에 비례하는 추가 효과)
#     prot_scale = 1.0 + k_p * (A_prot / max(A0, 1e-6))
#     CD0_protrusions = CDB * (A_prot / Sref) * prot_scale

#     # 최종
#     CD0_total = float(CD0_core + CD0_rotors + CD0_protrusions)
    

#     return CD0_total




# def _duration_hover(dh, ROC, dur_in, default_hover=30.0):
#     if _np.isfinite(dh) and _np.isfinite(ROC) and abs(ROC) > 1e-6 and abs(dh) > 0:
#         return abs(dh)/abs(ROC)
#     if _np.isfinite(dur_in) and dur_in > 0:
#         return dur_in
#     return default_hover

# def _duration_forward(dh, ROC, dist_m, V, dur_in, default_fwd=60.0):
#     if _np.isfinite(dh) and _np.isfinite(ROC) and abs(ROC) > 1e-6 and abs(dh) > 0:
#         return abs(dh)/abs(ROC)
#     if _np.isfinite(dist_m) and _np.isfinite(V) and dist_m > 0 and V > 0:
#         return dist_m/V
#     if _np.isfinite(dur_in) and dur_in > 0:
#         return dur_in
#     return default_fwd

# def _duration_cruise(dist_m, V, dur_in, default_fwd=60.0):
#     if _np.isfinite(dist_m) and _np.isfinite(V) and dist_m > 0 and V > 0:
#         return dist_m/V
#     if _np.isfinite(dur_in) and dur_in > 0:
#         return dur_in
#     return default_fwd

# def _pack_segment(tag, dur, P):
#     """SUAVE Data 포맷으로 한 세그먼트 결과 포장"""
#     out = _Data(); out.tag = tag
#     out.conditions = _Data()
#     out.conditions.frames = _Data(); out.conditions.frames.inertial = _Data()
#     out.conditions.frames.inertial.time = _np.array([0.0, dur], dtype=float)
#     out.conditions.propulsion = _Data()
#     out.conditions.propulsion.battery_power_draw = _np.array([P, P], dtype=float)
#     return out, dur * P  # [J]

# # ────────────────────────────────────────────────────────────────────────────
# # MODELS  (항력 블록, 호버 전력 등)
# # ────────────────────────────────────────────────────────────────────────────

# def _drag_block(W, V_cmd, rho, S, AR, e, CD0, CLmax_clean, stall_margin,
#                 cd0_extra=0.0, cd0_mult=1.0):
#     """
#     항력/스톨-가드 블록
#       - 속도는 스톨여유(stall_margin*CLmax)로부터 Vmin 보정
#       - CD0 -> (CD0 + cd0_extra) * cd0_mult
#     """
#     CL_allow = stall_margin * CLmax_clean
#     Vmin = _np.sqrt(W / max(1e-9, 0.5*rho*S*CL_allow))
#     V = max(float(V_cmd), Vmin, 1e-3)
#     q = 0.5*rho*V*V
#     CL = W/(q*S)
#     CDi = CL*CL/(_np.pi*AR*e)
#     CD0_eff = (CD0 + cd0_extra) * cd0_mult
#     CD = CD0_eff + CDi
#     D  = q*S*CD
#     return D, V, CL, CD, CD0_eff, Vmin

# def _hover_power(W, rho, A_tot, ROC, beta_hover, eta_hover_total):
#     """호버 전력(모멘텀 + 프로파일 근사)"""
#     vi   = _np.sqrt(max(W,1e-3) / (2.0*rho*max(A_tot,1e-6)))
#     Pind = W*vi + W*max(0.0, ROC)   # 상승률 항은 상승시에만 가산
#     return (1.0 + beta_hover) * Pind / max(1e-3, eta_hover_total)

# # ────────────────────────────────────────────────────────────────────────────
# # SEGMENT ENERGY  (타입별 계산 함수)
# # ────────────────────────────────────────────────────────────────────────────

# def seg_energy_hover(row, G, prev_alt_m):
#     """
#     Hover.Hover / Hover.Climb / Hover.Descent
#     입력 row: altitude_*_ft, climb/descent_rate_fpm, duration_s ...
#     """
#     tag = str(getattr(row,'tag','hover') or "")
#     # 고도
#     h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
#     h1_m = _f(getattr(row,'altitude_end_ft',None), h0_m/_FT) * _FT
#     dh   = h1_m - h0_m
#     rho  = _rho_at(0.5*(h0_m+h1_m))

#     # 상승/하강률
#     ROCc = _f(getattr(row,'climb_rate_fpm',None),   _np.nan) * _FPM
#     ROCd = _f(getattr(row,'descent_rate_fpm',None), _np.nan) * _FPM
#     ROC  = 0.0
#     cls  = (row.segment_class or "")
#     if 'Climb' in cls and _np.isfinite(ROCc):   ROC =  abs(ROCc)
#     if 'Descent' in cls and _np.isfinite(ROCd): ROC = -abs(ROCd)

#     # 지속시간
#     dur = _duration_hover(dh, ROC, _f(getattr(row,'duration_s',None), _np.nan), default_hover=30.0)

#     # 전력
#     if ROC < 0.0:
#         P = _hover_power(G.W_N, rho, G.A_tot, 0.0, G.beta_hover, G.eta_hover_total) + G.P_hotel
#     else:
#         P = _hover_power(G.W_N, rho, G.A_tot, ROC, G.beta_hover, G.eta_hover_total) + G.P_hotel

#     out, E = _pack_segment(tag, dur, P)
    
#     if ROC < 0.0:  # 수직 하강 페널티
#         E = E * G.k_vdes
#     if ROC > 0.0:  # 수직 상승 페널티
#         E = E * G.k_climb
    
#     return out, E, h1_m

# def seg_energy_cruise_loiter(row, G, prev_alt_m):
#     """
#     Cruise.Constant_Speed_Constant_Altitude
#     Cruise.Constant_Speed_Constant_Altitude_Loiter
#     """
#     tag = str(getattr(row,'tag','cruise') or "")
#     # 고도/밀도
#     h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
#     h1_m = _f(getattr(row,'altitude_end_ft',None), h0_m/_FT) * _FT
#     rho  = _rho_at(0.5*(h0_m+h1_m))

#     # 속도
#     V0 = _f(getattr(row,'air_speed_start_knots',None), _np.nan) * _KTS
#     V1 = _f(getattr(row,'air_speed_end_knots',None),   _np.nan) * _KTS
#     V_fixed = _f(getattr(row,'air_speed_knots',None),  _np.nan) * _KTS
#     if _np.isfinite(V_fixed):
#         V_cmd = V_fixed
#     elif _np.isfinite(V0) and _np.isfinite(V1):
#         V_cmd = 0.5*(V0+V1)
#     else:
#         V_cmd = V0 if _np.isfinite(V0) else (V1 if _np.isfinite(V1) else G.V_cruise_mps_default)

#     # 거리/시간
#     dist_m = _f(getattr(row,'distance_miles',None), _np.nan) * _MILE
#     dur_in = _f(getattr(row,'duration_s',None), _np.nan)

#     # 항력/전력
#     cd0_extra = 0
#     D, V, *_  = _drag_block(G.W_N, V_cmd, rho, G.S, G.AR, G.e, G.CD0, G.CLmax_clean, G.stall_margin,
#                             cd0_extra=cd0_extra, cd0_mult=1.0)
#     P = (D*V)/max(1e-3, G.eta_prop_total) + G.P_hotel

#     dur = _duration_cruise(dist_m, V, dur_in, default_fwd=60.0)
#     out, E = _pack_segment(tag, dur, P)
#     return out, E, h1_m


# def seg_energy_forward_rate(row, G, prev_alt_m):
#     """
#     Climb/Descent ... Constant_Rate (전진)
#     - 크루즈 항력 + 등률 항 + 부족양력 보전 + (옵션) 아이들/트림/효율 보정
#     - 본 블록은 '전진 등률' 구간(wing_climb / wing_descent)에 대한 보수적 보정 손잡이 포함
#       * params에서 전달된 전용 가중치로 CD0/추가드래그/추진효율/트림손실을 조절
#         - forward_climb_cd0_mult / forward_desc_cd0_mult
#         - forward_climb_delta_cd0_rotors / forward_desc_delta_cd0_rotors
#         - forward_climb_delta_cd0_gear   / forward_desc_delta_cd0_gear
#         - forward_climb_eta_prop_scale   / forward_desc_eta_prop_scale
#         - forward_climb_trim_power_frac  / forward_desc_trim_power_frac
#     """
#     tag = str(getattr(row,'tag','forward') or "")

#     # ── 고도/밀도
#     h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
#     h1_m = _f(getattr(row,'altitude_end_ft',None), h0_m/_FT) * _FT
#     dh   = h1_m - h0_m
#     rho  = _rho_at(0.5*(h0_m+h1_m))

#     # ── 속도(평균값 사용)
#     V0 = _f(getattr(row,'air_speed_start_knots',None), _np.nan) * _KTS
#     V1 = _f(getattr(row,'air_speed_end_knots',None),   _np.nan) * _KTS
#     if _np.isfinite(V0) and _np.isfinite(V1):
#         V_cmd = 0.5*(V0+V1)
#     else:
#         V_cmd = V0 if _np.isfinite(V0) else (V1 if _np.isfinite(V1) else G.V_cruise_mps_default)

#     # ── 등률(상승/하강 판정)
#     ROCc = _f(getattr(row,'climb_rate_fpm',None),   _np.nan) * _FPM
#     ROCd = _f(getattr(row,'descent_rate_fpm',None), _np.nan) * _FPM
#     ROC  = 0.0
#     cls  = (row.segment_class or "")
#     if 'Climb' in cls and _np.isfinite(ROCc):   ROC =  abs(ROCc)
#     if 'Descent' in cls and _np.isfinite(ROCd): ROC = -abs(ROCd)

#     is_climb   = (ROC >  1e-9)
#     is_descent = (ROC < -1e-9)

#     # ── 항력 보정 손잡이 설정
#     base_extra = G.delta_CD0_rotors + G.delta_CD0_gear
#     if is_climb:
#         cd0_extra = base_extra + G.forward_climb_delta_cd0_rotors + G.forward_climb_delta_cd0_gear
#         cd0_mult  = G.forward_climb_cd0_mult
#         eta_scale = G.forward_climb_eta_prop_scale
#         trim_frac = G.forward_climb_trim_power_frac
#     elif is_descent:
#         cd0_extra = base_extra + G.forward_desc_delta_cd0_rotors + G.forward_desc_delta_cd0_gear
#         cd0_mult  = G.forward_desc_cd0_mult
#         eta_scale = G.forward_desc_eta_prop_scale
#         trim_frac = G.forward_desc_trim_power_frac
#     else:
#         cd0_extra = base_extra
#         cd0_mult  = 1.0
#         eta_scale = 1.0
#         trim_frac = 0.0

#     # ── 항력/속도(스톨 가드 포함)
#     D, V, *_  = _drag_block(G.W_N, V_cmd, rho, G.S, G.AR, G.e, G.CD0, G.CLmax_clean, G.stall_margin,
#                             cd0_extra=cd0_extra, cd0_mult=cd0_mult)

#     # ── 부족양력 보전(로터 유사 전력)
#     CL_allow = G.stall_margin * G.CLmax_clean
#     L_avail  = 0.5*rho*V*V*G.S*CL_allow
#     L_def    = max(0.0, G.W_N - L_avail)
#     P_add    = 0.0
#     if L_def > 0.0:
#         vi_def = _np.sqrt(L_def / max(2.0*rho*G.A_tot, 1e-6))
#         P_add  = (L_def * vi_def)/max(1e-3, G.eta_hover_total)

#     # ── 추진 전력 (효율 보정 + 트림 손실)
#     T_req   = D + (G.W_N*ROC/max(1e-6, V))
#     eta_eff = max(1e-3, G.eta_prop_total * eta_scale)
#     P_prop  = (max(0.0, T_req) * V) / eta_eff
#     P_trim  = trim_frac * P_prop

#     # ── 디센트 아이들 손실(하강에서만 추가)
#     P_idle = G.P_idle_prop_W + (G.P_idle_prop_W_desc if is_descent else 0.0)

#     # ── 총 전력
#     P = P_idle + P_prop + P_trim + P_add + G.P_hotel

#     # ── 지속시간 산정
#     dist_m = _f(getattr(row,'distance_miles',None), _np.nan) * _MILE
#     dur_in = _f(getattr(row,'duration_s',None), _np.nan)
#     dur    = _duration_forward(dh, ROC, dist_m, V, dur_in, default_fwd=60.0)

#     # ── 결과 패키징
#     out, E = _pack_segment(tag, dur, P)
#     return out, E, h1_m




# def seg_energy_transition(row, G, prev_alt_m):
#     """
#     Transition.Constant_Acceleration_Constant_Angle_Linear_Climb (re-transition 포함)
#     - 속도: V0 -> V1 선형 변화(가속), 시간 등분 적분으로 에너지 산출
#     - 드래그: 전환 페널티 반영 (ΔCD0 + 배율)
#     - 부족양력: 각 속도점에서 보전(hover 효율), 10% 가산
#     - 추진: 프로펠러 전력 + (보전 전력) + 호텔부하
#     """
#     tag = str(getattr(row,'tag','transition') or "")

#     # -------- 고도/밀도 --------
#     h0_m = _f(getattr(row,'altitude_start_ft',None), 0.0 if prev_alt_m is None else prev_alt_m) * _FT
#     h1_m = _f(getattr(row,'altitude_end_ft',None),   h0_m/_FT) * _FT
#     dh   = h1_m - h0_m
#     rho  = _rho_at(0.5*(h0_m+h1_m))

#     # -------- 속도 (knots -> m/s) --------
#     V0 = _f(getattr(row,'air_speed_start_knots',None), _np.nan) * _KTS
#     V1 = _f(getattr(row,'air_speed_end_knots',None),   _np.nan) * _KTS
#     V_fixed = _f(getattr(row,'air_speed_knots',None), _np.nan) * _KTS

#     # V 명세가 없을 때의 fallback
#     if _np.isfinite(V_fixed):
#         V0 = V1 = V_fixed
#     else:
#         if not _np.isfinite(V0) and _np.isfinite(V1):
#             V0 = V1
#         if _np.isfinite(V0) and not _np.isfinite(V1):
#             V1 = V0
#         if not _np.isfinite(V0) and not _np.isfinite(V1):
#             V0 = V1 = G.V_cruise_mps_default

#     # -------- 등률 --------
#     ROCc = _f(getattr(row,'climb_rate_fpm',None),   _np.nan) * _FPM
#     ROCd = _f(getattr(row,'descent_rate_fpm',None), _np.nan) * _FPM
#     ROC  = 0.0
#     if _np.isfinite(ROCc): ROC =  abs(ROCc)
#     if _np.isfinite(ROCd): ROC = -abs(ROCd)

#     # -------- 거리/시간 --------
#     dist_m = _f(getattr(row,'distance_miles',None), _np.nan) * _MILE
#     dur_in = _f(getattr(row,'duration_s',None), _np.nan)

#     # 평균속도(선형 가속 가정)로 일단 전체 지속시간 산정
#     V_avg_for_dur = 0.5*(V0+V1)
#     dur = _duration_forward(dh, ROC, dist_m, V_avg_for_dur, dur_in, default_fwd=30.0)
#     dur = max(dur, 1e-3)

#     # -------- 전환 페널티 파라미터 --------
#     cd0_extra = G.delta_CD0_rotors + G.delta_CD0_gear
#     cd0_mult  = G.conversion_CD0_factor

#     # -------- 속도 구간 적분 (시간 등분, V 선형 변화) --------
#     N = int(getattr(G, 'transition_integration_steps', getattr(G, 'N_transition_steps', 20)) or 20)
#     N = max(5, min(N, 200))
#     dt = dur / N

#     E_sum = 0.0
#     P_peak = 0.0

#     for k in range(N):
#         tau = (k + 0.5) / N
#         V   = max(V0 + (V1 - V0) * tau, 1e-3)

#         # --- 전환 램프: 드래그 배율/부족양력 보전비율 ---
#         drag_mult_eff = G.drag_mult_start + (G.drag_mult_end - G.drag_mult_start) * tau
#         rotor_frac    = G.rot_lift_start  + (G.rot_lift_end  - G.rot_lift_start)  * tau
#         rotor_frac    = min(max(rotor_frac, 0.0), 1.0)

#         # 항력(전환 페널티: ΔCD0는 동일, 배율만 램프)
#         D, V_eff, CL, CD, CD0_eff, Vmin = _drag_block(
#             G.W_N, V, rho, G.S, G.AR, G.e, G.CD0, G.CLmax_clean, G.stall_margin,
#             cd0_extra=cd0_extra, cd0_mult=drag_mult_eff
#         )

#         # 부족양력 보전 (전환 중 가용양력에 약간 이득 옵션)
#         CL_allow = G.stall_margin * (G.CLmax_clean + G.extra_lift_gain)
#         L_avail  = 0.5*rho*V*V*G.S*CL_allow
#         L_def    = max(0.0, G.W_N - L_avail)

#         P_add = 0.0
#         if L_def > 0.0:
#             vi_def = _np.sqrt(L_def / max(2.0*rho*G.A_tot, 1e-6))
#             P_add  = rotor_frac * (L_def * vi_def) / max(1e-3, G.eta_hover_total)

#         # 추진 전력
#         T_req  = max(0.0, D + (G.W_N*ROC / max(V,1e-6)))
#         P_prop = (T_req * V) / max(1e-3, G.eta_prop_total)

#         P_total = G.P_idle_prop_W + P_prop + P_add + G.P_hotel
#         E_sum  += P_total * dt
#         P_peak  = max(P_peak, P_total)

#     # 평균 전력으로 세그먼트 패킹
#     P_avg = E_sum / dur
#     out = _Data(); out.tag = tag
#     out.conditions = _Data()
#     out.conditions.frames = _Data(); out.conditions.frames.inertial = _Data()
#     out.conditions.frames.inertial.time = _np.array([0.0, dur], dtype=float)
#     out.conditions.propulsion = _Data()
#     out.conditions.propulsion.battery_power_draw = _np.array([P_avg, P_avg], dtype=float)

#     return out, E_sum, h1_m



# # ────────────────────────────────────────────────────────────────────────────
# # MAIN  (기존 인터페이스 유지)
# # ────────────────────────────────────────────────────────────────────────────

# def evaluate_mission_energy_quick(params, vehicle, requirements, mission_profile):
#     """
#     수식 기반 빠른 미션 에너지 추정(모듈화 버전).
#     - 엑셀: mission_input_new.xlsx 포맷(단위 유지)
#     - 세그먼트 분류: Hover / Cruise·Loiter / Forward Constant-Rate(Climb/Descent) / Transition
#     - 출력: 각 세그먼트의 time, battery_power_draw 포함한 SUAVE Data
#     """
#     G = _collect_globals(params, vehicle, requirements)

#     results  = _Data(); results.segments = []
#     seg_rows = []
#     prev_alt_m = None

#     for row in mission_profile.segments:
#         cls = (row.segment_class or "")
#         tag = str(getattr(row,'tag','seg') or "")

#         # 분기
#         if cls.startswith('Hover'):
#             out, E, prev_alt_m = seg_energy_hover(row, G, prev_alt_m)
#         elif ('Cruise' in cls and 'Constant_Speed' in cls) or ('Loiter' in cls):
#             out, E, prev_alt_m = seg_energy_cruise_loiter(row, G, prev_alt_m)
#         elif (('Climb' in cls) or ('Descent' in cls)) and ('Constant_Rate' in cls):
#             out, E, prev_alt_m = seg_energy_forward_rate(row, G, prev_alt_m)
#         elif cls.startswith('Transition.'):
#             out, E, prev_alt_m = seg_energy_transition(row, G, prev_alt_m)
#         else:
#             # 미지원 → 건너뛰기
#             prev_alt_m = _f(getattr(row,'altitude_end_ft',None), 0.0)*_FT
#             continue

#         # 결과 누적/로그
#         results.segments.append(out)
#         dur = float(out.conditions.frames.inertial.time[-1] - out.conditions.frames.inertial.time[0])
#         Pk  = float(out.conditions.propulsion.battery_power_draw.max())
#         seg_rows.append((tag, dur, E/1e6, Pk/1000.0))

#     # 표 출력
#     if seg_rows:
#         print("\n======================mission======================")
#         print(f"{'segment':<28s} | {'dur[s]':>7s} | {'energy[MJ]':>12s} | {'peak[kW]':>9s}")
#         print("-"*62)
#         for tag, dur, Emj, Pk in seg_rows:
#             print(f"{tag:<28s} | {dur:7.0f} | {Emj:12.2f} | {Pk:9.2f}")
#         print("-"*62)
#         total_dur = sum(r[1] for r in seg_rows)
#         total_Emj = sum(r[2] for r in seg_rows)
#         total_Pk  = sum(r[3] for r in seg_rows)
#         print(f"{'TOTAL':<28s} | {total_dur:7.0f} | {total_Emj:12.2f} | {total_Pk:9.2f}")
#     print()

#     # 안전망: 비어있으면 1초 호텔부하 더미
#     if not results.segments:
#         out, _E = _pack_segment("dummy", 1.0, G.P_hotel)
#         results.segments.append(out)

#     return results

# # ========================= /QUICK MISSION ENERGY (MODULAR) ===========================