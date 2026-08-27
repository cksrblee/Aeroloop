## @ingroup Methods-Optimization
# GA_Optimization.py  (fixed_mode_Constraints_analysis.py 에서 분리해도 되고, 그대로 써도 됨)

# Created:  11.18 2025, Chanyoung Joo
# Modified: 11.19 2025, GA convergence plots auto-save to Project_plots/
#           11.19 2025, best design & MTOW saved as text in Project_plots/
#           11.19 2025, multiprocessing + 진행률 출력(메인 프로세스 한 줄)
#           11.19 2025, Manager.Value 사용 시 get_lock 제거

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import SUAVE
assert SUAVE.__version__ == '2.5.2'
from SUAVE.Core                        import Data
from aeroloop.engineering.suave_evtol.Sizing.sizing_iteration import sizing_iteration

import numpy as np
from deap import base, creator, tools, algorithms
import random
import copy
import matplotlib.pyplot as plt
import os
import datetime
import multiprocessing
import threading
import time


# ----------------------------------------------------------------------
#  개별 평가 함수 (top-level 함수: 멀티프로세싱에서 pickle 가능)
# ----------------------------------------------------------------------
def evaluate_individual(individual,
                        requirements,
                        params,
                        mission_profile,
                        fixed_points,
                        vtol_points,
                        AR_list,
                        cache,
                        progress_counter=None,
                        print_each_eval=False,
                        eval_counter=None,      
                        total_evals=None,         
                        use_multiprocessing=False  
                        ):
    """
    DEAP용 평가 함수.
    individual: [i_fixed, i_vtol, i_AR]  (정수 인덱스)
    반환: (MTOW,)
    """

    # 캐시 키
    key = tuple(individual)
    if key in cache:
        # 진행률 카운터만 업데이트
        if progress_counter is not None:
            progress_counter.value += 1
        if eval_counter is not None:
            eval_counter[0] += 1
        return (cache[key],)

    N_fixed = len(fixed_points)
    N_vtol  = len(vtol_points)
    N_AR    = len(AR_list)

    # 방어적 클램핑
    i_fixed, i_vtol, i_AR = individual
    i_fixed = max(0, min(N_fixed-1, int(i_fixed)))
    i_vtol  = max(0, min(N_vtol-1,  int(i_vtol)))
    i_AR    = max(0, min(N_AR-1,    int(i_AR)))

    # decode indices -> 항상 할당 (print 블록 밖으로 이동)
    WS, TW_fixed = fixed_points[i_fixed]
    DL, TW_vtol  = vtol_points[i_vtol]
    AR           = AR_list[i_AR]

    # ------------------------------
    # progress (counting)
    # ------------------------------
    if progress_counter is not None:
        progress_counter.value += 1

    if eval_counter is not None:
        eval_counter[0] += 1

    # 싱글코어일 때만 진행률 + 설계변수 동시 출력
    if (not use_multiprocessing) and print_each_eval and (eval_counter is not None) and (total_evals is not None):
        progress = 100.0 * eval_counter[0] / float(total_evals)
        print('\n=======================================================================')
        print(f"[GA 진행률] {progress:6.2f}%  ({eval_counter[0]:4d}/{total_evals})")
        print(f" Wing 조합={i_fixed}, Rotor 조합={i_vtol}, AR={i_AR}")
        print(f"  ===> WS={WS:.2f}, T/W_fixed={TW_fixed:.3f}, "
              f"DL={DL:.2f}, T/W_vtol={TW_vtol:.3f}, AR={AR:.2f}")
        print('=======================================================================')

    # 복사본 사용
    req = copy.deepcopy(requirements)
    par = copy.deepcopy(params)

    par.wingloading         = WS
    par.prop_thrust_margin  = TW_fixed
    par.diskloading         = DL
    par.hover_thrust_margin = TW_vtol
    par.aspect_ratio        = AR

    try:
        vehicle, MTOW = sizing_iteration(req, par, mission_profile)
        fitness = MTOW
    except:
        fitness = 3000

    cache[key] = fitness
    return (fitness,)


# ----------------------------------------------------------------------
#  Toolbox 구성 함수
# ----------------------------------------------------------------------
def make_toolbox(requirements,
                 params,
                 mission_profile,
                 fixed_points,
                 vtol_points,
                 AR_list,
                 progress_counter=None,
                 print_each_eval=False,
                 eval_counter=None,       
                 total_evals=None,       
                 use_multiprocessing=False
                 ):

    # --- 문제 크기 정의 ---
    N_fixed = len(fixed_points)
    N_vtol  = len(vtol_points)
    N_AR    = len(AR_list)

    # --- Fitness / Individual 정의 ---
    try:
        creator.FitnessMin  # MTOW 최소화
    except AttributeError:
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    try:
        creator.Individual
    except AttributeError:
        creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()

    # ---- 유전자(인덱스) 생성 함수 등록 ----
    toolbox.register("attr_fixed", random.randint, 0, N_fixed-1)
    toolbox.register("attr_vtol",  random.randint, 0, N_vtol-1)
    toolbox.register("attr_AR",    random.randint, 0, N_AR-1)

    # ---- 개체: [i_fixed, i_vtol, i_AR] ----
    toolbox.register(
        "individual",
        tools.initCycle,
        creator.Individual,
        (toolbox.attr_fixed, toolbox.attr_vtol, toolbox.attr_AR),
        n=1
    )

    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    # ---- 캐시(동일 조합 재평가 방지) ----
    cache = {}

    # ---- 평가 함수 등록 (top-level evaluate_individual) ----
    toolbox.register(
        "evaluate",
        evaluate_individual,
        requirements=requirements,
        params=params,
        mission_profile=mission_profile,
        fixed_points=fixed_points,
        vtol_points=vtol_points,
        AR_list=AR_list,
        cache=cache,
        progress_counter=progress_counter,
        print_each_eval=print_each_eval,
        eval_counter=eval_counter,     
        total_evals=total_evals,         
        use_multiprocessing=use_multiprocessing  
    )

    # ---- 교차 / 변이 / 선택 ----
    toolbox.register("mate", tools.cxUniform, indpb=0.5)
    toolbox.register(
        "mutate",
        tools.mutUniformInt,
        low=[0, 0, 0],
        up=[N_fixed-1, N_vtol-1, N_AR-1],
        indpb=0.2
    )
    toolbox.register("select", tools.selTournament, tournsize=2)

    return toolbox


# ----------------------------------------------------------------------
#   GA 실행 함수
# ----------------------------------------------------------------------
def GA_Optimization(requirements,
                    params,
                    mission_profile,
                    fixed_opt_points,
                    vtol_opt_points,
                    AR_list,
                    pop_size=40,
                    n_gen=50,
                    cx_prob=0.8,
                    mut_prob=0.2,
                    use_multiprocessing=False,
                    n_processes=None,
                    use_progress=True):
    """
    GA 최적화 메인 함수.

    use_multiprocessing=True 이면 multiprocessing.Pool 사용.
    use_progress=True 이면 멀티 상황에서 진행률 한 줄로 출력.
    """

    # -----------------------------
    # 멀티프로세싱용 progress counter 준비
    # -----------------------------
    manager = None
    progress_counter = None
    eval_counter = None
    total_evals = None
    total_evals_est = pop_size * n_gen  # 대략적인 총 평가 횟수 (세대마다 pop 전체 재평가 가정)

    if use_multiprocessing:
        if n_processes is None:
            n_processes = max(1, multiprocessing.cpu_count() - 1)
        print(f"[INFO] Using multiprocessing with {n_processes} processes")

        manager = multiprocessing.Manager()
        progress_counter = manager.Value('i', 0)   # 정수 공유 변수 (ValueProxy)
    else:
        eval_counter = [0]            
        total_evals = pop_size * n_gen 
        progress_counter = None

    # -----------------------------
    # Toolbox 생성
    # -----------------------------
    toolbox = make_toolbox(
            requirements, params, mission_profile,
            fixed_opt_points, vtol_opt_points, AR_list,
            progress_counter=progress_counter,
            print_each_eval=(not use_multiprocessing),
            eval_counter=eval_counter,         
            total_evals=total_evals,           
            use_multiprocessing=use_multiprocessing
    )

    # -----------------------------
    # Pool 등록 (멀티일 경우)
    # -----------------------------
    pool = None
    if use_multiprocessing:
        pool = multiprocessing.Pool(processes=n_processes)
        toolbox.register("map", pool.map)

    # -----------------------------
    # 진행률 출력 스레드
    # -----------------------------
    progress_thread = None
    stop_event = threading.Event()

    def progress_printer():
        last = -1
        while not stop_event.is_set():
            if progress_counter is not None:
                count = progress_counter.value
            else:
                count = 0

            if total_evals_est > 0:
                percent = 100.0 * count / float(total_evals_est)
                if count != last:
                    print(f"[GA Progress] {count}/{total_evals_est} ({percent:5.1f}%)", end="\r", flush=True)
                    last = count
            time.sleep(0.5)

        # 종료 시 최종 한 줄 출력
        if total_evals_est > 0:
            if progress_counter is not None:
                count = progress_counter.value
            else:
                count = total_evals_est
            percent = 100.0 * count / float(total_evals_est)
            print(f"\n[GA Progress] {count}/{total_evals_est} ({percent:5.1f}%) - finished")

    if use_multiprocessing and use_progress:
        progress_thread = threading.Thread(target=progress_printer, daemon=True)
        progress_thread.start()

    # -----------------------------
    # GA 실행
    # -----------------------------
    pop = toolbox.population(n=pop_size)
    hof = tools.HallOfFame(1)

    stats = tools.Statistics(lambda ind: ind.fitness.values[0])
    stats.register("avg", np.mean)
    stats.register("min", np.min)
    stats.register("max", np.max)

    pop, logbook = algorithms.eaSimple(
        pop,
        toolbox,
        cxpb=cx_prob,
        mutpb=mut_prob,
        ngen=n_gen,
        stats=stats,
        halloffame=hof,
        verbose=True
    )

    # 진행률 스레드 종료
    if progress_thread is not None:
        stop_event.set()
        progress_thread.join(timeout=2.0)

    # Pool 정리
    if pool is not None:
        pool.close()
        pool.join()

    # ------------------------------------------------------------------
    #   수렴 그래프 저장 (Project_plots 폴더)
    # ------------------------------------------------------------------
    gens     = logbook.select("gen")
    min_fits = logbook.select("min")   # 세대별 best MTOW
    avg_fits = logbook.select("avg")   # 세대별 평균 MTOW

    save_dir  = "Project_plots"
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1) MTOW convergence
    plt.figure()
    plt.plot(gens, min_fits, marker='o', linestyle='-', label="Best MTOW")
    plt.plot(gens, avg_fits, marker='x', linestyle='--', label="Average MTOW")
    plt.xlabel("Generation")
    plt.ylabel("MTOW [kg]")
    plt.title("GA Convergence (MTOW)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    fname_conv = f"GA_MTOW_convergence_{timestamp}.png"
    fpath_conv = os.path.join(save_dir, fname_conv)
    plt.savefig(fpath_conv, dpi=300)
    plt.close()
    print(f"[SAVED] GA convergence plot -> {fpath_conv}")

    # 2) Residual (Best - Global Best)
    global_best = min(min_fits)
    residuals   = [m - global_best for m in min_fits]

    plt.figure()
    plt.plot(gens, residuals, marker='o', linestyle='-')
    plt.xlabel("Generation")
    plt.ylabel("Residual Best MTOW [kg]")
    plt.title("GA Residual Convergence (Best - Global Best)")
    plt.grid(True)
    plt.tight_layout()

    fname_res = f"GA_MTOW_residuals_{timestamp}.png"
    fpath_res = os.path.join(save_dir, fname_res)
    plt.savefig(fpath_res, dpi=300)
    plt.close()
    print(f"[SAVED] GA residual plot -> {fpath_res}")

    # ------------------------------------------------------------------
    #   최적 개체 정리
    # ------------------------------------------------------------------
    best_ind  = hof[0]
    best_MTOW = best_ind.fitness.values[0]

    print(f"\n########################### Best individual (indices) = {best_ind} ###########################")
    print(f"################################ Best MTOW = {best_MTOW:.3f} kg ###############################")

    print('\n=================================================== 최종 설계 변수 적용 사이징 ==================================================')

    i_fixed, i_vtol, i_AR = best_ind

    WS, TW_fixed = fixed_opt_points[i_fixed]
    DL, TW_vtol  = vtol_opt_points[i_vtol]
    AR           = AR_list[i_AR]

    final_req = copy.deepcopy(requirements)
    final_par = copy.deepcopy(params)

    final_par.wingloading         = WS
    final_par.prop_thrust_margin  = TW_fixed
    final_par.diskloading         = DL
    final_par.hover_thrust_margin = TW_vtol
    final_par.aspect_ratio        = AR

    best_vehicle, best_MTOW_refined = sizing_iteration(final_req, final_par, mission_profile)

    # ------------------------------------------------------------------
    #   결과 텍스트 저장
    # ------------------------------------------------------------------
    txt_name = f"GA_best_design_{timestamp}.txt"
    txt_path = os.path.join(save_dir, txt_name)

    with open(txt_path, "w") as f:
        f.write("GA Optimization Result - Best Design\n")
        f.write("====================================\n\n")
        f.write(f"Timestamp           : {timestamp}\n\n")
        f.write(f"Population size     : {pop_size}\n")
        f.write(f"Number of generations: {n_gen}\n")
        f.write(f"Crossover prob      : {cx_prob}\n")
        f.write(f"Mutation prob       : {mut_prob}\n")
        f.write(f"use_multiprocessing : {use_multiprocessing}\n")
        if use_multiprocessing:
            f.write(f"n_processes         : {n_processes}\n")
        f.write("\n")

        f.write("Best individual (indices)\n")
        f.write(f"  i_fixed           : {int(i_fixed)}\n")
        f.write(f"  i_vtol            : {int(i_vtol)}\n")
        f.write(f"  i_AR              : {int(i_AR)}\n\n")

        f.write("Best design variables (decoded)\n")
        f.write(f"  Wing loading W/S [kg/m^2]     : {WS:.6f}\n")
        f.write(f"  T/W_fixed (prop_thrust_margin): {TW_fixed:.6f}\n")
        f.write(f"  Disk loading DL [kg/m^2]      : {DL:.6f}\n")
        f.write(f"  T/W_vtol (hover_thrust_margin): {TW_vtol:.6f}\n")
        f.write(f"  Aspect ratio AR               : {AR:.6f}\n\n")

        f.write("MTOW results\n")
        f.write(f"  GA best fitness MTOW [kg]     : {best_MTOW:.6f}\n")
        f.write(f"  Refined MTOW [kg]             : {best_MTOW_refined:.6f}\n")

    print(f"[SAVED] GA best design summary -> {txt_path}")

    return best_vehicle, best_MTOW_refined, {
        "indices": (int(i_fixed), int(i_vtol), int(i_AR)),
        "WS": float(WS),
        "TW_fixed": float(TW_fixed),
        "DL": float(DL),
        "TW_vtol": float(TW_vtol),
        "AR": float(AR)
    }
