## @ingroup Methods-Optimization
# fixed_mode_Constraints_analysis.py 

# Created:  11.18 2025, Chanyoung Joo
# Modified: 11.19 2025, auto-save plots added (no blocking GUI)

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import os
import datetime
import numpy as np
import matplotlib.pyplot as plt
from SUAVE.Core import Data

# ======================================================================
# fixed_mode_Constraints_analysis.py
#  - 고정 모드 제약조건 해석 및 플롯 생성
# ======================================================================


# Atmosphere model (ISA simplified)
def isa_density(h):
    T0 = 288.15
    p0 = 101325
    L  = 0.0065
    R  = 287.058
    g  = 9.80665

    if h < 0:
        h = 0.0

    T = T0 - L*h
    p = p0 * (T/T0)**(g/(R*L))
    rho = p / (R*T)
    return rho


# Aerodynamics
def k_factor(e, AR):
    return 1.0/(np.pi*e*AR)


# Basic constraint functions
def q_dyn(rho, V):
    return 0.5*rho*V**2


# Cruise T/W
def TW_cruise(WS_N, V, rho, CD0, k):
    q = q_dyn(rho, V)
    return q*CD0/WS_N + k*WS_N/q


# Climb optimum speed
def V_RoC(WS_N, rho, CD0, k):
    return np.sqrt(2.0*WS_N/rho) * (k/(3.0*CD0))**0.25


# Rate of Climb T/W
def TW_climb(WS_N, ROC, rho, CD0, k):
    Vroc = V_RoC(WS_N, rho, CD0, k)
    q    = q_dyn(rho, Vroc)
    TW = (ROC/Vroc) + q*CD0/WS_N + k*WS_N/q
    TW_m = TW * 1.1  # 마진 계수 (임시)
    
    return TW_m


# Stall Wing Loading (N/m²)
def WS_stall(Vstall, rho, CLmax):
    return 0.5*rho*Vstall**2 * CLmax


# Wrapper (WS in kg/m²)
def compute_constraints(
    V_cruise, ROC, V_stall,
    h_cruise, h_ceiling,
    CL_max, CD0, AR, e,
    WS_min_factor=0.1, WS_max_factor=1.1,
    n_points=300):

    # Air densities
    rho_cruise  = isa_density(h_cruise)
    rho_ceiling = isa_density(h_ceiling)
    rho_SL      = isa_density(0.0)
    g0          = 9.80665
    k           = k_factor(e, AR)

    # stall limit in N/m²
    WS_stall_N = WS_stall(V_stall, rho_SL, CL_max)

    # convert to kg/m²
    WS_stall_kg = WS_stall_N / g0

    # range of wing loading (kg/m²)
    WS_kg = np.linspace(WS_min_factor*WS_stall_kg,
                        WS_max_factor*WS_stall_kg,
                        n_points)
    WS_N  = WS_kg * g0

    # Cruise
    TWc = TW_cruise(WS_N, V_cruise, rho_cruise, CD0, k)

    # Climb
    TWcl = TW_climb(WS_N, ROC, rho_cruise, CD0, k)

    # Ceiling (R/C = 0.5 m/s)
    TWceil = TW_climb(WS_N, 0.5, rho_ceiling, CD0, k)

    return WS_kg, TWc, TWcl, TWceil, WS_stall_kg


# --------------------------------------
# fixed_mode_Constraints_analysis 메인 함수
# --------------------------------------
def fixed_mode_Constraints_analysis(vehicle, requirements, params, plot=True):
    """
    고정익 모드 제약조건 해석 및 설계 공간 출력.
    plot=True 일 때:
        - constraint_plots/ 폴더에 PNG로 자동 저장 (plt.show() 호출 안 함)
    """

    # 주요변수 (AR)
    AR = params['aspect_ratio']
    if vehicle is not None:
        try:
            AR_v = vehicle.wings.main_wing.spans.projected**2 / vehicle.wings.main_wing.areas.reference
            if AR_v is not None:
                AR = float(AR_v)
        except Exception:
            pass

    # 주요 입력값
    V_cruise          = params['V_cruise_mps']
    e                 = params['oswald_e']
    n_points_on_curve = params['num_of_gen_point']
    V_stall           = requirements['V_stall']
    h_cruise          = requirements['design_altitude']
    h_ceiling         = requirements['h_ceiling']
    ROC               = requirements['fixed_ROC_max']
    ws_lower_bound    = params['WS_lower_bound']

    # 공력계수 (임시/기본값)
    CL_max = 1.61
    CD0    = 0.0452

    # 제약조건 해석
    WS_kg, TWc, TWcl, TWceil, WS_stall_kg = compute_constraints(
        V_cruise, ROC, V_stall, h_cruise, h_ceiling,
        CL_max, CD0, AR, e
    )

    # 저장: 전체 곡선(그래프용)
    WS_full    = WS_kg.copy()
    TWc_full   = TWc.copy()
    TWcl_full  = TWcl.copy()
    TWceil_full= TWceil.copy()

    # WS_lower_bound 처리
    try:
        ws_lb = float(ws_lower_bound) if ws_lower_bound is not None else None
    except Exception:
        ws_lb = None
    if ws_lb is None:
        try:
            ws_lb = float(getattr(params, 'WS_lower_bound', None))
        except Exception:
            try:
                ws_lb = float(params.get('WS_lower_bound', None))
            except Exception:
                ws_lb = None

    if (ws_lb is not None) and (ws_lb > WS_full.max()):
        if plot:
            print(f"Warning: specified WS lower bound {ws_lb:.3f} > max WS grid {WS_full.max():.3f}. No feasible points.")

    # 상승/크루즈 추중비 비율
    ratio = TWcl / TWc   # shape: (n_points,)

    # -----------------------------
    # 교차점 및 등간격 점 계산용 함수
    # -----------------------------
    def find_curve_intersection(x, y1, y2):
        d = y1 - y2
        idx = np.where(np.sign(d[:-1]) * np.sign(d[1:]) < 0)[0]
        if idx.size == 0:
            return None  # 교차 없음
        i  = idx[0]
        x0, x1 = x[i], x[i+1]
        d0, d1 = d[i], d[i+1]
        t = -d0 / (d1 - d0)
        x_int = x0 + t * (x1 - x0)
        y_int = np.interp(x_int, x, y1)
        return x_int, y_int

    # 전체 곡선에서의 교차점(그래프용)
    cross_cruise_climb = find_curve_intersection(WS_full, TWc_full, TWcl_full)

    # Climb vs Stall vertical (x = WS_stall_kg) 교차
    if WS_full.min() <= WS_stall_kg <= WS_full.max():
        cross_climb_stall = (WS_stall_kg, float(np.interp(WS_stall_kg, WS_full, TWcl_full)))
    else:
        cross_climb_stall = None

    # --- feasible 영역 마스크 (그래프/샘플링용) ---
    TW_min_full = np.maximum.reduce([TWc_full, TWcl_full, TWceil_full])
    mask_shade  = np.ones_like(WS_full, dtype=bool)

    if ws_lb is not None:
        mask_shade &= (WS_full >= ws_lb)
    mask_shade &= (WS_full <= WS_stall_kg)

    feasible_exists_for_plot = np.any(mask_shade)

    # --- 샘플링: feasible 영역에서 n_points_on_curve 개 등간격 WS 선택 ---
    if feasible_exists_for_plot:
        WS_available = WS_full[mask_shade]
        if WS_available.size < 2:
            if plot:
                print("Feasible WS range has less than 2 points. Returning empty.")
            return np.empty((0, 2))
        WS_points    = np.linspace(WS_available.min(), WS_available.max(), int(max(2, n_points_on_curve)))
        TW_points    = np.interp(WS_points, WS_full, TWcl_full)
        ratio_points = np.interp(WS_points, WS_full, (TWcl_full / TWc_full))
        fixed_opt_points = np.column_stack((WS_points, ratio_points))
    else:
        if plot:
            print("No feasible WS range found after applying WS_lower_bound / stall limit.")
        return np.empty((0, 2))

    # ------------------------------------------------------------------
    #  플로팅 (자동 저장 모드: plt.show() 사용 안 함)
    # ------------------------------------------------------------------
    if plot:
        fig, ax = plt.subplots(figsize=(8, 6))

        # 곡선들
        ax.plot(WS_full, TWc_full,   label="Cruise")
        ax.plot(WS_full, TWcl_full,  label=f"Climb ROC={ROC} m/s")
        ax.plot(WS_full, TWceil_full,"--", label="Ceiling ROC=0.5 m/s")

        # Stall vertical line
        ax.axvline(WS_stall_kg, color='k', linestyle=':', label="Stall limit")

        # WS lower bound 선 (설정되어 있으면 한 번만 그림)
        if ws_lb is not None:
            ax.axvline(ws_lb, color='gray', linestyle='--', lw=1.2,
                       label=f"WS lower bound = {ws_lb:.1f}")

        # 샘플링 포인트
        ax.scatter(WS_points, TW_points, c='red', s=40, zorder=7,
                   label=f"{len(WS_points)} samples on feasible")

        # 교차점 표시
        if cross_cruise_climb is not None:
            ax.plot(cross_cruise_climb[0], cross_cruise_climb[1],
                    'ko', ms=6, label="Cruise∩Climb")
        if cross_climb_stall is not None:
            ax.plot(cross_climb_stall[0], cross_climb_stall[1],
                    'ks', ms=6, label="Climb∩Stall")

        # Feasible region 음영
        if feasible_exists_for_plot:
            curve_max = max(TWc_full.max(), TWcl_full.max(), TWceil_full.max())
            top_y     = max(TW_min_full[mask_shade].max() * 1.05, curve_max * 1.05)
            ax.fill_between(
                WS_full[mask_shade],
                TW_min_full[mask_shade],
                top_y,
                alpha=0.15,
                label="Feasible region"
            )
            ymin, ymax = ax.get_ylim()
            if top_y > ymax:
                ax.set_ylim(ymin, top_y)

        ax.set_xlabel("Wing Loading W/S [kg/m²]")
        ax.set_ylabel("Thrust-to-Weight T/W [-]")
        ax.grid(True, linestyle=":")
        ax.legend(loc="lower left")
        ax.set_title("Constraint Diagram (T/W vs W/S [kg/m²])")

        # 위쪽 x축: 상승/크루즈 추중비 비율
        ax_top = ax.twiny()
        x_max  = max(WS_kg.max(), WS_stall_kg) * 1.02
        ax.set_xlim(0.0, x_max)
        ax_top.set_xlim(0.0, x_max)

        n_ticks   = 6
        ws_ticks  = np.linspace(0.0, x_max, n_ticks)
        ratio_ticks = np.interp(ws_ticks, WS_kg, ratio,
                                left=ratio[0], right=ratio[-1])

        ax_top.set_xticks(ws_ticks)
        ax_top.set_xticklabels([f"{r:.2f}x" for r in ratio_ticks])
        ax_top.set_xlabel("T/W_climb / T/W_cruise ratio")

        fig.tight_layout()

        # ---------- 여기서 자동 저장 ----------
        save_dir = "Project_plots"
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fig_name  = f"fixed_constraint_AR{AR:.1f}_V{V_cruise:.0f}_ROC{ROC:.1f}_{timestamp}.png"
        fig_path  = os.path.join(save_dir, fig_name)

        plt.savefig(fig_path, dpi=300)
        plt.close(fig)
        print(f"[SAVED] Fixed-mode constraint plot -> {fig_path}")

    # 후보점 표 출력
    if plot:
        hdr = f"{'idx':>3s} {'W/S (kg/m^2)':>14s} {'T/W_climb / T/W_cruise':>24s}"
        sep = "-" * len(hdr)
        print('\n================================================== 날개 설계 공간 ======================================================')
        print(f"Fixed Constraint Analysis Inputs: "
              f"V_cruise = {V_cruise:.1f} m/s, ROC = {ROC:.1f} m/s, "
              f"V_stall = {V_stall:.1f} m/s, h_cruise = {h_cruise:.1f} m")
        print("\n" + hdr)
        print(sep)
        for i, row in enumerate(fixed_opt_points):
            ws, ratio_p = float(row[0]), float(row[1])
            print(f"{i:2d} {ws:14.3f} {ratio_p:24.4f}")
        print(sep + "\n")

    # 반환: (n,2) 배열: [W/S (kg/m²), T/W_climb/T/W_cruise]
    return fixed_opt_points


# --------------------------------------
# test
# --------------------------------------
if __name__ == "__main__":

    vehicle = None
    requirements = Data()
    params = Data()

    params.V_cruise_mps      = 50.0
    requirements.fixed_ROC_max   = 5.0
    requirements.V_stall         = 30.0
    requirements.design_altitude = 300.0
    requirements.h_ceiling       = 3000.0
    params.aspect_ratio          = 11.0
    params.oswald_e              = 0.8
    params.num_of_gen_point      = 5
    params.WS_lower_bound        = 60.0

    fixed_opt_points = fixed_mode_Constraints_analysis(
        vehicle, requirements, params, plot=True
    )
