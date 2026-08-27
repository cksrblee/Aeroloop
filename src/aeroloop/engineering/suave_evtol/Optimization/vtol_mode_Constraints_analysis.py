## @ingroup Methods-Optimization
# vtol_mode_Constraints_analysis.py 

# Created:  11.18 2025, Chanyoung Joo
# Modified: 11.19 2025, auto-save plots added (no blocking GUI)

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import os
import datetime
import numpy as np
import matplotlib.pyplot as plt
from SUAVE.Core    import Data

# ------------------------------
# 1) Atmosphere model (simple ISA)
# ------------------------------
def isa_density(h_m):
    """
    Simple ISA density up to ~11 km.
    h_m : altitude [m]
    return: rho [kg/m^3]
    """
    T0 = 288.15      # K
    p0 = 101325.0    # Pa
    L  = 0.0065      # K/m
    R  = 287.058     # J/(kg*K)
    g  = 9.80665     # m/s^2

    h = max(h_m, 0.0)
    T = T0 - L*h
    p = p0 * (T/T0)**(g/(R*L))
    rho = p/(R*T)
    return rho


# ------------------------------
# 2) VTOL 성능 제약: DL + ROC + Drag → required margin
# ------------------------------
def required_margin_from_DL_with_drag(
    DL_mass,       # [kg/m^2]  disk loading (mass-based, MTOW/total rotor disk area)
    MTOW_kg,       # [kg]
    ROC,           # [m/s] vertical climb rate
    rho,           # [kg/m^3] air density at given altitude
    A_proj,        # [m^2] projected area in climb direction
    CD_fp=1.1      # [-] flat-plate drag coefficient
):
    """
    Momentum-theory based estimate of minimum hover_thrust_margin (m = T_avail/W)
    such that installed hover power (sized at T_avail) is sufficient to sustain
    vertical climb ROC against weight + flat-plate drag.
    """
    
    g0 = 9.81
    
    if ROC <= 0.0:
        return 1.0

    # Weight and rotor area
    W = MTOW_kg * g0            # [N]
    A = MTOW_kg / DL_mass       # [m^2] total rotor disc area (since DL_mass = m/A)

    # Flat-plate drag in vertical climb (V = ROC)
    D = 0.5 * rho * ROC**2 * CD_fp * A_proj   # [N]

    # Effective weight (weight + drag)
    W_eff = W + D

    # Base hover induced velocity at T = W (no drag)
    v_i0_base = np.sqrt(W / (2.0 * rho * A))

    # Hover induced velocity corresponding to W_eff
    v_i0_eff = np.sqrt(W_eff / (2.0 * rho * A))

    # Vertical climb momentum theory (Rankine–Froude)
    lam = ROC / (2.0 * v_i0_eff)
    v_i = v_i0_eff / (lam + np.sqrt(1.0 + lam**2))

    # Installed hover power sized at T_avail = m W:
    rhs   = (W_eff / W) * (v_i + ROC) / v_i0_base
    m_req = rhs**(2.0/3.0)

    return m_req


# ------------------------------
# 3) VTOL 제약조건 메인 함수 (envelope)
# ------------------------------
def compute_vtol_lift_constraints(
    MTOW_kg,
    h_ref,
    h_ceil,
    ROC_max,
    ROC_ceil,
    A_proj,
    CD_fp=1.1,
    DL_min_grid=20.0,
    DL_max_grid=120.0,
    n_points=200,
    ctrl_margin_frac=0.2,
):
    """
    Compute required hover_thrust_margin vs disk loading for a lift-rotor VTOL.

    Returns:
        DL_grid          : [kg/m^2]
        m_req_roc_ctrl   : required margin from ROC_max (with control margin)
        m_req_ceil       : required margin from ceiling ROC
        m_envelope       : max of the two (design requirement)
    """
    DL_grid = np.linspace(DL_min_grid, DL_max_grid, n_points)

    rho_ref  = isa_density(h_ref)
    rho_ceil = isa_density(h_ceil)

    m_req_roc      = np.zeros_like(DL_grid)
    m_req_ceil     = np.zeros_like(DL_grid)
    m_req_roc_ctrl = np.zeros_like(DL_grid)

    for i, DL in enumerate(DL_grid):
        # 1) At reference altitude, ROC_max
        m_req_roc[i] = required_margin_from_DL_with_drag(
            DL_mass=DL,
            MTOW_kg=MTOW_kg,
            ROC=ROC_max,
            rho=rho_ref,
            A_proj=A_proj,
            CD_fp=CD_fp,
        )
        # Control margin at max ROC
        m_req_roc_ctrl[i] = m_req_roc[i] * (1.0 + ctrl_margin_frac)

        # 2) At ceiling altitude, ROC_ceil
        m_req_ceil[i] = required_margin_from_DL_with_drag(
            DL_mass=DL,
            MTOW_kg=MTOW_kg,
            ROC=ROC_ceil,
            rho=rho_ceil,
            A_proj=A_proj,
            CD_fp=CD_fp,
        )

    # Envelope: must satisfy both
    m_envelope = np.maximum(m_req_roc_ctrl, m_req_ceil)

    return DL_grid, m_req_roc_ctrl, m_req_ceil, m_envelope


# ------------------------------
# 4) R_max estimation from wing span
# ------------------------------
def estimate_R_max_from_span(
    wing_span,
    n_rotors_spanwise_per_side,
    span_margin_factor=0.8,
    clearance_factor=0.7,
):
    """
    Estimate maximum rotor tip radius R_max from wing span geometry.

    Assumptions:
    - On each side, n_rotors_spanwise_per_side rotors are placed along the span.
    - Usable half span = 0.5 * wing_span * span_margin_factor
      (tip/center 영역 제외)
    - Rotors are evenly spaced on that half span.
    - 2*R_max = spacing * clearance_factor

    Returns:
        R_max [m]
    """
    if n_rotors_spanwise_per_side < 2:
        raise ValueError("n_rotors_spanwise_per_side must be >= 2 to define spacing.")

    usable_half_span = 0.5 * wing_span * span_margin_factor
    spacing          = usable_half_span / (n_rotors_spanwise_per_side - 1)
    R_max            = 0.5 * spacing * clearance_factor
    return R_max


# ------------------------------
# 5) Geometry-based DL_min
# ------------------------------
def dl_min_geom(MTOW_kg, n_rotors, R_max):
    """
    Minimum disk loading from geometry (max rotor radius).
    """
    A_max = n_rotors * np.pi * R_max**2  # [m^2] total rotor area
    return MTOW_kg / A_max               # [kg/m^2]


# ------------------------------
# 6) Power-based DL_max (hover power limit)
# ------------------------------
def required_hover_power(DL_mass, MTOW_kg, rho, m_design, FM=0.7):
    """
    Required hover power [W] to sustain T = m_design * W
    at disk loading DL_mass, including induced power and FM.
    """
    g0 = 9.81
    W  = MTOW_kg * g0
    A  = MTOW_kg / DL_mass          # [m^2]
    T  = m_design * W
    v_i = np.sqrt(T/(2.0 * rho * A))
    P_i = T * v_i
    return P_i / FM                 # [W]


def dl_max_from_power(
    MTOW_kg,
    P_avail_tot,
    m_design,
    rho,
    DL_candidates,
    FM=0.7
):
    """
    Compute max DL that can hover with thrust margin m_design
    under total available power P_avail_tot.
    """
    P_req = np.array([
        required_hover_power(DL, MTOW_kg, rho, m_design, FM)
        for DL in DL_candidates
    ])
    feasible = P_req <= P_avail_tot
    if not np.any(feasible):
        return None
    return DL_candidates[feasible].max()


# ------------------------------
# 7) 최종 DL 범위 합치기
# ------------------------------
def compute_final_DL_range(
    MTOW_kg,
    n_rotors,
    R_max,
    DL_grid,
    m_env,             # from VTOL constraint (perf envelope)
    margin_max_allow,
    P_avail_tot,
    m_design,
    rho_power,
    DL_max_FM=None
):
    # (A) geometry
    DL_min_geom_val = dl_min_geom(MTOW_kg, n_rotors, R_max)

    # (B) performance + thrust margin
    feasible_perf = m_env <= margin_max_allow
    if np.any(feasible_perf):
        DL_max_perf = DL_grid[feasible_perf].max()
    else:
        DL_max_perf = None

    # (C) motor/battery power
    DL_max_power = dl_max_from_power(
        MTOW_kg=MTOW_kg,
        P_avail_tot=P_avail_tot,
        m_design=m_design,
        rho=rho_power,
        DL_candidates=DL_grid
    )

    # (D) FM limit (scalar 입력)

    # ---- 최종 범위 합치기 ----
    DL_min_final = DL_min_geom_val

    candidates_max = []
    if DL_max_perf  is not None: candidates_max.append(DL_max_perf)
    if DL_max_power is not None: candidates_max.append(DL_max_power)
    if DL_max_FM    is not None: candidates_max.append(DL_max_FM)

    if len(candidates_max) == 0:
        DL_max_final = None
    else:
        DL_max_final = min(candidates_max)

    details = {
        "DL_min_geom": DL_min_geom_val,
        "DL_max_perf": DL_max_perf,
        "DL_max_power": DL_max_power,
        "DL_max_FM": DL_max_FM,
    }

    return DL_min_final, DL_max_final, details


# ------------------------------
# 8) 최종 메인 함수
# ------------------------------
def vtol_mode_Constraints_analysis(vehicle, requirements, params, plot=True, title=None):
    """
    VTOL 모드 제약조건 해석 및 설계 공간 출력.
    plot=True 일 때:
        - constraint_plots/ 폴더에 PNG로 자동 저장 (plt.show() 호출 안 함)
    """

    # 주요 입력값(갱신 변수)
    MTOW_kg = params['initial_MTOW']
    if vehicle is not None:
        mp = getattr(vehicle, 'mass_properties', None)
        if mp is not None:
            mt = getattr(mp, 'max_takeoff', None)
            if mt is not None:
                MTOW_kg = float(mt)
    
    # 날개 투영면적
    A_proj = MTOW_kg / params['wingloading']   # 초기값
    if vehicle is not None:
        try:
            A = vehicle.wings.main_wing.areas.reference
            if A is not None:
                A_proj = float(A)
        except Exception:
            pass
    
    # 날개 종횡비
    AR = params['aspect_ratio']
    if vehicle is not None:
        try:
            AR_v = vehicle.wings.main_wing.spans.projected**2 / vehicle.wings.main_wing.areas.reference
            if AR_v is not None:
                AR = float(AR_v)
        except Exception:
            pass
    
    # 날개 스팬
    wing_span = np.sqrt(AR * A_proj)  # 초기값
    if vehicle is not None:
        try:
            ws = vehicle.wings.main_wing.spans.projected
            if ws is not None:
                wing_span = float(ws)
        except Exception:
            pass

    # n points on envelope (params 우선)
    try:
        n_points_on_curve = int(getattr(params, 'n_points_on_curve', getattr(params, 'num_of_gen_point', None)))
    except Exception:
        n_points_on_curve = None
    if n_points_on_curve is None:
        try:
            n_points_on_curve = int(params.get('n_points_on_curve', params.get('num_of_gen_point', 5)))
        except Exception:
            n_points_on_curve = 5

    # 주요 변수 출력
    if plot:
        print('\n================================================== 로터 설계 공간 ======================================================')
        print(f"VTOL Constraint Analysis Inputs: "
              f"MTOW = {MTOW_kg:.1f} kg, A_proj = {A_proj:.3f} m^2, "
              f"Wing span = {wing_span:.3f} m, AR = {AR:.3f}") 
    
    # 주요 변수(비갱신 변수)
    n_rotors = params['number_of_rotors']          # 총 로터 수
    n_rotors_spanwise_per_side = n_rotors / 4.0    # 한쪽 날개당 spanwise 로터 수 (4면체 대칭 가정)
    h_ref   = requirements['design_altitude']      # reference altitude for ROC_max
    h_ceil  = requirements['h_ceiling']            # ceiling altitude for ROC_ceil
    ROC_max = requirements['vtol_ROC_max']         # max vertical climb rate at h_ref

    # 상수/파라미터
    ROC_ceil          = 0.5                        # vertical climb rate at ceiling
    span_margin_factor= 0.7                        # 사용 가능한 span 비율
    clearance_factor  = 0.7                        # 로터 간 간격 대비 로터 직경 비율
    CD_fp             = 1.1                        # flat-plate drag coefficient
    DL_min_grid       = 20.0                       # [kg/m^2]
    DL_max_grid       = 120.0                      # [kg/m^2]
    n_points          = 200                        # grid size
    ctrl_margin_frac  = 0.1                        # control margin fraction at ROC_max
    margin_max_allow  = 2.0                        # allowed max thrust margin
    P_avail_tot       = 1.5e6                      # total available power [W]
    m_design          = 1.2                        # power sizing margin
    FM_hover          = 0.7                        # hover FM (not directly used here, but kept)
    DL_max_FM         = 65.0                       # FM 기반 DL 최대 한계선 75

    if title is None:
        title = "Constraint Diagram (Thrust MarginLift vs Rotor DL [kg/m²])"

    # 0) R_max를 span 기반으로 계산
    R_max = estimate_R_max_from_span(
        wing_span=wing_span,
        n_rotors_spanwise_per_side=n_rotors_spanwise_per_side,
        span_margin_factor=span_margin_factor,
        clearance_factor=clearance_factor,
    )

    # 1) VTOL 성능 envelope 계산
    DL_grid, m_roc_ctrl, m_ceil, m_env = compute_vtol_lift_constraints(
        MTOW_kg=MTOW_kg,
        h_ref=h_ref,
        h_ceil=h_ceil,
        ROC_max=ROC_max,
        ROC_ceil=ROC_ceil,
        A_proj=A_proj,
        CD_fp=CD_fp,
        DL_min_grid=DL_min_grid,
        DL_max_grid=DL_max_grid,
        n_points=n_points,
        ctrl_margin_frac=ctrl_margin_frac,
    )

    # 2) 최종 DL 범위 계산 (geometry + perf + power + FM)
    rho_power = isa_density(h_ref)
    DL_min_final, DL_max_final, details = compute_final_DL_range(
        MTOW_kg=MTOW_kg,
        n_rotors=n_rotors,
        R_max=R_max,
        DL_grid=DL_grid,
        m_env=m_env,
        margin_max_allow=margin_max_allow,
        P_avail_tot=P_avail_tot,
        m_design=m_design,
        rho_power=rho_power,
        DL_max_FM=DL_max_FM
    )

    # ------------------------------------------------------------------
    #  플로팅 (자동 저장 모드: plt.show() 사용 안 함)
    # ------------------------------------------------------------------
    if plot:
        fig, ax = plt.subplots(figsize=(9, 6))

        ax.plot(DL_grid, m_roc_ctrl, label="ROC_max + control margin")
        ax.plot(DL_grid, m_ceil,     label="Ceiling ROC requirement", linestyle="--")

        # 성능 + margin 허용 범위
        feasible_mask_perf = m_env <= margin_max_allow
        if np.any(feasible_mask_perf):
            ax.fill_between(
                DL_grid[feasible_mask_perf],
                m_env[feasible_mask_perf],
                margin_max_allow,
                alpha=0.15,
                label=f"Feasible regin-ROC"
            )

        # Geometry / Perf / Power / FM 한계선 표시
        DL_min_geom_val = details["DL_min_geom"]
        ax.axvline(DL_min_geom_val, color="green", linestyle=":",
                   label=f"DL_min_geom = {DL_min_geom_val:.1f}")

        if details["DL_max_power"] is not None:
            ax.axvline(details["DL_max_power"], color="red", linestyle="--",
                       label=f"DL_max_power = {details['DL_max_power']:.1f}")
        if details["DL_max_FM"] is not None:
            ax.axvline(details["DL_max_FM"], color="purple", linestyle="--",
                       label=f"DL_max_FM = {details['DL_max_FM']:.1f}")

        # 최종 설계 가능 DL 범위 음영 + 샘플 포인트
        DL_points_plot = None
        m_points_plot  = None
        if (DL_min_final is not None) and (DL_max_final is not None) and (DL_max_final > DL_min_final):
            ax.axvspan(DL_min_final, DL_max_final, alpha=0.25, color="yellow",
                       label=f"Feasible regin-DL [{DL_min_final:.1f}, {DL_max_final:.1f}] kg/m²")

            DL_points_plot = np.linspace(DL_min_final, DL_max_final, max(2, int(n_points_on_curve)))
            m_points_plot  = np.interp(DL_points_plot, DL_grid, m_env)
            ax.scatter(DL_points_plot, m_points_plot, c='red', s=40, zorder=7,
                       label=f"{len(DL_points_plot)} samples on feasible")

        ax.set_xlabel("Disk loading [kg/m²]  (MTOW / total rotor disk area)")
        ax.set_ylabel("hover_thrust_margin  (T_avail / W)")
        ax.set_title(title)
        ax.grid(True, linestyle=":")
        ax.legend(loc="best")
        plt.tight_layout()

        # ---------- 자동 저장 ----------
        save_dir = "Project_plots"
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fig_name  = f"vtol_constraint_MTOW{MTOW_kg:.0f}_ROC{ROC_max:.1f}_{timestamp}.png"
        fig_path  = os.path.join(save_dir, fig_name)

        plt.savefig(fig_path, dpi=300)
        plt.close(fig)
        print(f"[SAVED] VTOL-mode constraint plot -> {fig_path}")

    # 최종 feasible DL 범위내에서 n_points_on_curve 등간격 샘플링
    # (DL_min_final / DL_max_final이 유효하지 않으면 빈 배열 반환)
    if (DL_min_final is None) or (DL_max_final is None) or (DL_max_final <= DL_min_final):
        if plot:
            print(">>> No non-empty final DL range found under given constraints.")
        return np.empty((0, 2))

    DL_start  = DL_min_final
    DL_end    = DL_max_final
    DL_points = np.linspace(DL_start, DL_end, max(2, int(n_points_on_curve)))
    m_points  = np.interp(DL_points, DL_grid, m_env)

    points_on_env = np.column_stack((DL_points, m_points))

    # 콘솔 표 출력
    if plot:
        hdr = f"{'idx':>3s} {'DL (kg/m^2)':>14s} {'req_margin (T/W)':>18s}"
        sep = "-" * len(hdr)
        print('\n' + hdr)
        print(sep)
        for i, row in enumerate(points_on_env):
            dl, mreq = float(row[0]), float(row[1])
            print(f"{i:3d} {dl:14.3f} {mreq:18.4f}")
        print(sep + "\n")

    # 반환: (n,2) 배열: [DL (kg/m^2), required_margin (T/W)]
    return points_on_env


# ------------------------------
# 9) Example usage
# ------------------------------
if __name__ == "__main__":

    vehicle      = None
    requirements = Data()
    params       = Data()
    
    # 주요 입력값(갱신 변수)
    params.initial_MTOW   = 950.0
    params.wingloading    = 90.0
    params.aspect_ratio   = 11.4

    # 주요 변수(비갱신 변수)
    params.number_of_rotors      = 12            # 총 로터 수
    requirements.design_altitude = 300.0         # reference altitude for ROC_max
    requirements.h_ceiling       = 1000.0        # ceiling altitude for ROC_ceil
    requirements.vtol_ROC_max    = 4.0           # max vertical climb rate at h_ref
    params.n_points_on_curve     = 31

    vtol_mode_Constraints_analysis(
        vehicle,
        requirements,
        params,
        plot=True
    ) 
