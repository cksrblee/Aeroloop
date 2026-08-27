# # @ingroup Methods-Sizing
# # sizing_battery.py

# # Created: 2025-09-11 Chanyoung
# # Modified: 


# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import SUAVE
import numpy as np
from SUAVE.Core import Data, Units
from SUAVE.Methods.Power.Battery.Sizing      import initialize_from_energy_and_power

def sizing_battery(params, vehicle, mission_results, *, verbose=True):
    """
    미션 결과(세그먼트별 시간·전력)를 이용해 필요한 배터리 에너지[J]와 피크 전력[W]를 계산,
    SUAVE의 initialize_from_energy_and_power()로 배터리 팩을 사이징한 뒤 vehicle에 반영.

    Parameters
    ----------
    params : object-like
        - battery_energy_margin_frac (optional, float) : 에너지 마진(예: 0.1 → +10%)
        - battery_power_margin_frac  (optional, float) : 전력   마진(예: 0.1 → +10%)
    vehicle : SUAVE vehicle
        - vehicle.networks 내 battery 객체를 찾아 갱신
    mission_results : SUAVE.Core.Data
        - mission quick 해석 결과. 예:
          results.segments[i].conditions.frames.inertial.time -> [s0, s1, ...]
          results.segments[i].conditions.propulsion.battery_power_draw -> [W0, W1, ...]

    Returns
    -------
    vehicle : 업데이트된 vehicle
    out     : Data
        .energy_req_J      : 마진 적용 전/후 요구 에너지
        .power_peak_W      : 마진 적용 전/후 피크 전력
        .battery_mass_kg   : 결과 질량
        .battery_energy_J  : 결과 팩 에너지
        .battery_power_W   : 결과 팩 최대전력
    """
    
    # 로깅 헬퍼: params.Log_print이 True이고 verbose가 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True) and verbose:
            print(*args, **kwargs)
    
    # ------------------------------ 설정값 읽기 ------------------------------
    energy_margin = float(getattr(params, 'battery_energy_margin_frac', 1.10))
    power_margin  = float(getattr(params,  'battery_power_margin_frac', 1.10))


    # ------------------------------ 미션 적분 ------------------------------
    E_pos_J = 0.0   # 방전 에너지 적분
    P_peaks = []    # 각 세그먼트 피크 전력(양수 기준)

    for seg in getattr(mission_results, 'segments', []):
        tag = seg.get('tag', 'seg')

        # 시간/전력 벡터 가져오기
        try:
            t = np.asarray(seg['conditions']['frames']['inertial']['time'], dtype=float)
            P = np.asarray(seg['conditions']['propulsion']['battery_power_draw'], dtype=float)
        except Exception:
            _log(f"[sizing_battery][WARN] '{tag}' 세그먼트: time/P 배열을 찾지 못해 스킵.")
            continue

        if t.size < 2 or P.size != t.size:
            _log(f"[sizing_battery][WARN] '{tag}' 세그먼트: time/Power 길이 부적합 → 스킵.")
            continue

        # 전력 
        P = np.maximum(P, 0.0)
        
        # 에너지 적분(J)
        E_pos = float(np.trapz(P, t))

        E_pos_J += E_pos


        # 피크 전력(양수만)
        P_peak = float(np.max(P)) if P.size else 0.0
        P_peaks.append(P_peak)


    if not P_peaks:
        raise RuntimeError("[sizing_battery] 유효한 세그먼트가 없습니다(피크 전력 계산 실패).")
    

    # 실사용 요구 에너지 = 방전 적분
    E_req_J_base = max(E_pos_J, 0.0)
    P_peak_W_base = max(P_peaks)
    

    # 마진 적용
    E_req_J = E_req_J_base * energy_margin
    P_req_W = P_peak_W_base * power_margin
    


    # ------------------------------ 배터리 사이징 ------------------------------
    # 베터리 객체 호출
    bat = getattr(getattr(getattr(vehicle, 'networks', None), 'lift_cruise', None), 'battery', None)
    
    # 에너지 기반 배터리 사이징
    bat.specific_energy = 300.0 * Units.Wh / Units.kg    # 배터리 에너지 밀도 (논문값)
    bat.specific_power  = 2400.0 * Units.W / Units.kg   # 배터리 파워 밀도 (논문값) ======= SUAVE 내부 오류 수정
    initialize_from_energy_and_power(bat, E_req_J, P_req_W, max='hard')  

    # vehicle에 배터리 갱신
    vehicle.networks.lift_cruise.battery = bat

    # 결과 패키징
    out = Data()
    out.energy_req_J_base   = E_req_J_base
    out.energy_req_J_final  = E_req_J
    out.power_peak_W_base   = P_peak_W_base
    out.power_peak_W_final  = P_req_W
    out.battery_mass_kg     = float(getattr(bat.mass_properties, 'mass', 0.0))
    out.battery_energy_J    = float(getattr(bat, 'max_energy', 0.0))
    out.battery_power_W     = float(getattr(bat, 'max_power', 0.0))
    out.battery_ref         = bat

    if verbose:
        _log("\n[sizing_battery] === Mission Energy/Power Summary & Battery Pack Sized ===")
        _log(f"  E_pos_total      = {E_pos_J/1e6:9.2f} MJ")
        _log(f"  E_req_final      = {E_req_J/1e6:9.2f} MJ")
        _log(f"  P_peak_base      = {P_peak_W_base/1e3:9.2f} kW")
        _log(f"  P_req_final      = {P_req_W/1e3:9.2f} kW")
        _log(f"  mass             = {out.battery_mass_kg:9.3f} kg")
        _log(f"  max_energy       = {out.battery_energy_J/3.6e6:9.3f} kWh")
        _log(f"  max_power        = {out.battery_power_W/1e3:9.3f} kW\n")


    return vehicle