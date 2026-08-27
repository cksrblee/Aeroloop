"""
역할 요약
이 코드는 eVTOL(전기 수직이착륙기) 항공기의 최대이륙중량(MTOW)을 빌드업(각 부품별 중량 합산) 중량과 일치하도록 반복적으로 조정(수렴)시키는 함수입니다.
SUAVE의 중량 해석 파이프라인에서 MTOW와 실제 부품 중량의 합이 일치하도록 자동으로 맞춰주는 핵심 루틴입니다.

인풋
vehicle: SUAVE Vehicle 객체 (MTOW, 각 부품 정보 포함)
print_iterations: 수렴 과정의 diff(차이) 출력 여부 (기본 False)
contingency_factor, speed_of_sound, max_tip_mach, disk_area_factor, safety_factor, max_thrust_to_weight_ratio, max_g_load, motor_efficiency:
중량 해석에 필요한 각종 설계 파라미터(기본값 제공)

아웃풋
True/False:
수렴 성공 시 True
100회 반복에도 수렴 실패 시 False
(수렴 성공 시) vehicle.mass_properties.max_takeoff가 빌드업 중량과 일치

방법론
초기 빌드업 중량 계산:
empty() 함수로 각 부품별 중량을 모두 합산한 빌드업 중량 계산
반복 수렴 루프:
MTOW와 빌드업 중량의 차이(diff)가 1kg 이하가 될 때까지
MTOW를 MTOW - diff로 갱신
다시 empty()로 빌드업 중량 재계산
반복 횟수 100회 제한
수렴 결과 출력:
수렴 성공 시 최종 MTOW 출력
실패 시 경고 메시지 출력

특성
MTOW와 실제 부품 중량의 합이 일치하도록 자동 수렴
MTOW가 바뀔 때마다 empty()로 각 부품 중량을 최신값으로 재계산
eVTOL, 멀티콥터 등 다양한 전기항공기 설계에 활용 가능
SUAVE 중량 해석 파이프라인에서 반복적으로 호출되어 설계 변수 변화에 따라 MTOW를 자동으로 맞춤

주요 기능
함수명: converge_evtol_weight
목적: eVTOL 항공기의 각 부품별 중량을 모두 합산(빌드업)한 값과현재 설정된 MTOW가 일치하도록
MTOW 값을 반복적으로 조정(수렴)합니다.

동작 원리
- 초기값 설정
입력된 vehicle 객체의 mass_properties.max_takeoff(MTOW)와 빌드업(각 부품별 중량 합산) 결과의 차이(diff)를 계산
- 반복 수렴 루프
두 값의 차이가 1kg 이하가 될 때까지 MTOW 값을 MTOW - diff로 갱신, 매 반복마다 empty() 함수를 호출해
빌드업 중량을 다시 계산 수렴 실패 방지
100회 반복해도 수렴하지 않으면 실패 메시지 출력 후 False 반환
수렴 성공 시 최종적으로 수렴된 MTOW를 출력하고 True 반환

사용 목적
eVTOL 설계/사이징 과정에서 각 부품별 중량 공식(배터리, 동체, 로터, 모터 등)을 모두 더한 값과
전체 MTOW가 일치하도록 자동으로 맞추기 위해 사용
최적화/사이징 루프에서 반복적으로 호출하여 설계 변수 변화에 따라 MTOW를 자동으로 맞출 수 있음

요약
eVTOL의 MTOW(최대이륙중량)를 빌드업 중량과 일치하도록 반복적으로 조정(수렴)하는 함수
SUAVE의 eVTOL 중량 해석 파이프라인에서 핵심적으로 사용됨
즉, 이 코드는 eVTOL 항공기 설계에서 실제 부품 중량의 합과 MTOW가 일치하도록 자동으로 맞춰주는 수렴 루틴입니다.
1. 변화하는 값
vehicle.mass_properties.max_takeoff (MTOW)
루프를 돌 때마다 vehicle.mass_properties.max_takeoff 값이 갱신(업데이트)됩니다.
이 값이 바로 "최대이륙중량(MTOW)"입니다.
2. 루프 내 동작
현재 MTOW와 빌드업 중량의 차이(diff) 계산
diff = vehicle.mass_properties.max_takeoff - build_up_mass
MTOW 갱신
vehicle.mass_properties.max_takeoff = vehicle.mass_properties.max_takeoff - diff
즉, MTOW를 빌드업 중량에 맞춰 한 번에 이동시킴
empty() 함수로 빌드업 중량 재계산
empty() 함수는 vehicle 객체의 최신 MTOW 값을 사용해서
각 부품(배터리, 동체, 로터, 모터 등)의 중량을 다시 계산합니다.
예를 들어, 배터리 중량, 로터 중량 등은 MTOW에 따라 달라질 수 있습니다.
빌드업 중량(build_up_mass)과 MTOW의 차이가 1kg 이하가 될 때까지 반복
3. 결론
MTOW가 바뀌면, 각 부품(컴포넌트) 중량 공식도 그 값을 사용해 다시 계산됩니다.
즉, MTOW → 컴포넌트 중량 → 빌드업 중량 → MTOW
이런 식으로 값이 계속 상호작용하며 수렴합니다.
최종적으로 MTOW와 실제 빌드업 중량이 일치하도록 반복해서 맞추는 구조입니다.
정리:
루프를 도는 동안

vehicle.mass_properties.max_takeoff(MTOW)가 계속 갱신되고,
이 값이 다시 각 컴포넌트(배터리, 동체, 로터 등) 중량 산출에 반영되어
전체 빌드업 중량이 다시 계산됩니다.
"""
## @ingroup Methods-Weights-Buildups-eVTOL
# converge_evtol_weight.py

# Created: Aug 2022, M. Clarke

#-------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------- 
from aeroloop.engineering.suave_evtol.Weights.Buildups.eVTOL.empty import empty
from SUAVE.Core import Data

#-------------------------------------------------------------------------------
# Empty
#-------------------------------------------------------------------------------

## @ingroup Methods-Weights-Buildups-eVTOL 
def converge_evtol_weight(params, vehicle,
                          print_iterations              = False,
                          contingency_factor            = 1.1,
                          speed_of_sound                = 340.294,
                          max_tip_mach                  = 0.65,
                          disk_area_factor              = 1.15,
                          safety_factor                 = 1.5,
                          max_thrust_to_weight_ratio    = 1.1,
                          max_g_load                    = 3.8,
                          motor_efficiency              = 0.85 * 0.98,
                          per_passenger_baggage_kg     = 15.0):
    '''Converges the maximum takeoff weight of an aircraft using the eVTOL 
    weight buildup routine.'''
    # 로깅 헬퍼: params가 주어지면 params.Log_print에 따라 출력, params가 None이면 기존처럼 출력
    def _log(*args, **kwargs):
        if params is None:
            print(*args, **kwargs)
        else:
            if getattr(params, 'Log_print', True):
                print(*args, **kwargs)

    settings       = Data()
    breakdown      = empty(vehicle,settings,contingency_factor,
                           speed_of_sound,max_tip_mach,disk_area_factor,
                           safety_factor,max_thrust_to_weight_ratio,
                           max_g_load,motor_efficiency,
                           per_passenger_baggage_kg) 
    build_up_mass  = breakdown.total    
    diff           = vehicle.mass_properties.max_takeoff - build_up_mass
    iterations     = 0
    
    while(abs(diff)>1):
        vehicle.mass_properties.max_takeoff = vehicle.mass_properties.max_takeoff - diff
        
        # Note that 'diff' will be negative if buildup mass is larger than MTOW, so subtractive
        # iteration always moves MTOW toward buildup mass
        
        breakdown      = empty(vehicle,settings,contingency_factor,
                           speed_of_sound,max_tip_mach,disk_area_factor,
                           safety_factor,max_thrust_to_weight_ratio,
                           max_g_load,motor_efficiency)
        build_up_mass  = breakdown.total    
        diff           = vehicle.mass_properties.max_takeoff - build_up_mass 
        iterations     += 1
        if print_iterations:
            _log(round(diff,3))
        if iterations == 100:
            _log('Weight convergence failed!')
            return False 
        
    _log('++++++++++++++++++++++++++++++  Mass Estimation  ++++++++++++++++++++++++++++++')
    _log('Converged MTOW = ' + str(round(vehicle.mass_properties.max_takeoff)) + ' kg')
    _log('  Empty Weight = ' + str(round(breakdown.empty)) + ' kg')
    _log('  Structural Weight = ' + str(round(breakdown.structural)) + ' kg')
    _log('  Propulsion System Weight = ' + str(round(breakdown.battery+breakdown.motors+breakdown.ECS+breakdown.wiring)) + ' kg')
    _log('  Payload Weight = ' + str(round(breakdown.passengers+breakdown.payload)) + ' kg')
    _log()     
    _log('  Wing+Booms = ' + str(round(breakdown.total_wing_weight+breakdown.booms)) + ' kg')
    _log('  Fuselage Weight = ' + str(round(breakdown.fuselage)) + ' kg')
    _log('  Motor system Weight = ' + str(round(breakdown.motors+breakdown.ECS+breakdown.wiring)) + ' kg')
    _log('  Battery Weight = ' + str(round(breakdown.battery)) + ' kg')
    _log('  Rotor/Propeller Weight = ' + str(round(breakdown.propellers+breakdown.lift_rotors+breakdown.hubs)) + ' kg')
    _log('  System/Equipment Weight = ' + str(round(breakdown.BRS+breakdown.avionics)) + ' kg')
    _log('  Landing Gear Weight = ' + str(round(breakdown.landing_gear)) + ' kg')
    _log()    
    _log('  Passenger Weight = ' + str(round(breakdown.passengers)) + ' kg')
    _log('  Baggage Weight = ' + str(round(breakdown.payload)) + ' kg')
    _log('  Seats Weight = ' + str(round(breakdown.seats)) + ' kg')
    _log('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
    
    return vehicle
