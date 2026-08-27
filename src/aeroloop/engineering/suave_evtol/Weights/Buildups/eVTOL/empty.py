"""
역할 요약
이 코드는 eVTOL(전기 수직이착륙기) 항공기의 빈 중량(empty weight)과 주요 부품별 중량을 계산하는 함수입니다.
동체, 날개, 로터, 모터, 배터리, 랜딩기어, 전장품 등 모든 주요 부품의 중량을 경험식과 공식에 따라 산출하여
전체 빈 중량 및 계층별 중량을 반환합니다.

인풋
config: SUAVE Vehicle Configuration 객체 (항공기 전체 설계 정보)
settings: 추가 설정값
contingency_factor: 불확실성 보정 계수 (기본 1.1)
speed_of_sound: 음속 (기본 340.294 m/s)
max_tip_mach: 허용 팁 마하수 (기본 0.65)
disk_area_factor: 디스크 면적 효율 역수 (기본 1.15)
safety_factor: 설계 안전 계수 (기본 1.5)
max_thrust_to_weight_ratio: 최대 추력/중량비 (기본 1.1)
max_g_load: 최대 g-load (기본 3.8)
motor_efficiency: 모터 효율 (기본 0.833)

아웃풋
output:
SUAVE Data 객체로,
각 부품별 중량(동체, 날개, 로터, 모터, 배터리, 랜딩기어, 전장품 등)
계층별 중량(구조, 빈 중량, 총 중량 등)
구조: output.fuselage, output.wings, output.lift_rotors, output.propellers, output.battery, output.motors, output.servos, output.hubs, output.BRS, output.landing_gear, output.wiring, output.structural, output.empty, output.total 등

방법론
고정 중량 계산: 좌석, 승객, 항공전자, 랜딩기어, 환경제어장치 등
네트워크(추진계통)별 중량 계산:
배터리, 페이로드, 항공전자, 서보, 허브, BRS(비상 낙하산) 등
로터/프로펠러/모터 중량은 각각의 경험식 함수(prop, wiring 등)로 계산
날개, 배선 중량 계산: 각 날개별로 중량과 배선 중량을 계산
랜딩기어, 동체 중량 계산: 랜딩기어, 동체(경험식) 중량 산출
전체 구조 중량, 빈 중량, 총 중량 합산:
구조 중량, 빈 중량(empty), 총 중량(total) 등 계층적으로 합산
출력:
각 부품별, 계층별 중량이 담긴 Data 객체 반환

특성
경험식과 구조역학 공식을 조합하여 실제 설계에 가까운 중량 산출
fuselage.py, prop.py, wing.py, wiring.py 등 외부 모듈의 함수들을 호출해 각 부품별 중량 계산
eVTOL, 멀티콥터 등 다양한 전기항공기 설계에 활용 가능
SUAVE 중량 해석 파이프라인에서 빈 중량 및 부품별 중량 계산의 핵심 함수로 사용
MTOW 수렴 루프(converge_evtol_weight) 등에서 반복적으로 호출되어 설계 변수 변화에 따라 중량을 자동으로 갱신

주요 기능
함수명: empty
목적:
eVTOL 항공기의 각 부품(동체, 날개, 로터, 모터, 배터리, 랜딩기어, 전장품 등)의 중량을
다양한 경험식과 공식(프로젝트 Vahana, Raymer 등)에 따라 계산하여
전체 빈 중량(empty weight)과 주요 부품별 중량을 산출합니다.
동작 과정 요약
입력값 준비

config: 항공기(또는 설정) 객체
여러 설계 상수(여유계수, 최대 마하, 추력/중량비 등)
고정 중량 계산

좌석, 승객, 항공전자, 랜딩기어, 환경제어장치 등
네트워크(추진계통)별 중량 계산

배터리, 페이로드, 항공전자, 서보, 허브, BRS(비상 낙하산) 등
로터/프로펠러/모터 중량은 각각의 경험식 함수(prop, wiring 등)로 계산
날개, 배선 중량 계산

각 날개별로 중량과 배선 중량을 계산
랜딩기어, 동체 중량 계산

랜딩기어, 동체(경험식) 중량 산출
전체 구조 중량, 빈 중량, 총 중량 합산

구조 중량, 빈 중량(empty), 총 중량(total) 등 계층적으로 합산
출력

각 부품별, 계층별 중량이 담긴 Data 객체 반환
요약
eVTOL 항공기의 빈 중량(empty weight)과 부품별 중량을 계산하는 함수
각 부품별로 경험식/공식 기반 중량 산출
결과는 Data 객체로 반환되어, 전체 중량 해석 및 MTOW 수렴 루프 등에 사용됨
즉, 이 코드는 SUAVE에서 eVTOL 항공기 중량 해석의 핵심 역할을 하는
빈 중량 및 부품별 중량 계산 함수입니다.

정리:
fuselage.py, prop.py, wing.py, wiring.py는
이 코드에서 각 부품별 중량을 계산할 때
함수로 import해서 실제로 호출해 사용하는 모듈입니다.

중량 계산 정리
prop, wing, wiring, fuselage 등은 각각
prop.py, wing.py, wiring.py, fuselage.py의 함수를 호출하여
실제 중량을 계산합니다.
배터리, 모터, 페이로드 등은
네트워크 객체의 mass_properties.mass 값을 읽어와 사용합니다.
**기타(좌석, 승객, 랜딩기어, BRS 등)**은
경험식 또는 상수 곱셈으로 empty.py 내부에서 직접 계산합니다.
structural, empty, total 등은
위에서 계산된 각 요소를 합산하여 계층적으로 산출합니다.
즉, empty.py는 직접 계산(상수 곱셈),
외부 함수 호출(prop, wing, wiring, fuselage),
네트워크/컴포넌트의 mass 속성 읽기
이 세 가지 방식으로 모든 중량 요소를 계산합니다.
"""
## @ingroup Methods-Weights-Buildups-eVTOL
# empty.py
#
# Created:    Apr, 2019, J. Smart
# Modified:   July, 2021, R. Erhard

#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------
import SUAVE
from SUAVE.Core import Units, Data

from SUAVE.Methods.Weights.Buildups.Common.fuselage import fuselage
from SUAVE.Methods.Weights.Buildups.Common.prop import prop
from SUAVE.Methods.Weights.Buildups.Common.wiring import wiring
from SUAVE.Methods.Weights.Buildups.Common.wing import wing
from SUAVE.Components.Energy.Converters import Propeller, Lift_Rotor
from SUAVE.Components.Energy.Networks import Battery_Propeller
from SUAVE.Components.Energy.Networks import Lift_Cruise

import numpy as np
import math

#-------------------------------------------------------------------------------
# Empty
#-------------------------------------------------------------------------------

## @ingroup Methods-Weights-Buildups-eVTOL

def empty(config,
          settings,
          contingency_factor            = 1.1,
          speed_of_sound                = 340.294,
          max_tip_mach                  = 0.65,
          disk_area_factor              = 1.15,
          safety_factor                 = 1.5,
          max_thrust_to_weight_ratio    = 1.1,
          max_g_load                    = 3.8,
          motor_efficiency              = 0.85 * 0.98,
          per_passenger_baggage_kg       = 10.0):

    """ Calculates the empty vehicle mass for an EVTOL-type aircraft including seats,
        avionics, servomotors, ballistic recovery system, rotor and hub assembly,
        transmission, and landing gear. Incorporates the results of the following
        common-use buildups:

            fuselage.py
            prop.py
            wing.py
            wiring.py

        Sources:
        Project Vahana Conceptual Trade Study
        https://github.com/VahanaOpenSource


        Inputs: 
            config:                     SUAVE Config Data Stucture
            contingency_factor          Factor capturing uncertainty in vehicle weight [Unitless]
            speed_of_sound:             Local Speed of Sound                           [m/s]
            max_tip_mach:               Allowable Tip Mach Number                      [Unitless]
            disk_area_factor:           Inverse of Disk Area Efficiency                [Unitless]
            max_thrust_to_weight_ratio: Allowable Thrust to Weight Ratio               [Unitless]
            safety_factor               Safety Factor in vehicle design                [Unitless]
            max_g_load                  Maximum g-forces load for certification        [UNitless]
            motor_efficiency:           Motor Efficiency                               [Unitless]

        Outputs: 
            outputs:                    Data Dictionary of Component Masses [kg]

        Output data dictionary has the following book-keeping hierarchical structure:

            Output
                Total.
                    Empty.
                        Structural.
                            Fuselage
                            Wings
                            Landing Gear
                            Rotors
                            Hubs
                        Seats
                        Battery
                        Motors
                        Servo
                    Systems.
                        Avionics
                        ECS               - Environmental Control System
                        BRS               - Ballistic Recovery System
                        Wiring            - Aircraft Electronic Wiring
                    Payload

    """

    # Set up data structures for SUAVE weight methods
    output                   = Data()
    output.lift_rotors       = 0.0
    output.propellers        = 0.0
    output.lift_rotor_motors = 0.0
    output.propeller_motors  = 0.0
    output.battery           = 0.0
    output.payload           = 0.0
    output.servos            = 0.0
    output.hubs              = 0.0
    output.BRS               = 0.0

    config.payload.passengers                      = SUAVE.Components.Physical_Component()
    config.payload.baggage                         = SUAVE.Components.Physical_Component()
    config.payload.cargo                           = SUAVE.Components.Physical_Component()
    control_systems                                = SUAVE.Components.Physical_Component()
    electrical_systems                             = SUAVE.Components.Physical_Component()
    furnishings                                    = SUAVE.Components.Physical_Component()
    air_conditioner                                = SUAVE.Components.Physical_Component()
    fuel                                           = SUAVE.Components.Physical_Component()
    apu                                            = SUAVE.Components.Physical_Component()
    hydraulics                                     = SUAVE.Components.Physical_Component()
    avionics                                       = SUAVE.Components.Energy.Peripherals.Avionics()
    optionals                                      = SUAVE.Components.Physical_Component()

    # assign components to vehicle
    config.systems.control_systems                 = control_systems
    config.systems.electrical_systems              = electrical_systems
    config.systems.avionics                        = avionics
    config.systems.furnishings                     = furnishings
    config.systems.air_conditioner                 = air_conditioner
    config.systems.fuel                            = fuel
    config.systems.apu                             = apu
    config.systems.hydraulics                      = hydraulics
    config.systems.optionals                       = optionals


    #-------------------------------------------------------------------------------
    # Fixed Weights
    #-------------------------------------------------------------------------------
    MTOW                = config.mass_properties.max_takeoff
    output.seats        = config.passengers * 15.   * Units.kg
    output.passengers   = config.passengers * 80.   * Units.kg
    output.avionics     = 15.                       * Units.kg
    output.landing_gear = MTOW * 0.02               * Units.kg
    output.ECS          = config.passengers * 7.    * Units.kg

    # Inputs and other constants
    tipMach        = max_tip_mach
    k              = disk_area_factor
    ToverW         = max_thrust_to_weight_ratio
    eta            = motor_efficiency
    rho_ref        = 1.225
    maxVTip        = speed_of_sound * tipMach         # Prop Tip Velocity
    maxLift        = MTOW * ToverW * 9.81             # Maximum Thrust
    AvgBladeCD     = 0.012                            # Average Blade CD

    # Select a length scale depending on what kind of vehicle this is
    length_scale = 1.
    nose_length  = 0.

    # Check if there is a fuselage
    C =  SUAVE.Components
    if len(config.fuselages) == 0.:
        for w  in config.wings:
            if isinstance(w ,C.Wings.Main_Wing):
                b = w.chords.root
                if b>length_scale:
                    length_scale = b
                    nose_length  = 0.25*b
    else:
        for fuse in config.fuselages:
            nose   = fuse.lengths.nose
            length = fuse.lengths.total
            if length > length_scale:
                length_scale = length
                nose_length  = nose

    #-------------------------------------------------------------------------------
    # Environmental Control System
    #-------------------------------------------------------------------------------
    config.systems.air_conditioner.origin[0][0]          = 0.51 * length_scale
    config.systems.air_conditioner.mass_properties.mass  = output.ECS

    #-------------------------------------------------------------------------------
    # Network Weight
    #-------------------------------------------------------------------------------
    for network in config.networks:

        #-------------------------------------------------------------------------------
        # Battery Weight
        #-------------------------------------------------------------------------------
        network.battery.origin[0][0]                                   = 0.51 * length_scale
        network.battery.mass_properties.center_of_gravity[0][0]        = 0.0
        output.battery                                                += network.battery.mass_properties.mass * Units.kg

        #-------------------------------------------------------------------------------
        # Payload Weight
        #-------------------------------------------------------------------------------
        network.payload.origin[0][0]                                   = 0.51 * length_scale
        network.payload.mass_properties.center_of_gravity[0][0]        = 0.0
        output.payload                                                += ((network.payload.mass_properties.mass) + (config.passengers * per_passenger_baggage_kg)) * Units.kg

        #-------------------------------------------------------------------------------
        # Avionics Weight
        #-------------------------------------------------------------------------------
        network.avionics.origin[0][0]                                  = 0.4 * nose_length
        network.avionics.mass_properties.center_of_gravity[0][0]       = 0.0
        network.avionics.mass_properties.mass                          = output.avionics


        #-------------------------------------------------------------------------------
        # Servo, Hub and BRS Weights
        #-------------------------------------------------------------------------------

        lift_rotor_hub_weight   = 4.   * Units.kg
        prop_hub_weight         = MTOW * 0.04  * Units.kg

        lift_rotor_BRS_weight   = 16.  * Units.kg



        #-------------------------------------------------------------------------------
        # Rotor, Propeller, parameters for sizing
        #-------------------------------------------------------------------------------
        if isinstance(network, Lift_Cruise):
            # Total number of rotors and propellers
            nLiftRotors   = network.number_of_lift_rotor_engines
            nThrustProps  = network.number_of_propeller_engines
            props         = network.propellers
            rots          = network.lift_rotors
            prop_motors   = network.propeller_motors
            rot_motors    = network.lift_rotor_motors

        elif isinstance(network, Battery_Propeller): 
            props         = network.propellers 
            prop_motors   = network.propeller_motors          
            nThrustProps  = 0  
            nLiftRotors   = 0    
            nProps        = 0 
            for rot_idx in range(len(props.keys())):               
                if type(props[list(props.keys())[rot_idx]]) == Propeller: 
                    props          = network.propellers
                    nThrustProps  +=1
    
                elif type(props[list(props.keys())[rot_idx]]) == Lift_Rotor:    
                    nLiftRotors   +=1  
                    
            if (nThrustProps == 0) and (nLiftRotors != 0):
                network.lift_rotors           = network.propellers
                rot_motors                    = network.propeller_motors  
                network.identical_lift_rotors = network.number_of_propeller_engines
        else:
            raise NotImplementedError("""eVTOL weight buildup only supports the Battery Propeller and Lift Cruise energy networks.\n
            Weight buildup will not return information on propulsion system.""",RuntimeWarning)

        
        nProps  = int(nLiftRotors + nThrustProps)  
        if nProps > 1:
            prop_BRS_weight     = 16.   * Units.kg
        else:
            prop_BRS_weight     = 0.   * Units.kg

        prop_servo_weight  = 0.0

        if nThrustProps > 0: 
            for idx, propeller in enumerate(network.propellers):
                proprotor    = propeller
                propmotor    = prop_motors[list(prop_motors.keys())[idx]]
                rTip_ref     = proprotor.tip_radius
                bladeSol_ref = proprotor.blade_solidity

                if proprotor.variable_pitch:
                    prop_servo_weight  = 5.2  * Units.kg

                # Compute and add propeller weights
                propeller_mass                 = prop(proprotor, maxLift/5.) * Units.kg
                output.propellers             += propeller_mass
                output.propeller_motors       += propmotor.mass_properties.mass
                proprotor.mass_properties.mass = propeller_mass + prop_hub_weight + prop_servo_weight

        lift_rotor_servo_weight = 0.0
        if nLiftRotors > 0: 
            for idx, lift_rotor in enumerate(network.lift_rotors):
                liftrotor    = lift_rotor
                liftmotor    = rot_motors[list(rot_motors.keys())[idx]]
                rTip_ref     = liftrotor.tip_radius
                bladeSol_ref = liftrotor.blade_solidity


                if liftrotor.variable_pitch:
                    lift_rotor_servo_weight = 0.65 * Units.kg

                # Compute and add lift_rotor weights
                lift_rotor_mass                = prop(liftrotor, maxLift / max(nLiftRotors - 1, 1))  * Units.kg
                output.lift_rotors            += lift_rotor_mass
                output.lift_rotor_motors      += liftmotor.mass_properties.mass
                liftrotor.mass_properties.mass = lift_rotor_mass + lift_rotor_hub_weight + lift_rotor_servo_weight

        # Add associated weights
        output.servos += (nLiftRotors * lift_rotor_servo_weight + nThrustProps * prop_servo_weight)
        output.hubs   += (nLiftRotors * lift_rotor_hub_weight + nThrustProps * prop_hub_weight)
        output.BRS    += (prop_BRS_weight + lift_rotor_BRS_weight)

        maxLiftPower   = 1.15*maxLift*(k*np.sqrt(maxLift/(2*rho_ref*np.pi*rTip_ref**2)) +
                                           bladeSol_ref*AvgBladeCD/8*maxVTip**3/(maxLift/(rho_ref*np.pi*rTip_ref**2)))
        # Tail Rotor
        if nLiftRotors == 1: # this assumes that the vehicle is an electric helicopter with a tail rotor
            
            maxLiftOmega   = maxVTip/rTip_ref
            maxLiftTorque  = maxLiftPower / maxLiftOmega

            tailrotor = next(iter(network.lift_rotors))
            output.tail_rotor   = prop(tailrotor, 1.5*maxLiftTorque/(1.25*rTip_ref))*0.2 * Units.kg
            output.lift_rotors += output.tail_rotor

    # sum motor weight
    output.motors = output.lift_rotor_motors + output.propeller_motors

    #-------------------------------------------------------------------------------
    # Wing and Motor Wiring Weight
    #-------------------------------------------------------------------------------
    total_wing_weight   = 0.0
    total_wiring_weight = 0.0
    output.wings        = Data()
    output.wiring       = Data()

    for w in config.wings:
        if w.symbolic:
            wing_weight = 0
        else:
            wing_weight            = wing(w, config, maxLift/5, safety_factor= safety_factor, max_g_load =  max_g_load )
            wing_tag               = w.tag
            output.wings[wing_tag] = wing_weight
            w.mass_properties.mass = wing_weight

        total_wing_weight    = total_wing_weight + wing_weight

        # wiring weight
        wiring_weight        = wiring(w, config, maxLiftPower/(eta*nProps)) * Units.kg
        total_wiring_weight  = total_wiring_weight + wiring_weight

    output.wiring            = total_wiring_weight
    output.total_wing_weight = total_wing_weight

    #-------------------------------------------------------------------------------
    # Landing Gear Weight
    #-------------------------------------------------------------------------------
    if not hasattr(config.landing_gear, 'nose'):
        config.landing_gear.nose       = SUAVE.Components.Landing_Gear.Nose_Landing_Gear()
    config.landing_gear.nose.mass      = 0.0
    if not hasattr(config.landing_gear, 'main'):
        config.landing_gear.main       = SUAVE.Components.Landing_Gear.Main_Landing_Gear()
    config.landing_gear.main.mass      = output.landing_gear

    #-------------------------------------------------------------------------------
    # Fuselage  Weight
    #-------------------------------------------------------------------------------
    output.fuselage = fuselage(config) * Units.kg
    config.fuselages.fuselage.mass_properties.center_of_gravity[0][0] = .45*config.fuselages.fuselage.lengths.total
    config.fuselages.fuselage.mass_properties.mass                    =  output.fuselage + output.passengers + output.seats +\
                                                                         output.wiring + output.BRS
                                                                         
    #-------------------------------------------------------------------------------
    # Boom (auxiliary tubular spars)
    #-------------------------------------------------------------------------------
    output.booms = 0.0

    # 재료/두께/피팅 계수(원하면 settings에서 가져오고, 없으면 기본값 사용)
    rho_mat = getattr(settings, 'boom_material_density', 1600.0)      # [kg/m^3] CFRP 대략
    t_wall  = getattr(settings, 'boom_wall_thickness_m', 0.002)      # [m] 2.5 mm
    k_fit   = getattr(settings, 'boom_fittings_factor', 1.15)         # 조인트/브래킷 가산

    # config.fuselages 안에 'fuselage'(메인) 외 나머지 Fuselage를 모두 붐으로 간주
    def _iter_booms(cfg):
        # 다양한 컨테이너 형태 지원
        fs = getattr(cfg, 'fuselages', None)
        if fs is None:
            return []
        items = []
        # Data/dict/list 모두 대응
        try:
            # dict 스타일
            if isinstance(fs, dict):
                items = list(fs.values())
            # 리스트 스타일
            elif isinstance(fs, (list, tuple)):
                items = list(fs)
            else:
                # Data: 속성 중 Fuselage만 뽑기
                for name in dir(fs):
                    if name.startswith('_'): 
                        continue
                    v = getattr(fs, name, None)
                    if getattr(v, '__class__', type(None)).__name__.endswith('Fuselage'):
                        items.append(v)
        except Exception:
            pass
        # 메인 동체(tag=='fuselage') 제외
        return [f for f in items if getattr(f, 'tag', '') != 'fuselage']

    for boom in _iter_booms(config):
        # 지름/길이 취득 (sizing_boom.py에서 width/heights/effective_diameter 채워둠)
        d = float(getattr(boom, 'effective_diameter', 
                 getattr(boom, 'width', getattr(getattr(boom, 'heights', object()), 'maximum', 0.12))))
        L = float(getattr(getattr(boom, 'lengths', object()), 'total', 0.0))
        if d <= 0.0 or L <= 0.0:
            continue

        r_o = 0.5 * d
        r_i = max(r_o - t_wall, 0.0)
        # 튜브 체적(원통벽) + 피팅 가산
        vol  = math.pi * (r_o*r_o - r_i*r_i) * L
        m    = rho_mat * vol * k_fit

        output.booms += m

        # 컴포넌트에도 기록(후속 CG 합산 등을 위해)
        try:
            boom.mass_properties.mass = m
            if hasattr(boom, 'origin') and boom.origin and len(boom.origin[0]) >= 3:
                x0, y0, z0 = float(boom.origin[0][0]), float(boom.origin[0][1]), float(boom.origin[0][2])
                boom.mass_properties.center_of_gravity = [[x0 + 0.5*L, y0, z0]]
        except Exception:
            pass


    #-------------------------------------------------------------------------------
    # Pack Up Outputs
    #-------------------------------------------------------------------------------
    output.structural = (output.lift_rotors + output.propellers + output.hubs +
                         output.fuselage + output.booms + output.landing_gear +
                         output.total_wing_weight) * Units.kg

    output.empty      = (contingency_factor * (output.structural + output.seats + output.avionics +output.ECS +\
                        output.motors + output.servos + output.wiring + output.BRS) + output.battery) *Units.kg

    output.total      = output.empty + output.payload + output.passengers
    

    return output
