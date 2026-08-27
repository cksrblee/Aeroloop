## @ingroup Methods-Sizing
# sizing_thrust_prop.py 

# Created:  09.09 2025, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import numpy as np
from math import sqrt
from SUAVE.Core import Data, Units
from SUAVE.Components.Energy.Converters import Propeller
from SUAVE.Components.Airfoils import Airfoil
from SUAVE.Methods.Propulsion import propeller_design

# ======================================================================
#  sizing_thrust_prop.py
#  - Mission-based cruise propeller sizing (balanced heuristic)
#  - SUAVE Propeller 구성 + propeller_design 호출
# ======================================================================

# ---------------- ISA 간이 모델 (대류권 근사) ----------------
G0     = 9.80665
GAMMA  = 1.4
R_AIR  = 287.05
T0     = 288.15
P0     = 101325.0
LAMBDA = -0.0065
H_TROP = 11000.0

def _isa_T(alt_m: float) -> float:
    h = max(0.0, float(alt_m))
    return T0 + LAMBDA*min(h, H_TROP)

def _isa_a(alt_m: float) -> float:
    """음속 [m/s]"""
    T = _isa_T(alt_m)
    return sqrt(GAMMA * R_AIR * T)

def _isa_rho(alt_m: float) -> float:
    """밀도 [kg/m^3]"""
    h = max(0.0, float(alt_m))
    if h <= H_TROP:
        T = T0 + LAMBDA*h
        expo = -G0/(LAMBDA*R_AIR)
        P = P0 * (T/T0)**expo
    else:
        T = T0 + LAMBDA*H_TROP
        expo = -G0/(LAMBDA*R_AIR)
        P = P0 * (T/T0)**expo
    return P/(R_AIR*T)



def _estimate_CD0_quick(vehicle, main_wing, fuselage_design, params, V_mps, h_m):
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
    Sref = main_wing.wing_area

    # --- 젖은면적 합 (날개 + 동체 + tails 기존 동작) ---
    # --- 젖은면적 합 ---
    Swet = 0.0
    # 날개류
    Swet += 3.0 * Sref # 날개류 합산 (간이: 3*Sref)

    # 동체류
    Swet += fuselage_design.areas.wetted
    
    Swet = max(Swet, 1e-6)  # 안전망

    # --- 특성 길이/레이놀즈/마하 ---
    L_char = main_wing.MAC
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
    MTOW  = getattr(getattr(vehicle, 'mass_properties', None), 'max_takeoff', None)
    takeoff_mass          = MTOW or params.initial_MTOW  # [kg]
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



def sizing_thrust_prop(requirements, params, main_wing, fuselage_design, vehicle):
    """
    Mission-based cruise prop sizing (balanced heuristic).

    절차(개념설계용):
      1) 크루즈 상태에서 기체 항력 산정 → 총 설계 추력 T_total = D * 여유계수
      2) 프롭 수로 나눠 per-prop 추력 T_per
      3) 축동력 추정 P_shaft ≈ T_per * V / eta_prop (개념치)
      4) 지름 후보 3종 계산
         - D_prim : 모멘텀/전진 모델 (전진비 내 유도속도 포함)
         - D_J    : 목표 advance ratio 하한 J_target으로부터
         - D_DL   : 목표 디스크 로딩 하한 DL_target으로부터
      5) 가중 평균으로 균형 지름 결정 후 [D_min, D_max]로 clip
      6) 팁마하/회전수 상한을 동시 고려하여 omega 선정
      7) SUAVE Propeller 구성 → 에어포일 부착 → propeller_design() 실행
      8) design_power/design_torque 보장 세팅 (모터 사이징과 연계)

    반환: SUAVE Propeller 객체
    """

    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)
            

    # ---------------- 0) 입력 로드 ----------------
    # 크루즈 상태
    V       = float(getattr(params, 'V_cruise_mps', 65.0))   # [m/s]
    h       = float(getattr(params, 'cruise_altitude_m',
                            getattr(requirements, 'design_altitude', 0.0)))  # [m]
    a_sound = _isa_a(h)
    rho     = _isa_rho(h)

    # 기체/날개/항력
    takeoff_mass     = getattr(getattr(vehicle, 'mass_properties', None), 'max_takeoff', None)  # 이륙중량 업데이트
    MTOW_kg  = takeoff_mass or params.initial_MTOW  # [kg]
    
    W_N     = MTOW_kg * G0
    S_w     = float(main_wing.wing_area)
    AR      = float(params.aspect_ratio)
    e       = float(getattr(params, 'oswald_e', 0.80))
    CD0    = _estimate_CD0_quick(vehicle, main_wing, fuselage_design, params, V, h)
    
    T_margin= float(getattr(params, 'prop_thrust_margin', 1.15))

    # 프롭 설정
    N_props   = int(getattr(params, 'number_of_thruster', 1))
    eta_prop  = float(getattr(params, 'prop_eta_guess', 0.80))
    rpm_cruise= float(getattr(params, 'prop_cruise_rpm', 1800.0))
    J_target  = float(getattr(params, 'prop_target_J', 0.65))
    DL_target = float(getattr(params, 'prop_target_DL_Nm2', 600.0))
    M_tip_max = float(getattr(params, 'prop_tip_mach_max', 0.70))
    Rhub_frac = float(getattr(params, 'prop_hub_radius_frac', 0.10))
    n_blades  = int(getattr(params, 'number_of_blades_prop', 3))

    # 위치/오프셋 (원하면 직접 지정 가능)
    prop_origin = getattr(params, 'prop_origin', None)  # e.g., [x,y,z] in meters
    prop_offset_frac = float(getattr(params, 'prop_offset_frac', 0.02))
    prop_origin_y    = float(getattr(params, 'prop_origin_y', 0.0))

    # 에어포일 (필수 경로를 params에서)
    airfoil_geom  = getattr(params, 'prop_airfoil_geom_file',
                            getattr(params, 'airfoil_geom_file', './Airfoils/NACA_4412.txt'))
    airfoil_polars= list(getattr(params, 'prop_airfoil_polar_files',
                                 getattr(params, 'airfoil_polar_files', [])))
    Cl_design     = float(getattr(params, 'prop_design_Cl', 0.70))

    # ---------------- 1) 항력 → 설계 추력 ----------------
    q   = 0.5 * rho * V**2
    CL  = W_N / max(q * S_w, 1e-12)
    k   = 1.0 / (np.pi * e * AR)
    CD  = CD0 + k * CL**2
    D_N = q * S_w * CD                        # 총 항력 [N]
    T_total = D_N * T_margin                  # 총 설계 추력 [N]

    # per-prop 추력/축동력(개념치)
    T_per  = T_total / max(N_props, 1)
    P_shaft= max((T_per * V) / max(eta_prop, 1e-6), 1e-6)  # [W]

    # ---------------- 2) 직경 후보 ----------------
    # (1) Momentum forward primary
    vi     = max(P_shaft / max(T_per, 1e-9) - V, 1e-6)       # [m/s]
    A_prim = T_per / max(2.0 * rho * vi * (V + vi), 1e-9)    # [m^2]
    D_prim = 2.0 * np.sqrt(max(A_prim, 1e-12) / np.pi)       # [m]

    # (2) J 하한
    n_hz   = rpm_cruise / 60.0                               # [rev/s]
    D_J    = V / max(n_hz * J_target, 1e-6)                  # [m]

    # (3) DL 하한
    A_DL   = T_per / max(DL_target, 1e-9)                    # [m^2]
    D_DL   = 2.0 * np.sqrt(max(A_DL, 1e-12) / np.pi)         # [m]

    # 균형 지름 (가중 평균) + 클리핑
    w_prim, w_J, w_DL = 0.5, 0.3, 0.2
    D_bal  = (w_prim*D_prim + w_J*D_J + w_DL*D_DL) / (w_prim+w_J+w_DL)
    D_min  = float(getattr(params, 'prop_min_d_m', 1.00))
    D_max  = float(getattr(params, 'prop_max_d_m', 3.50))
    D      = float(np.clip(D_bal, D_min, D_max))
    R      = 0.5 * D
    Rhub   = Rhub_frac * R

    # ---------------- 3) 팁마하/회전 제한 → ω ----------------
    omega_tip = (M_tip_max * a_sound) / max(R, 1e-9)          # [rad/s]
    omega_rpm = (rpm_cruise * 2.0*np.pi) / 60.0               # [rad/s]
    omega     = min(omega_tip, omega_rpm)
    rpm_final = omega * 60.0 / (2.0*np.pi)

    # ---------------- 4) 위치(origin) ----------------
    if prop_origin is not None:
        x0, y0, z0 = [float(v) for v in prop_origin]
    else:
        # 동체 마지막 세그먼트 기준 후방 약간(offset_frac*L) 이동 (튜토리얼 유사)
        tail_seg = fuselage_design.segments[-1]
        fus_L    = float(fuselage_design.lengths.total)
        x0 = fus_L * float(tail_seg.percent_x_location + prop_offset_frac)
        y0 = prop_origin_y
        z0 = 0.5 * float(tail_seg.height)

    # ---------------- 5) SUAVE Propeller 구성 ----------------
    prop = Propeller()
    prop.tag                = 'cruise_prop'
    prop.origin             = [[x0, y0, z0]]
    prop.number_of_blades   = n_blades
    prop.tip_radius         = R
    prop.hub_radius         = Rhub
    prop.angular_velocity   = omega               # [rad/s]
    prop.freestream_velocity= V                   # [m/s]
    prop.design_Cl          = Cl_design
    prop.design_altitude    = h * Units.meter     # [m]
    prop.design_thrust      = T_per               # [N]
    prop.variable_pitch     = False               # 튜토리얼과 일치

    # 에어포일
    af = Airfoil()
    af.coordinate_file = airfoil_geom
    af.polar_files     = airfoil_polars
    prop.append_airfoil(af)
    prop.airfoils = [af]
    prop.airfoil_polar_stations = np.zeros((20), dtype=np.int8).tolist()

    # ---------------- 6) SUAVE 설계 실행 ----------------
    prop = propeller_design(prop)

    # ---------------- 7) design_power/torque 보강 ----------------
    # 일부 케이스에서 propeller_design이 design_torque를 채우지 못할 수 있음
    # (모터 사이징 size_optimal_motor가 필요로 하므로 반드시 채움)
    if not hasattr(prop, 'design_power'):
        prop.design_power = float(P_shaft)
    if not hasattr(prop, 'angular_velocity') or (prop.angular_velocity is None) or (prop.angular_velocity == 0):
        prop.angular_velocity = float(omega)
    if not hasattr(prop, 'design_torque'):
        prop.design_torque = float(prop.design_power) / max(float(prop.angular_velocity), 1e-9)

    #  ---------------- 8) 요약 출력 ----------------
    try:
        try:
            ox, oy, oz = prop.origin[0]
        except Exception:
            ox, oy, oz = (x0, y0, z0)

        af_set = 'set' if len(prop.airfoils) > 0 else 'none'
        n_polars = len(airfoil_polars) if airfoil_polars is not None else 0

        _log(
            f"[cruise prop] N={N_props}, D={D:.3f} m, R={R:.3f} m, "
            f"T/rot={T_per:.1f} N, x={ox:.3f}, y={oy:.3f}, z={oz:.3f}, "
            f"airfoil={af_set}, polars={n_polars} files, ω={prop.angular_velocity:.1f} rad/s"
        )
    except Exception:
        pass

    return prop
