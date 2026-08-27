## @ingroup Methods-Sizing
# sizing_iteration.py 

# Created:  11.18 2025, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import SUAVE
assert SUAVE.__version__=='2.5.2'
# 필수 라이브러리
from pathlib                                                    import Path
from SUAVE.Core                                                 import Data        # 단위 지정     
from SUAVE.Input_Output.OpenVSP                                 import write       # OpenVSP로 기체 정의 정보 저장
from aeroloop.engineering.suave_evtol.Weights.Buildups.eVTOL.converge_evtol_weight import converge_evtol_weight  # eVTOL 기체 중량 수렴
# 사이징 함수
from aeroloop.engineering.suave_evtol.Sizing.sizing_fuselage                       import sizing_fuselage
from aeroloop.engineering.suave_evtol.Sizing.sizing_main_wing                      import sizing_main_wing
from aeroloop.engineering.suave_evtol.Sizing.sizing_lift_rotor                     import sizing_lift_rotor
from aeroloop.engineering.suave_evtol.Sizing.sizing_thrust_prop                    import sizing_thrust_prop
from aeroloop.engineering.suave_evtol.Sizing.sizing_motors                         import sizing_motors
from aeroloop.engineering.suave_evtol.Sizing.sizing_stabilizer                     import sizing_stabilizer
from aeroloop.engineering.suave_evtol.Sizing.sizing_boom                           import sizing_boom
from aeroloop.engineering.suave_evtol.Sizing.sizing_battery                        import sizing_battery
from aeroloop.engineering.suave_evtol.Vehicles.setup_vehicle                       import setup_vehicle
# 미션 에너지 산출
from aeroloop.engineering.suave_evtol.Missions.evaluate_mission_energy_quick       import evaluate_mission_energy_quick


# ======================================================================
#  sizing_iteration.py
# ======================================================================
def sizing_iteration(requirements, params, mission_profile):
    """
    1. 임무 요구도, 미션 프로파일 엑셀로 불러오기(이런식으로 => requirements = SUAVE.Input_Output.Excel.Excel_Reader('Project_file/evtol_sizing_requirements_v0.0.1.xlsx'))
    2. 초기 설계 파라미터, 사이징 파라미터 정의
    3. 컴퍼넌트 사이징
    4. 기체 정의
    5. 해석 정의
    6. 미션 해석(1번에서 불러온 임무 프로파일 기반)
    7. 배터리 사이징(미션 요구 에너지 기반)
    8. 컴퍼넌트 중량 추정 및 MTOW 수렴
    9. 새 MTOW 와 2번에서 입력된 MTOW 비교하여 오차 5kg 이상이면 2번부터 다시 반복(새 MTOW 반영)
    """

    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)
            
    # ----------------------------------------------------------------------------------------------------------------------
    #   반복계산 루프
    # ----------------------------------------------------------------------------------------------------------------------  
    # 기록용 히스토리
    history = []

    # vehicle 초기화 (첫 회전은 None 전달)
    vehicle = None

    for it in range(1, params.MAX_ITERS + 1):
        _log(f"\n=================================================== MTOW Iteration {it} ===================================================")

        # ----------------------------- Component Sizing -----------------------------
        fuselage_design = sizing_fuselage(requirements, params)
        main_wing       = sizing_main_wing(params, fuselage_design, vehicle)
        lift_rotor      = sizing_lift_rotor(requirements, params, main_wing, fuselage_design, vehicle)
        thrust_prop     = sizing_thrust_prop(requirements, params, main_wing, fuselage_design, vehicle)
        motors          = sizing_motors(params, lift_rotor, thrust_prop)
        stabilizer      = sizing_stabilizer(params, main_wing, lift_rotor, fuselage_design)
        booms           = sizing_boom(params, main_wing, stabilizer, lift_rotor)

        # ------------------------------- Setup Vehicle ------------------------------
        vehicle = setup_vehicle(requirements, params,
                                fuselage_design, main_wing,
                                lift_rotor, thrust_prop,
                                motors, stabilizer, booms,
                                vehicle)
        
        
        # OpenVSP로 기체 정의 정보 저장
        # write(vehicle, f"Chanyoung_evtol_Iter_{it}")

        # setup_vehicle 직후 값
        bat_before = vehicle.networks.lift_cruise.battery.mass_properties.mass
        mtow_before = vehicle.mass_properties.max_takeoff


        # 기하 기록
        span_m = getattr(main_wing, 'spans', getattr(main_wing, 'span', 0.0))
        rotor_Dm = 0.0
        if isinstance(lift_rotor, (list, tuple)) and len(lift_rotor) > 0:
            rotor_Dm = 2.0 * getattr(lift_rotor[0], 'tip_radius', 0.0)

        # -------------------------------- Analyses/Mission --------------------------
        mission_results = evaluate_mission_energy_quick(params, vehicle, requirements, mission_profile)
        
        # -------------------------------- Battery Sizing ----------------------------
        vehicle = sizing_battery(params, vehicle, mission_results)
        bat_after = vehicle.networks.lift_cruise.battery.mass_properties.mass

        # -------------------------- Component Mass Estimation -----------------------
        vehicle = converge_evtol_weight(params, vehicle,
                                        print_iterations           = False,
                                        contingency_factor         = 1.1,
                                        speed_of_sound             = 340.294,
                                        max_tip_mach               = 0.65,
                                        disk_area_factor           = 1.15,
                                        safety_factor              = 1.5,
                                        max_thrust_to_weight_ratio = 1.1,
                                        max_g_load                 = 3.8,
                                        motor_efficiency           = 0.85 * 0.98,
                                        per_passenger_baggage_kg    = 15.0)

        mtow_after = vehicle.mass_properties.max_takeoff
             

        # ------------------------------ 기록 & 수렴 체크 ----------------------------
        history.append(dict(
            iter=it,
            bat_before=bat_before,
            bat_after=bat_after,
            mtow_before=mtow_before,
            mtow_after=mtow_after,
            span=span_m,
            rotorD=rotor_Dm,
        ))

        d_bat  = abs(bat_after  - bat_before)
        d_mtow = abs(mtow_after - mtow_before)
        _log(f"[check] ΔBattery = {d_bat:.2f} kg (tol {params.BAT_TOL_KG} kg), "
             f"ΔMTOW = {d_mtow:.2f} kg (tol {params.MTOW_TOL_KG} kg)")

        if (d_bat <= params.BAT_TOL_KG) and (d_mtow <= params.MTOW_TOL_KG):
            _log("✅ Converged by tolerances. Stop iterations.")
            break
        

    # ===============================================
    # 리포트 출력
    # ===============================================
    _log("\n================= Iteration Report (battery mass, MTOW, span, rotor D) ==================")
    hdr = f"{'it':>3} | {'Bat_before[kg]':>13} {'Bat_after[kg]':>13} | {'MTOW_before[kg]':>15} {'MTOW_after[kg]':>14} | {'Span[m]':>8} {'RotorD[m]':>9}"
    _log(hdr)
    _log("-"*len(hdr))
    for row in history:
        _log(f"{row['iter']:3d} | "
             f"{row['bat_before']:13.2f} {row['bat_after']:13.2f} | "
             f"{row['mtow_before']:15.2f} {row['mtow_after']:14.2f} | "
             f"{row['span']:8.3f} {row['rotorD']:9.3f}")
        
    return vehicle, mtow_after