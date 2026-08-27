## @ingroup Methods
# setup_vehicle.py 

# Created:  09.11 2025, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import SUAVE
import numpy as np
from SUAVE.Core                                                 import Units, Data
from SUAVE.Methods.Geometry.Two_Dimensional.Planform            import segment_properties, wing_segmented_planform, wing_planform  # 날개 단면적, 날개 분할, 날개 형상 정의
from SUAVE.Components.Wings                                     import Horizontal_Tail, Vertical_Tail
from SUAVE.Methods.Power.Battery.Sizing                         import initialize_from_mass 
from SUAVE.Components.Airfoils import Airfoil


def setup_vehicle(requirements, params, fuselage_design, main_wing, lift_rotor, thrust_prop, motors, stabilizer, booms, vehicle):

    # ------------------------------------------------------------------
    #   이전 루프에서 정의된 vehicle 내 값 추출
    # ------------------------------------------------------------------  
    # 질량
    max_takeoff_mass = None
    payload_mass = None
    oe_mass = None
    existing_bat = None

    if vehicle is not None:
        mp = getattr(vehicle, 'mass_properties', None)
        if mp is not None:
            max_takeoff_mass = getattr(mp, 'max_takeoff', None)
            payload_mass     = getattr(mp, 'max_payload', None)
            oe_mass          = getattr(mp, 'operating_empty', None)

        # 배터리: vehicle.networks.lift_cruise.battery 우선 탐색
        nets = getattr(vehicle, 'networks', None)
        if nets is not None:
            lc = getattr(nets, 'lift_cruise', None)
            if lc is not None and hasattr(lc, 'battery'):
                existing_bat = lc.battery
    
    
    # ------------------------------------------------------------------
    #   Initialize the Vehicle
    # ------------------------------------------------------------------    
    # Create a vehicle and set level properties
    vehicle               = SUAVE.Vehicle()
    vehicle.tag           = 'eVTOL'
    
    
    # ------------------------------------------------------------------
    #   Vehicle-level Properties
    # ------------------------------------------------------------------
    # mass properties  (Vehicle.py 클래스 안에 값 할당)
    mtow_prev = max_takeoff_mass
    vehicle.mass_properties.max_takeoff = mtow_prev or float(params.initial_MTOW)
    vehicle.mass_properties.takeoff     = vehicle.mass_properties.max_takeoff  # 동기화!
    vehicle.mass_properties.max_payload = payload_mass or float(requirements.payload)
    vehicle.mass_properties.operating_empty = (oe_mass if oe_mass is not None
                                               else vehicle.mass_properties.max_takeoff - float(requirements.payload))
    
    vehicle.mass_properties.center_of_gravity = [[main_wing.MAC_25_x,   0.  ,  0. ]]     # [m] 무게중심 위치 (x, y, z)

    # basic parameters
    vehicle.envelope.ultimate_load = requirements.ultimate_load     # 궁극 하중
    vehicle.envelope.limit_load    = requirements.limit_load        # 제한 하중
    
    # 탑승객 및 화물 정의
    vehicle.passengers             = int(getattr(requirements, 'number_of_seats', 0))     # 탑승객 수


    # ---------------------------------------------------------------
    # FUSELAGE
    # ---------------------------------------------------------------
    # FUSELAGE PROPERTIES  
    fuselage               = SUAVE.Components.Fuselages.Fuselage()   # 동체 컴퍼넌트 생성
    fuselage.tag           = 'fuselage'    
    fuselage.seats_abreast = float(fuselage_design.seats_abreast)
    
    # 동체 길이
    fuselage.lengths.total = fuselage_design.lengths.total
    fuselage.lengths.nose  = fuselage_design.lengths.nose
    fuselage.lengths.cabin = fuselage_design.lengths.cabin
    fuselage.lengths.tail  = fuselage_design.lengths.tail
    
    # 동체 너비
    fuselage.width                   = fuselage_design.width
    fuselage.heights = Data()
    fuselage.heights.maximum         = fuselage_design.heights.maximum
    fuselage.heights.at_quarter_length          = 0.80 * fuselage_design.heights.maximum
    fuselage.heights.at_wing_root_quarter_chord = 1.00 * fuselage_design.heights.maximum
    fuselage.heights.at_three_quarters_length   = 0.92 * fuselage_design.heights.maximum
    
    # 동체 높이
    fuselage.areas = Data()
    fuselage.areas.front_projected = fuselage_design.areas.front_projected
    fuselage.areas.wetted          = fuselage_design.areas.wetted
    
    
    # 동체 단면적
    fuselage.effective_diameter     = fuselage_design.effective_diameter
    fuselage.differential_pressure  = fuselage_design.differential_pressure
    
    # 피네스(길이/직경)
    fuselage.fineness = Data()
    fuselage.fineness.nose = fuselage_design.fineness.nose
    fuselage.fineness.tail = fuselage_design.fineness.tail
    
    # 세그먼트 추가
    for i, segd in enumerate(fuselage_design.segments):
        segment = SUAVE.Components.Lofted_Body_Segment.Segment()
        segment.tag                = f'segment_{i}'
        segment.percent_x_location = segd.percent_x_location
        segment.percent_z_location = segd.percent_z_location
        segment.height             = segd.height
        segment.width              = segd.width
        fuselage.Segments.append(segment)
    vehicle.append_component(fuselage)  


    
    # ------------------------------------------------------------------
    # MAIN WINGS
    # ------------------------------------------------------------------ 
    from SUAVE.Core import Units
    from SUAVE.Methods.Geometry.Two_Dimensional.Planform import segment_properties, wing_segmented_planform

    wing                           = SUAVE.Components.Wings.Main_Wing()
    wing.tag                       = 'main_wing'
    wing.symmetric                 = True

    # 기본 형상
    wing.spans.projected           = float(main_wing.spans) * Units.meter
    wing.chords.root               = float(main_wing.root_chord) * Units.meter
    wing.chords.tip                = float(main_wing.tip_chord) * Units.meter
    wing.chords.MAC                = float(main_wing.MAC) * Units.meter
    wing.thickness_to_chord        = float(params.wing_thickness_to_chord)
    

    # 에어포일 지정
    af = Airfoil()
    af.coordinate_file = main_wing.airfoil_geom
    af.polar_files     = main_wing.airfoil_polars

    # 배치
    wing.origin                    = main_wing.origin                       # [[x,y,z]], m 단위
    wing.exposed_root_chord_offset = float(main_wing.exposed_root_chord_offset)

    # ---------------- Segments ----------------
    # Root
    seg_root                          = SUAVE.Components.Wings.Segment()
    seg_root.tag                      = 'Root'
    seg_root.percent_span_location    = 0.0
    seg_root.twist                    = float(main_wing.twists.root)        # [rad]
    seg_root.root_chord_percent       = 1.0
    seg_root.dihedral_outboard        = 0.0 * Units.degrees
    seg_root.sweeps.quarter_chord     = 0.0 * Units.degrees
    seg_root.thickness_to_chord       = float(params.wing_thickness_to_chord)
    seg_root.airfoil_type             = params.wing_airfoil

    wing.Segments.append(seg_root) 

    # Tip
    seg_tip                           = SUAVE.Components.Wings.Segment()
    seg_tip.tag                       = 'Tip'
    seg_tip.percent_span_location     = 1.0
    seg_tip.twist                     = float(main_wing.twists.tip)         # [rad]
    seg_tip.root_chord_percent        = float(params.taper)                 # tip/root
    seg_tip.dihedral_outboard         = 0.0 * Units.degrees
    seg_tip.sweeps.quarter_chord      = 0.0 * Units.degrees
    seg_tip.thickness_to_chord        = float(params.wing_thickness_to_chord)
    seg_tip.airfoil_type              = params.wing_airfoil
    
    seg_tip.append_airfoil(af)

    wing.Segments.append(seg_tip)

    # 세그먼트/플랜폼 자동 채우기
    wing = segment_properties(wing)
    wing = wing_segmented_planform(wing)

    # 기준 면적(레퍼런스 영역) 설정
    vehicle.reference_area           = wing.areas.reference


    # vehicle 에 추가
    vehicle.append_component(wing)


    

    # ------------------------------------------------------------------
    # Horizontal Tail
    # ------------------------------------------------------------------
    ht_data = stabilizer.horizontal
    ht = Horizontal_Tail()
    ht.tag                      = ht_data.tag
    ht.areas.reference          = float(ht_data.area)
    ht.aspect_ratio             = float(ht_data.aspect_ratio)
    ht.taper                    = float(ht_data.taper)
    ht.sweeps.quarter_chord     = float(ht_data.sweeps.quarter_chord) * Units.degrees
    ht.thickness_to_chord       = float(ht_data.thickness_to_chord)
    ht.dihedral                 = float(ht_data.dihedral) * Units.degrees
    ht.origin                   = [[float(ht_data.origin[0][0]),
                                    float(ht_data.origin[0][1]),
                                    float(ht_data.origin[0][2])]]
    # 플랜폼 자동 채움
    ht = wing_planform(ht)
    vehicle.append_component(ht)


    # ------------------------------------------------------------------
    # Vertical Tail
    # ------------------------------------------------------------------
    # ===== Vertical Tail - Right =====
    vtR_data = stabilizer.vertical_R
    vtR = Vertical_Tail()
    vtR.tag                     = vtR_data.tag
    vtR.areas.reference         = float(vtR_data.area)
    vtR.aspect_ratio            = float(vtR_data.aspect_ratio)
    vtR.taper                   = float(vtR_data.taper)
    vtR.sweeps.quarter_chord    = float(vtR_data.sweeps.quarter_chord) * Units.degrees
    vtR.thickness_to_chord      = float(vtR_data.thickness_to_chord)
    vtR.dihedral                = 0.0 * Units.degrees
    vtR.origin                  = [[float(vtR_data.origin[0][0]),
                                    float(vtR_data.origin[0][1]),
                                    float(vtR_data.origin[0][2])]]
    # 플랜폼 자동 채움
    vtR = wing_planform(vtR)
    vehicle.append_component(vtR)

    # ===== Vertical Tail - Left =====
    vtL_data = stabilizer.vertical_L
    vtL = Vertical_Tail()
    vtL.tag                     = vtL_data.tag
    vtL.areas.reference         = float(vtL_data.area)
    vtL.aspect_ratio            = float(vtL_data.aspect_ratio)
    vtL.taper                   = float(vtL_data.taper)
    vtL.sweeps.quarter_chord    = float(vtL_data.sweeps.quarter_chord) * Units.degrees
    vtL.thickness_to_chord      = float(vtL_data.thickness_to_chord)
    vtL.dihedral                = 0.0 * Units.degrees
    vtL.origin                  = [[float(vtL_data.origin[0][0]),
                                    float(vtL_data.origin[0][1]),
                                    float(vtL_data.origin[0][2])]]
    # 플랜폼 자동 채움
    vtL = wing_planform(vtL)
    vehicle.append_component(vtL)
    
    

    #------------------------------------------------------------------
    # Network : Lift_Cruise (값을 requirements/params에서 읽어옴)
    #------------------------------------------------------------------
    net                              = SUAVE.Components.Energy.Networks.Lift_Cruise()
    net.number_of_lift_rotor_engines = int(getattr(params, 'number_of_rotors',   4))
    net.number_of_propeller_engines  = int(getattr(params, 'number_of_thruster', 1))
    net.identical_propellers         = bool(getattr(params, 'identical_propellers',  True))
    net.identical_lift_rotors        = bool(getattr(params, 'identical_lift_rotors', True))
    net.voltage                      = float(getattr(params, 'bus_voltage_V', 400.0))     # [V] (튜토리얼과 동일하게 무단위 float 사용)


    #------------------------------------------------------------------
    # Design Rotors 
    #------------------------------------------------------------------    
    # The lift rotors           
    for lr in lift_rotor:  
        net.lift_rotors.append(lr)        # 사이징된 리프트 로터를 네트워크에 추가
        


    #------------------------------------------------------------------
    # Design Propellers  
    #------------------------------------------------------------------          
    # The tractor propeller
    net.propellers.append(thrust_prop)    # 사이징된 프로펠러를 네트워크에 추가


    #------------------------------------------------------------------
    # Electronic Speed Controller (ESC)
    #------------------------------------------------------------------
    lift_rotor_esc              = SUAVE.Components.Energy.Distributors.Electronic_Speed_Controller()
    lift_rotor_esc.efficiency   = float(getattr(params, 'lift_esc_efficiency', 0.95))
    net.lift_rotor_esc          = lift_rotor_esc

    propeller_esc               = SUAVE.Components.Energy.Distributors.Electronic_Speed_Controller()
    propeller_esc.efficiency    = float(getattr(params, 'prop_esc_efficiency', 0.95))
    net.propeller_esc           = propeller_esc

 
    #------------------------------------------------------------------
    # Payload (임무 장치 전력)
    #------------------------------------------------------------------
    payload               = SUAVE.Components.Energy.Peripherals.Avionics()
    payload.power_draw    = float(getattr(requirements, 'payload_power_W', 0.0)) * Units.watts
    payload.mass_properties.mass = float(getattr(requirements, 'equipment_mass', 0.0)) * Units.kg   # [kg] 장비 중량
    net.payload           = payload
    
    
    #------------------------------------------------------------------
    # Avionics (항공전자 전력)
    #------------------------------------------------------------------
    avionics              = SUAVE.Components.Energy.Peripherals.Avionics()
    avionics.power_draw   = float(getattr(requirements, 'avionics_power_W', 300.0)) * Units.watts
    net.avionics          = avionics
    
    
    #------------------------------------------------------------------
    # Design Battery     
    #------------------------------------------------------------------
    # 기존 배터리가 있으면 그대로 사용
    if existing_bat is not None and getattr(existing_bat.mass_properties, 'mass', 0.0) > 0:
        bat = existing_bat

    # 없으면 새 배터리 생성 (초기 guess 기반)
    else:
        bat = SUAVE.Components.Energy.Storages.Batteries.Constant_Mass.Lithium_Ion_LiNiMnCoO2_18650()
        bat.mass_properties.mass = params.initial_MTOW * params.initial_battery_mass_frac   # 초기 배터리 중량 [kg]
        bat.max_voltage          = net.voltage

        
        initialize_from_mass(bat) 
        

    # 네트워크에 배터리 업데이트
    net.battery = bat   



    #------------------------------------------------------------------
    # Design Motors
    #------------------------------------------------------------------
    def _first_or_self(x):
        """origin이 [[x,y,z]] 형태일 수 있어 첫 원소를 꺼내되, 아니면 그대로 반환"""
        try:
            if isinstance(x, (list, tuple)) and len(x) > 0 and isinstance(x[0], (list, tuple)):
                return x[0]
        except Exception:
            pass
        return x

    # ================= Thrust Prop Motor =================
    if hasattr(motors, 'thrust_motors') and motors.thrust_motors:
        for m in motors.thrust_motors:
            # origin/반경 보강 (필요할 때만)
            if getattr(m, 'origin', None) is None and getattr(thrust_prop, 'origin', None):
                m.origin = _first_or_self(thrust_prop.origin)
            if getattr(m, 'propeller_radius', None) in (None, 0.0) and getattr(thrust_prop, 'tip_radius', None):
                m.propeller_radius = float(thrust_prop.tip_radius)
            net.propeller_motors.append(m)

    # ================= Lift Rotor Motors =================
    lift_list = lift_rotor if isinstance(lift_rotor, (list, tuple)) else [lift_rotor]
    if hasattr(motors, 'lift_motors') and motors.lift_motors:
        for lr, m in zip(lift_list, motors.lift_motors):   # ← 원본 리스트 기반 매칭
            if getattr(m, 'origin', None) is None and getattr(lr, 'origin', None):
                m.origin = _first_or_self(lr.origin)
            if getattr(m, 'propeller_radius', None) in (None, 0.0) and getattr(lr, 'tip_radius', None):
                m.propeller_radius = float(lr.tip_radius)
            net.lift_rotor_motors.append(m)
    
  
    vehicle.append_component(net)   # vehicle에 에너지 네트워크 컴퍼넌트 추가
    
    
    
    #------------------------------------------------------------------
    # 배선을 위한 위치 파라미터 생성 (motor_spanwise_locations)
    #------------------------------------------------------------------
    try:
        MSL_list = []
        # lift_rotor 입력이 리스트/튜플인지 확인
        lift_list = lift_rotor if isinstance(lift_rotor, (list, tuple)) else [lift_rotor]

        # wingspan (m)
        wingspan = float(getattr(wing.spans, 'projected', 0.0))
        half_span = 0.5 * wingspan if wingspan > 0.0 else 1.0

        for lr in lift_list:
            orig = getattr(lr, 'origin', None)
            if orig is None:
                MSL_list.append(0.0)
                continue
            # origin이 [[x,y,z]] 형태일 수 있으므로 안전하게 첫 요소 사용
            try:
                if isinstance(orig, (list, tuple)) and len(orig) > 0 and isinstance(orig[0], (list, tuple)):
                    o = orig[0]
                else:
                    o = orig
            except Exception:
                o = orig
            # y 좌표 추출 (없으면 0)
            try:
                y = float(o[1])
            except Exception:
                y = 0.0
            frac = abs(y) / half_span if half_span > 0.0 else 0.0
            # 0..1 범위로 클램프
            frac = max(0.0, min(1.0, frac))
            MSL_list.append(frac)

        # wing에 numpy 배열로 저장 (wiring이 abs/np.sum 사용시 안전)
        MSL_array = np.array(MSL_list, dtype=float)

        # --- build half-wing list preserving multiplicity:
        # take positive y motors (one side) in the original order, compute frac = abs(y)/half_span
        try:
            pos_fracs = []
            for lr in lift_list:
                orig = getattr(lr, 'origin', None)
                if orig is None:
                    continue
                try:
                    o = orig[0] if isinstance(orig, (list, tuple)) and len(orig) > 0 else orig
                    y = float(o[1])
                except Exception:
                    continue
                if y >= 0.0:
                    frac = abs(y) / half_span if half_span > 0 else 0.0
                    pos_fracs.append(max(0.0, min(1.0, frac)))
            # If nothing positive found, fallback to absolute fractions
            if len(pos_fracs) == 0:
                pos_fracs = np.abs(MSL_array).tolist()
            MSL_array = np.array(pos_fracs, dtype=float)
        except Exception:
            # fallback to previous array if anything goes wrong
            MSL_array = np.array(MSL_list, dtype=float)

        wing.motor_spanwise_locations = MSL_array

        # vehicle.config.wings[...] 구조가 필요한 코드(wiring 등)를 위해 기본 구조 생성/저장
        if not hasattr(vehicle, 'config') or vehicle.config is None:
            vehicle.config = Data()
        if not hasattr(vehicle.config, 'wings') or vehicle.config.wings is None:
            vehicle.config.wings = {}
        vehicle.config.wings[wing.tag] = {'motor_spanwise_locations': MSL_array}
    except Exception as _e:
        print(f"[WARN] unable to build motor_spanwise_locations: {_e}")



    #------------------------------------------------------------------
    # Booms : 사이징된 붐 컴포넌트 추가
    #------------------------------------------------------------------
    for b in booms:
        vehicle.append_component(b)
        
    # Now account for things that have been overlooked for now:  
    vehicle.excrescence_area = 0.001   # 차량의 돌출부 면적(렌딩기어-논문 참조)

    return vehicle

