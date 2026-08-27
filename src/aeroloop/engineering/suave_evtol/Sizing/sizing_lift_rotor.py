## @ingroup Methods-Sizing
# sizing_lift_rotor.py 

# Created:  09.09 2025, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import numpy as np
from math import sqrt
from copy import deepcopy
from SUAVE.Core import Data, Units
from SUAVE.Components.Energy.Converters import Lift_Rotor
from SUAVE.Components.Airfoils import Airfoil
from SUAVE.Methods.Propulsion import propeller_design

# ======================================================================
#  sizing_lift_rotor.py  (ESSENTIALS-ONLY, 4/8/12 rotors)
#  - Lift rotor sizing from MTOW & disk loading
#  - Placement: half front, half back; indexing & rotation rules enforced
# ======================================================================

# --- 상수(ISA 근사) ---
G0     = 9.80665          # [m/s^2]
GAMMA  = 1.4
R_AIR  = 287.05           # [J/(kg·K)]
T0     = 288.15           # [K]
LAMBDA = -0.0065          # [K/m]
H_TROP = 11000.0          # [m]
P0     = 101325.0         # [Pa]

def _isa_speed_of_sound(alt_m: float) -> float:
    """대류권까지만 간단 ISA로 음속 계산."""
    h = max(0.0, float(alt_m))
    T = T0 + (LAMBDA * min(h, H_TROP))
    return sqrt(GAMMA * R_AIR * T)

def _isa_density(alt_m: float) -> float:
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

def sizing_lift_rotor(requirements, params, main_wing, fuselage_design, vehicle):
    """
    리프트 로터 사이징 + 배치 (4/8/12개 지원, SUAVE Lift_Rotor 반환)

    배치 규칙
      - x : '루트 LE + 0.25*MAC' 중앙점 기준 전/후 두 줄
            전/후 간격 = (D_rot + c_root) + (x_offset_m + x_offset_frac*D_rot)
      - y : 동체 반폭 + R + (y_margin_frac*D_rot)에서 시작, 등간격으로 좌→우
      - z : 날개 z + (z_offset_m + z_offset_frac*D_rot)
      - 번호 : 전방 좌→우 1..m / 후방 우→좌 m+1..N
      - 회전 : 홀수(CCW=+1), 짝수(CW=-1)

    필수 params:
      initial_MTOW[kg], diskloading[kg/m^2], number_of_rotors∈{4,8,12},
      hover_thrust_margin[-], hover_tip_mach_max[-],
      lift_rotor_hub_radius_frac[-],
      lift_z_offset_m[m], lift_z_offset_frac_of_D[-],
      lift_x_spacing_offset_m[m], lift_x_spacing_offset_frac[-],
      lift_y_spacing_offset_frac[-]
      (선택) number_of_blades_lift[-](기본 4)

    에어포일 경로 (이 버전에서 사용):
      airfoil_geom_file[str], airfoil_polar_files[list[str]]

    필수 참조:
      main_wing.origin[[x,y,z]], main_wing.MAC[m], main_wing.root_chord[m]
      fuselage_design.width[m]

    선택 requirements:
      design_altitude[m]  (팁 마하→각속도 변환용 음속 추정)
    """

    # -------- 0) 입력 로드/검증 --------
    takeoff_mass     = getattr(getattr(vehicle, 'mass_properties', None), 'max_takeoff', None)  # 이륙중량 업데이트
    MTOW_kg  = takeoff_mass or params.initial_MTOW  # [kg]
    
    DL_kgm2 = float(params.diskloading)
    N_rot   = int(params.number_of_rotors)
    if N_rot not in (4, 8, 12):
        raise ValueError("number_of_rotors는 4, 8, 12 중 하나여야 합니다.")

    hov_mrg = float(params.hover_thrust_margin)
    M_tip   = float(params.hover_tip_mach_max)
    hub_fr  = float(params.lift_rotor_hub_radius_frac)
    if MTOW_kg <= 0:  raise ValueError("initial_MTOW는 양수여야 합니다.")
    if DL_kgm2 <= 0:  raise ValueError("diskloading(kg/m^2)은 양수여야 합니다.")
    if hov_mrg < 1.0: raise ValueError("hover_thrust_margin은 1.0 이상 권장.")
    if not (0.2 <= M_tip <= 0.9):
        raise ValueError("hover_tip_mach_max는 0.2~0.9 범위 권장.")
    if not (0.0 < hub_fr < 1.0):
        raise ValueError("lift_rotor_hub_radius_frac는 (0,1) 범위.")

    # 배치 오프셋
    z_off_m     = float(params.lift_z_offset_m)
    z_off_fr    = float(params.lift_z_offset_frac_of_D)
    xgap_off_m  = float(params.lift_x_spacing_offset_m)
    xgap_off_fr = float(params.lift_x_spacing_offset_frac)
    y_margin_fr = float(params.lift_y_spacing_offset_frac)

    # 에어포일/공력
    n_blades = int(getattr(params, 'number_of_blades_lift', 4))
    airfoil_geom   = getattr(params, 'airfoil_geom_file', './Airfoils/NACA_4412.txt')
    airfoil_polars = list(getattr(params, 'airfoil_polar_files', []))
    V_fpm          = float(getattr(params, 'lift_rotor_freestream_fpm', 500.0))   # [ft/min]
    Cl_design      = float(getattr(params, 'lift_rotor_design_Cl', 0.70))         # section Cl

    # 메인윙/동체 필수 필드
    if not (hasattr(main_wing, 'origin') and main_wing.origin and len(main_wing.origin[0]) >= 3):
        raise ValueError("main_wing.origin([[x,y,z]])이 필요합니다.")
    x_le_root = float(main_wing.origin[0][0])
    z_wing    = float(main_wing.origin[0][2])
    MAC       = float(main_wing.MAC)
    c_root    = float(main_wing.root_chord)
    fus_w     = float(fuselage_design.width)

    # -------- 1) 로터 사이징 --------
    A_total = MTOW_kg / DL_kgm2                 # [m^2]
    A_one   = A_total / N_rot                   # [m^2]
    R_tip   = sqrt(A_one / np.pi)               # [m]
    D_rot   = 2.0 * R_tip                       # [m]
    R_hub   = hub_fr * R_tip                    # [m]

    T_per   = (MTOW_kg * G0 * hov_mrg) / N_rot  # [N]

    # 팁 마하 → 각속도
    alt_m = float(getattr(requirements, 'design_altitude', 0.0))
    a_snd = _isa_speed_of_sound(alt_m)
    omega = (M_tip * a_snd) / max(R_tip, 1e-9)  # [rad/s]
    
    # 유도동력(백업용)
    rho   = _isa_density(alt_m)
    P_ind = (T_per**1.5) / max(np.sqrt(2.0 * rho * A_one), 1e-12)   # [W]
    Q_ind = P_ind / max(omega, 1e-9)                                # [N·m]

    # -------- 2) 배치(x,y,z) --------
    x_center  = x_le_root + 0.25 * MAC
    spacing_x = (D_rot + c_root) + xgap_off_m + xgap_off_fr * D_rot
    x_front   = x_center - 0.5 * spacing_x
    x_back    = x_center + 0.5 * spacing_x
    z0        = z_wing + z_off_m + z_off_fr * D_rot

    # y: 전/후 한 줄당 m개
    m      = N_rot // 2
    y_base = 0.5 * fus_w + R_tip + y_margin_fr * D_rot
    dy     = D_rot + y_margin_fr * D_rot
    idxs   = list(range(m // 2))                # 0..(m/2-1)
    y_abs  = [y_base + i * dy for i in idxs]    # [y0, y1, ...]
    y_front = ([-y for y in reversed(y_abs)] + y_abs)   # 좌→우
    y_back  = list(reversed(y_front))                    # 우→좌

    # -------- 3) 템플릿 Lift_Rotor 생성 (에어포일 포함) --------
    lr_t = Lift_Rotor()
    lr_t.tag               = 'lift_rotor_template'
    lr_t.tip_radius        = float(R_tip)
    lr_t.hub_radius        = float(R_hub)
    lr_t.number_of_blades  = n_blades
    lr_t.design_tip_mach   = float(M_tip)
    lr_t.angular_velocity  = float(omega)
    lr_t.design_thrust     = float(T_per)
    lr_t.variable_pitch    = False
    lr_t.freestream_velocity = V_fpm * Units['ft/min']   # [m/s]
    lr_t.design_Cl           = Cl_design
    lr_t.design_altitude     = alt_m * Units.meter

    # 에어포일 부착
    af = Airfoil()
    af.coordinate_file = airfoil_geom
    af.polar_files     = airfoil_polars
    lr_t.append_airfoil(af)
    lr_t.airfoils = [af]
    lr_t.airfoil_polar_stations = np.zeros((20), dtype=np.int8).tolist()

    # SUAVE 설계 실행 → design_torque 등 내부 필드 생성
    lr_t = propeller_design(lr_t)

    # 백업: 혹시 design_torque/Power가 없다면 유도치로 채움
    if not hasattr(lr_t, 'design_torque'):
        lr_t.design_power  = float(P_ind)
        lr_t.design_torque = float(Q_ind)

    # ---------- 4) 인스턴스 생성/배치/회전 ----------
    rotors = []

    # 전방 1..m (좌→우)
    for i in range(m):
        lr = deepcopy(lr_t)
        lr.tag     = f"lift_rotor_{i+1}"
        lr.origin  = [[float(x_front), float(y_front[i]), float(z0)]]
        lr.rotation = +1 if ((i+1) % 2 == 1) else -1
        rotors.append(lr)

    # 후방 m+1..N (우→좌)
    for j in range(m):
        idx = m + j + 1
        lr = deepcopy(lr_t)
        lr.tag     = f"lift_rotor_{idx}"
        lr.origin  = [[float(x_back), float(y_back[j]), float(z0)]]
        lr.rotation = +1 if (idx % 2 == 1) else -1
        rotors.append(lr)

    # (선택) 로그
    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)

    _log(
        f"[lift rotor] N={N_rot} (front/back={m}/{m}), "
        f"D={D_rot:.3f} m, R={R_tip:.3f} m, T/rot={T_per:.1f} N, "
        f"x: front={x_front:.3f}, back={x_back:.3f}, "
        f"y_base={y_base:.3f}, dy={dy:.3f}, z={z0:.3f}, "
        f"airfoil={'set' if airfoil_geom else 'none'}, polars={len(airfoil_polars)} files, "
        f"ω={omega:.1f} rad/s"
    )

    return rotors