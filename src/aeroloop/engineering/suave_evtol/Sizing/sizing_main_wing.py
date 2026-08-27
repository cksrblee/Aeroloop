# ======================================================================
#  sizing_main_wing.py  (ESSENTIALS-ONLY + incidence & airfoil support)
# ======================================================================
from SUAVE.Core import Data, Units
import numpy as np

def sizing_main_wing(params, fuselage_design, vehicle):
    """
    MTOW, AR, W/S, taper로 주익 형상을 정하고, 동체 치수 기반 origin을 배치.
    추가: 주익 붙임각(incidence)과 에어포일(좌표/폴라 파일) 지정 지원.
    """
    # ---------------- 0) 필수 입력 로드/검증 ----------------
    takeoff_mass  = getattr(getattr(vehicle, 'mass_properties', None), 'max_takeoff', None)
    MTOW          = takeoff_mass or params.initial_MTOW  # [kg]

    WS    = float(params.wingloading)           # [kg/m^2]
    AR    = float(params.aspect_ratio)          # [-]
    taper = float(params.taper)                 # [-]

    if WS <= 0.0:      raise ValueError("wingloading(kg/m^2)은 양수여야 합니다.")
    if AR <= 0.0:      raise ValueError("aspect_ratio는 양수여야 합니다.")
    if not (0.05 <= taper <= 1.0):
        raise ValueError("taper는 0.05~1.0 범위 권장(0=triangular 금지).")

    # --- 배치 ---
    tail_clear = float(params.wing_TE_tail_clear_m)   # [m]
    nose_clear = float(params.wing_LE_front_clear_m)  # [m]
    h_frac     = float(params.wing_height_frac)       # [-] 0~1
    y0         = float(params.wing_origin_y)          # [m]
    if not (0.0 <= h_frac <= 1.0):
        raise ValueError("wing_height_frac는 0~1 범위여야 합니다.")

    # --- 동체 정보(필수) ---
    if fuselage_design is None:
        raise ValueError("fuselage_design(Data)이 필요합니다. (sizing_fuselage() 결과 전달)")
    L_fus = float(getattr(fuselage_design.lengths, 'total'))
    H_fus = float(getattr(fuselage_design.heights, 'maximum'))
    W_fus = float(getattr(fuselage_design, 'width'))

    # ---------------- 1) 기본 형상 ----------------
    S      = MTOW / WS                                 # [m^2]
    b      = np.sqrt(AR * S)                           # [m]
    c_root = 2.0 * S / (b * (1.0 + taper))             # [m]
    c_tip  = c_root * taper                            # [m]
    MAC    = (2.0/3.0) * c_root * (1 + taper + taper**2) / (1 + taper)
 
    # ---------------- 2) origin 배치 ----------------
    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)

    frac = getattr(params, 'wing_origin_x_frac', None)
    if frac is None:
        x_origin = L_fus - tail_clear - c_root
    else:
        frac = float(frac)
        if not (0.0 <= frac <= 1.0):
            raise ValueError("params.wing_origin_x_frac must be between 0 and 1.")
        desired_mac25_x     = frac * L_fus
        x_origin_from_frac  = desired_mac25_x - 0.25 * MAC
        x_min               = nose_clear
        x_max               = L_fus - tail_clear - c_root
        x_origin            = min(max(x_origin_from_frac, x_min), x_max)
        if abs(x_origin - x_origin_from_frac) > 1e-6:
            _log(f"[WARN] requested MAC25 at {desired_mac25_x:.3f} m clamped to valid range -> x_origin={x_origin:.3f} m")
 
    z_origin = (h_frac - 0.5) * H_fus
    # y = y0

    # ---------------- 3) 동체 폭 기반 노출 루트 오프셋 ----------------
    exposed_root_chord_offset = W_fus / max(b, 1e-9)   # [-]

    # ---------------- 4) 붙임각(incidence) & 에어포일 처리 ----------------
    # 붙임각: deg 입력 → rad 내부값. 기본은 0 deg.
    incidence_deg = float(getattr(params, 'wing_incidence_angle', 0.0))
    incidence_rad = incidence_deg * Units.deg

    # 에어포일: 좌표/폴라 파일은 선택 입력. 경로만 붙여도 OK(로더는 별도 단계에서)
    airfoil_geom  = getattr(params, 'wing_airfoil_geom_file',
                            getattr(params, 'wing_airfoil_polar_files', './Airfoils/NACA_4412.txt'))
    airfoil_polars= list(getattr(params, 'wing_airfoil_polar_files',
                                getattr(params, 'airfoil_polar_files', [])))
        

    # ---------------- 5) 패키징 ----------------
    main_wing = Data()
    main_wing.spans          = float(b)
    main_wing.root_chord     = float(c_root)
    main_wing.tip_chord      = float(c_tip)
    main_wing.wing_area      = float(S)
    main_wing.MAC            = float(MAC)
    main_wing.origin         = [[float(x_origin), float(y0), float(z_origin)]]
    main_wing.exposed_root_chord_offset = float(exposed_root_chord_offset)
    main_wing.MAC_25_x       = float(x_origin + 0.25 * MAC)
    main_wing.airfoil_geom   = airfoil_geom
    main_wing.airfoil_polars = airfoil_polars

    # === incidence & airfoil ===
    # SUAVE 윙 객체 관례: twists.root/tip (rad). 붙임각만 주는 경우 root=tip=incidence.
    main_wing.twists = Data()
    main_wing.twists.root = float(incidence_rad)
    main_wing.twists.tip  = float(incidence_rad)
    # 사람이 읽기 쉬운 값도 함께 보관(디버그용)
    main_wing.incidence_deg = float(incidence_deg)


    # --- 요약 출력 ---
    try:
        ox, oy, oz = main_wing.origin[0]
        ai = main_wing.incidence_deg
        af_tag = getattr(params, 'wing_airfoil', 'unset')
        _log(
            f"[main wing] span={main_wing.spans:.3f} m, S={main_wing.wing_area:.3f} m^2, "
            f"c_root={main_wing.root_chord:.3f} m, c_tip={main_wing.tip_chord:.3f} m, "
            f"MAC={main_wing.MAC:.3f} m, MAC25_x={main_wing.MAC_25_x:.3f} m, "
            f"origin=({ox:.3f},{oy:.3f},{oz:.3f}), exposed_root_frac={main_wing.exposed_root_chord_offset:.3f}, "
            f"incidence={ai:.2f} deg, airfoil={af_tag}"
        )
    except Exception:
        pass

    return main_wing