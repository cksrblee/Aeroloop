## @ingroup Methods-Missions
# setup_mission.py – build Sequential_Segments from mission_profile
#
# Created:  09.10 2025, Chanyoung Joo
# Modified: 10.02 2025, Chanyoung Joo

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import numpy as np
import SUAVE
from SUAVE.Core import Units

def setup_mission(params, vehicle, analyses, mission_profile):
    """
    mission_profile(Excel_Reader.py의 mission_profile_reader가 생성)을 받아
    SUAVE Sequential_Segments 미션을 구성한다.

    기대하는 mission_profile.segments 각 원소의 필드(단위는 엑셀 그대로): 
      - tag: str
      - segment_class: 아래 8종 중 하나
        1) 'Hover.Hover'
        2) 'Hover.Climb'
        3) 'Hover.Descent'
        4) 'Transition.Constant_Acceleration_Constant_Angle_Linear_Climb'
        5) 'Climb.Linear_Speed_Constant_Rate'
        6) 'Descent.Linear_Mach_Constant_Rate'
        7) 'Cruise.Constant_Speed_Constant_Altitude_Loiter'
        8) 'Cruise.Constant_Speed_Constant_Altitude'
      - altitude_start_ft, altitude_end_ft
      - air_speed_start_knots, air_speed_end_knots
      - climb_rate_fpm, descent_rate_fpm
      - duration_s, distance_miles
      - pitch_initial( deg ), pitch_final( deg )
      - battery_energy_frac (0~1, 선택)

    반환:
      SUAVE.Analyses.Mission.Sequential_Segments 객체
    """

    # --------------------------------------------------------------------------------
    # Mission / Base Segment 공통 설정
    # --------------------------------------------------------------------------------
    mission     = SUAVE.Analyses.Mission.Sequential_Segments()
    mission.tag = 'normal_mission'

    Segments = SUAVE.Analyses.Mission.Segments

    base_segment = Segments.Segment()
    base_segment.state.numerics.number_control_points = params.num_of_control_points
    base_segment.process.initialize.initialize_battery      = SUAVE.Methods.Missions.Segments.Common.Energy.initialize_battery
    base_segment.process.iterate.conditions.planet_position = SUAVE.Methods.skip
    base_segment.process.iterate.conditions.stability       = SUAVE.Methods.skip
    base_segment.process.finalize.post_process.stability    = SUAVE.Methods.skip

    # 배터리 시작 에너지(옵션): 첫 세그먼트에서 battery_energy_frac 제공시만 적용
    def _maybe_set_initial_batt_energy(seg, frac):
        # None 또는 float NaN이면 무시
        if frac is None or (isinstance(frac, float) and np.isnan(frac)) or frac <= 0.0:
            return
        try:
            seg.battery_energy = float(frac) * vehicle.networks.lift_cruise.battery.max_energy
        except Exception:
            pass

    # 숫자 안전 추출
    def _f(v, default=None):
        try:
            x = float(v)
            return x
        except Exception:
            return default

    # --------------------------------------------------------------------------------
    # 세그먼트 작성 루틴
    # --------------------------------------------------------------------------------
    for row in mission_profile.segments:
        cls = (row.segment_class or "").strip()
        tag = (row.tag or "").strip() or "seg"

        # 공통 입력(엑셀 단위 → SUAVE 단위로 변환)
        h0  = _f(getattr(row, 'altitude_start_ft', None), None)
        h1  = _f(getattr(row, 'altitude_end_ft',   None), None)
        V0k = _f(getattr(row, 'air_speed_start_knots', None), None)
        V1k = _f(getattr(row, 'air_speed_end_knots',   None), None)
        roc = _f(getattr(row, 'climb_rate_fpm',        None), None)
        rod = _f(getattr(row, 'descent_rate_fpm',      None), None)
        dur = _f(getattr(row, 'duration_s',            None), None)
        dis = _f(getattr(row, 'distance_miles',        None), None)
        pit0= _f(getattr(row, 'pitch_initial',         None), None)
        pit1= _f(getattr(row, 'pitch_final',           None), None)
        frac= _f(getattr(row, 'battery_energy_frac',   None), None)
        
        # 입력받은 mission_profile 데이터
        try:
            if not hasattr(setup_mission, "_printed_mission_table_header"):
                hdr = (f"{'segment':<22s} | {'h0(ft)':>8s} | {'h1(ft)':>8s} | "
                       f"{'roc(fpm)':>9s} | {'rod(fpm)':>9s} | {'V0(kt)':>7s} | {'V1(kt)':>7s} | "
                       f"{'dist(mi)':>9s} | {'dur(s)':>7s} | {'pit0(deg)':>10s} | {'pit1(deg)':>10s} | {'batt_frac':>9s}")
                sep = "-" * len(hdr)
                print("\n" + hdr)
                print(sep)
                setattr(setup_mission, "_printed_mission_table_header", True)

            def _fmt(x, fmt):
                return "-" if x is None else fmt.format(x)

            row_str = (f"{tag:<22s} | "
                       f"{_fmt(h0,'{:8.0f}')} | {_fmt(h1,'{:8.0f}')} | "
                       f"{_fmt(roc,'{:9.1f}')} | {_fmt(rod,'{:9.1f}')} | "
                       f"{_fmt(V0k,'{:7.1f}')} | {_fmt(V1k,'{:7.1f}')} | "
                       f"{_fmt(dis,'{:9.2f}')} | {_fmt(dur,'{:7.1f}')} | "
                       f"{_fmt(pit0,'{:10.2f}')} | {_fmt(pit1,'{:10.2f}')} | "
                       f"{_fmt(frac,'{:9.3f}')}")
            print(row_str)
        except Exception:
            # fallback to original simple print if formatting fails
            print(tag ,h0, h1, roc, rod, V0k, V1k, dis, dur, pit0, pit1, frac)

        # ─────────────────────────────────────────────────────────────────────
        # 1) Hover.Hover  (제자리 호버: altitude, time)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Hover.Hover':
            segment     = Segments.Hover.Hover(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            # 필수: altitude(ft), time(s)
            segment.altitude = (h1 if h1 is not None else h0 if h0 is not None else 0.0) * Units.ft
            segment.time     = (dur if dur is not None else 30.0) * Units.s

            # 첫 세그먼트에서만 배터리 초기 에너지 비율 적용을 권장
            _maybe_set_initial_batt_energy(segment, frac)

            # 네트워크 잔차/미지수(호버)
            segment.process.iterate.unknowns.mission = SUAVE.Methods.skip
            segment = vehicle.networks.lift_cruise.add_lift_unknowns_and_residuals_to_segment(segment)

            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 2) Hover.Climb  (수직상승: alt_start, alt_end, climb_rate)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Hover.Climb':
            segment     = Segments.Hover.Climb(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            segment.altitude_start = (h0 if h0 is not None else 0.0)  * Units.ft
            segment.altitude_end   = (h1 if h1 is not None else 50.0) * Units.ft
            segment.climb_rate     = (roc if roc is not None else 500.0) * Units['ft/min']

            _maybe_set_initial_batt_energy(segment, frac)

            segment.process.iterate.unknowns.mission = SUAVE.Methods.skip
            segment = vehicle.networks.lift_cruise.add_lift_unknowns_and_residuals_to_segment(segment)

            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 3) Hover.Descent (수직강하: alt_start, alt_end, descent_rate)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Hover.Descent':
            segment     = Segments.Hover.Descent(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            segment.altitude_start = (h0 if h0 is not None else 5.0) * Units.ft
            segment.altitude_end   = (h1 if h1 is not None else 0.0)  * Units.ft
            segment.descent_rate   = (rod if rod is not None else 300.0) * Units['ft/min']

            _maybe_set_initial_batt_energy(segment, frac)

            segment.process.iterate.unknowns.mission = SUAVE.Methods.skip
            segment = vehicle.networks.lift_cruise.add_lift_unknowns_and_residuals_to_segment(segment)

            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 4) Transition.Constant_Acceleration_Constant_Angle_Linear_Climb
        #    (전환: alt_start/end, V_start/end, climb/descent rate → t, accel, angle 계산)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Transition.Constant_Acceleration_Constant_Angle_Linear_Climb':
            segment     = Segments.Transition.Constant_Acceleration_Constant_Angle_Linear_Climb(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            # 입력 단위 → SI로 계산
            alt0 = (h0 if h0 is not None else 0.0)   * Units.ft
            alt1 = (h1 if h1 is not None else alt0)  * Units.ft
            V0   = (V0k if V0k is not None else 0.0) * Units.knots
            V1   = (V1k if V1k is not None else V0)  * Units.knots

            # 등률(상승/하강) 선택
            rate = None
            if roc is not None and roc != 0.0:
                rate = roc * Units['ft/min']
            elif rod is not None and rod != 0.0:
                rate = -abs(rod) * Units['ft/min']
            else:
                # 기본: 500 ft/min 상승, 만약 하강 케이스면 음수
                rate = 500.0 * Units['ft/min'] if (alt1 >= alt0) else -500.0 * Units['ft/min']

            # 지속시간 추정: t = Δh / rate (부호 일치 보정)
            dh = alt1 - alt0
            if rate == 0.0:
                t_des = 30.0 * Units.s
            else:
                t_des = abs(dh / rate)
                if not np.isfinite(t_des) or t_des <= 0.0:
                    t_des = 30.0 * Units.s

            # 수평변위 & 기울기각
            Vavg = 0.5 * (V0 + V1)
            dx   = Vavg * t_des
            if roc is not None and roc != 0.0:
                gamma= np.arctan2(dh, dx if dx != 0.0 else 1e-9)  # [rad]
            elif rod is not None and rod != 0.0:
                gamma= (np.arctan2(dh, dx if dx != 0.0 else 1e-9)) * 1.01  # [rad]
                
            # 가속도
            accel = (V1 - V0) / t_des

            # 값 패킹
            segment.altitude_start = alt0
            segment.altitude_end   = alt1
            segment.air_speed      = V0                    # 초기 속도
            segment.acceleration   = accel
            segment.climb_angle    = gamma                 # [rad]
            segment.pitch_initial  = (pit0 if pit0 is not None else 0.0) * Units.deg
            segment.pitch_final    = (pit1 if pit1 is not None else 0.0) * Units.deg

            segment.process.iterate.unknowns.mission = SUAVE.Methods.skip
            segment = vehicle.networks.lift_cruise.add_transition_unknowns_and_residuals_to_segment(segment)

            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 5) Climb.Linear_Speed_Constant_Rate
        #    (등률 전진 상승: air_speed_start/end, alt_start/end, climb_rate)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Climb.Linear_Speed_Constant_Rate':
            segment     = Segments.Climb.Linear_Speed_Constant_Rate(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            segment.air_speed_start = (V0k if V0k is not None else 60.0)  * Units.knots
            segment.air_speed_end   = (V1k if V1k is not None else 100.0) * Units.knots
            segment.altitude_start  = (h0  if h0  is not None else 300.0) * Units.ft
            segment.altitude_end    = (h1  if h1  is not None else 1000.0)* Units.ft
            segment.climb_rate      = (roc if roc is not None else 500.0) * Units['ft/min']

            segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)
            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 6) Descent.Linear_Mach_Constant_Rate
        #    (등률 전진 하강: speed_start/end, alt_start/end, descent_rate)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Descent.Linear_Mach_Constant_Rate':
            segment     = Segments.Descent.Linear_Mach_Constant_Rate(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            segment.speed_start   = (V0k if V0k is not None else 100.0) * Units.knots
            segment.speed_end     = (V1k if V1k is not None else 70.0)  * Units.knots
            segment.altitude_start= (h0  if h0  is not None else 1000.0)* Units.ft
            segment.altitude_end  = (h1  if h1  is not None else 300.0) * Units.ft
            segment.descent_rate  = (rod if rod is not None else 500.0) * Units['ft/min']

            segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)
            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 7) Cruise.Constant_Speed_Constant_Altitude_Loiter
        #    (등속/등고 로이터: altitude, time, air_speed)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Cruise.Constant_Speed_Constant_Altitude_Loiter':
            segment     = Segments.Cruise.Constant_Speed_Constant_Altitude_Loiter(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            segment.altitude  = (h1 if h1 is not None else h0 if h0 is not None else 300.0) * Units.ft
            segment.time      = (dur if dur is not None else 60.0) * Units.s
            # 로이터는 시작/끝 속도가 동일 입력이라고 가정(엑셀에선 둘 다 채워짐)
            Vref = (V0k if V0k is not None else V1k if V1k is not None else 60.0)
            segment.air_speed = Vref * Units.knots

            segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)
            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 8) Cruise.Constant_Speed_Constant_Altitude
        #    (등속/등고 크루즈: distance(마일), air_speed)
        # ─────────────────────────────────────────────────────────────────────
        if cls == 'Cruise.Constant_Speed_Constant_Altitude':
            segment     = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
            segment.tag = tag
            segment.analyses.extend(analyses)

            # 거리: 엑셀은 "마일"(statute) 기준 → Units.mile 사용
            if dis is not None:
                segment.distance = dis * Units.mile
            else:
                # 기본: 60 nmi 유지하고 싶다면 아래 한 줄로 교체
                # segment.distance = 60.0 * Units.nautical_miles
                segment.distance = 60.0 * Units.mile

            Vref = (V0k if V0k is not None else V1k if V1k is not None else 100.0)
            segment.air_speed = Vref * Units.knots

            segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)
            mission.append_segment(segment)
            continue

        # ─────────────────────────────────────────────────────────────────────
        # 알 수 없는 세그먼트 → 스킵
        # ─────────────────────────────────────────────────────────────────────
        print(f"[WARN] Unknown segment_class='{cls}' (tag='{tag}') → skipped.")

    return mission







# ----------------------------------------------------------------------------------------------------------------------
#   코드 테스트용 하드코딩 Mission
# ----------------------------------------------------------------------------------------------------------------------
def setup_mission_test(params, vehicle, analyses, mission_profile): 
    
    # -------------------------------------------------------------------------------------------------------
    #   Initialize the Mission
    # -------------------------------------------------------------------------------------------------------
    mission            = SUAVE.Analyses.Mission.Sequential_Segments()    # 연속 세그먼트로 구성된 임무 해석 분석 모듈 생성
    mission.tag        = 'normal_mission'   # 임무 태그 설정(일반 임무 프로파일)

    # unpack Segments module
    Segments                                                 = SUAVE.Analyses.Mission.Segments  # 세그먼트 모듈 언팩

    # base segment
    base_segment                                             = Segments.Segment()                 # 기본 세그먼트 생성
    base_segment.state.numerics.number_control_points        = params.num_of_control_points       # 제어 포인트 수 설정
    base_segment.process.initialize.initialize_battery       = SUAVE.Methods.Missions.Segments.Common.Energy.initialize_battery # 배터리 초기화 메소드 설정
    base_segment.process.iterate.conditions.planet_position  = SUAVE.Methods.skip   
    base_segment.process.iterate.conditions.stability        = SUAVE.Methods.skip
    base_segment.process.finalize.post_process.stability     = SUAVE.Methods.skip      
    ones_row                                                 = base_segment.state.ones_row
    
    
    # -------------------------------------------------------------------------------------------------------
    #   Hover Segment
    # -------------------------------------------------------------------------------------------------------
    segment     = Segments.Hover.Hover(base_segment)
    segment.tag = "hover"
    segment.analyses.extend(analyses)
    segment.altitude                                         = 5.0  * Units.ft
    segment.time                                             = 30.  * Units.s
    segment.battery_energy                                   = vehicle.networks.lift_cruise.battery.max_energy*0.95
    segment.process.iterate.unknowns.mission                 = SUAVE.Methods.skip
    segment = vehicle.networks.lift_cruise.add_lift_unknowns_and_residuals_to_segment(segment)
    
    # add to misison
    mission.append_segment(segment)
    
    
    
    # -------------------------------------------------------------------------------------------------------
    #   Hover Climb Segment
    # -------------------------------------------------------------------------------------------------------
    segment     = Segments.Hover.Climb(base_segment)
    segment.tag = "hover_climb"
    segment.analyses.extend(analyses)
    segment.altitude_start                                   = 5.0   * Units.ft
    segment.altitude_end                                     = 50.  * Units.ft
    segment.climb_rate                                       = 500.  * Units['ft/min']
    segment.process.iterate.unknowns.mission                 = SUAVE.Methods.skip
    segment = vehicle.networks.lift_cruise.add_lift_unknowns_and_residuals_to_segment(segment)
    
    # add to misison
    mission.append_segment(segment)
    
    
    # -------------------------------------------------------------------------------------------------------
    #   Transition Segment [Constant_Acceleration_Constant_Angle_Linear_Climb] 
    # -------------------------------------------------------------------------------------------------------
    segment     = Segments.Transition.Constant_Acceleration_Constant_Angle_Linear_Climb(base_segment)
    segment.tag = "Transition_climb"
    segment.analyses.extend(analyses)
    
    # 입력값
    altitude_start                                           = 50.   * Units.ft
    altitude_end                                             = 300.  * Units.ft
    airspeed_start                                           = 0.0   * Units.knots
    airspeed_end                                             = 60.   * Units.knots   
    climb_rate                                               = 500.  * Units['ft/min']
    pitch_initial                                            = 10.   * Units.degrees 
    pitch_final                                              = 10.   * Units.degrees
    
    # 계산값
    t_des                                                    = ((altitude_end - altitude_start) / climb_rate) * Units.s 
    Δx_m                                                     = (((airspeed_start + airspeed_end) / 2) * t_des) * Units.m
    Δh_m                                                     = (altitude_end - altitude_start) * Units.m
    gamma_deg                                                = np.arctan2(Δh_m, Δx_m)
    acceleration                                             = ((airspeed_end - airspeed_start) / t_des) * Units['m/s**2']  

    # 값 패킹
    segment.altitude_start                                   = altitude_start
    segment.altitude_end                                     = altitude_end
    segment.air_speed                                        = airspeed_start
    segment.acceleration                                     = acceleration
    segment.climb_angle                                      = gamma_deg
    segment.pitch_initial                                    = pitch_initial
    segment.pitch_final                                      = pitch_final
    
    segment.process.iterate.unknowns.mission                 = SUAVE.Methods.skip
    segment = vehicle.networks.lift_cruise.add_transition_unknowns_and_residuals_to_segment(segment)
    
    # add to misison
    mission.append_segment(segment)
    

    
    # -------------------------------------------------------------------------------------------------------
    #   Loiter_1 Segment (1min)
    # -------------------------------------------------------------------------------------------------------
    segment                                            = Segments.Cruise.Constant_Speed_Constant_Altitude_Loiter(base_segment)
    segment.tag                                        = "Loiter_1"
    segment.analyses.extend(analyses)
    segment.altitude                                   = 300.  * Units.ft
    segment.time                                       = 1.    * Units.min
    segment.air_speed                                  = 60.  * Units.knots
    segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)

    # add to misison
    mission.append_segment(segment)  
    
    
    # -------------------------------------------------------------------------------------------------------
    #   Second Climb Segment: Linear Speed, Constant Rate
    # -------------------------------------------------------------------------------------------------------
    segment                                            = Segments.Climb.Linear_Speed_Constant_Rate(base_segment)
    segment.tag                                        = 'wing_climb'
    segment.analyses.extend(analyses)

    segment.climb_rate                                 = 500. * Units['ft/min']
    segment.air_speed_start                            = 60.  * Units.knots
    segment.air_speed_end                              = 100. * Units.knots
    segment.altitude_start                             = 300. * Units.ft
    segment.altitude_end                               = 1000. * Units.ft
    segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)
    
    # add to misison
    mission.append_segment(segment)        
    
    # -------------------------------------------------------------------------------------------------------
    #   Cruise
    # -------------------------------------------------------------------------------------------------------
    segment                                            = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
    segment.tag                                        = "Cruise"
    segment.analyses.extend(analyses)
    segment.distance                                   = 60.   * Units.nautical_miles
    segment.air_speed                                  = 100.  * Units.knots
    segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)

    # add to misison
    mission.append_segment(segment)    
    
    
    # -------------------------------------------------------------------------------------------------------
    #   Descent Segment: Linear Speed, Constant Rate
    # -------------------------------------------------------------------------------------------------------
    segment                                            = Segments.Descent.Linear_Mach_Constant_Rate(base_segment)
    segment.tag                                        = 'wing_descent'
    segment.analyses.extend(analyses)

    segment.descent_rate                               = 500.  * Units['ft/min']
    segment.speed_start                                = 100.  * Units.knots
    segment.speed_end                                  = 80.   * Units.knots
    segment.altitude_start                             = 1000. * Units.ft
    segment.altitude_end                               = 300.  * Units.ft
    segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)
    
    # add to misison
    mission.append_segment(segment)    
    
    
    # -------------------------------------------------------------------------------------------------------
    #   Loiter_2 Segment (1min)
    # -------------------------------------------------------------------------------------------------------
    segment                                            = Segments.Cruise.Constant_Speed_Constant_Altitude_Loiter(base_segment)
    segment.tag                                        = "Loiter_2"
    segment.analyses.extend(analyses)
    segment.altitude                                   = 300.  * Units.ft
    segment.time                                       = 1.    * Units.min
    segment.air_speed                                  = 80.   * Units.knots
    segment = vehicle.networks.lift_cruise.add_cruise_unknowns_and_residuals_to_segment(segment)

    # add to misison
    mission.append_segment(segment)  
    
    
    # -------------------------------------------------------------------------------------------------------
    #   re_Transition Segment [Constant_Acceleration_Constant_Angle_Linear_Climb] 
    # -------------------------------------------------------------------------------------------------------
    segment     = Segments.Transition.Constant_Acceleration_Constant_Angle_Linear_Climb(base_segment)
    segment.tag = "re_Transition_descent"
    segment.analyses.extend(analyses)
    
    # 입력값
    altitude_start                                           = 300.  * Units.ft
    altitude_end                                             = 50.   * Units.ft
    airspeed_start                                           = 80.   * Units.knots
    airspeed_end                                             = 0.    * Units.knots   
    climb_rate                                               = -500. * Units['ft/min']
    pitch_initial                                            = 0.0   * Units.degrees 
    pitch_final                                              = 0.0   * Units.degrees
    
    # 계산값
    t_des                                                    = ((altitude_end - altitude_start) / climb_rate) * Units.s 
    Δx_m                                                     = (((airspeed_start + airspeed_end) / 2) * t_des) * Units.m
    Δh_m                                                     = (altitude_end - altitude_start) * Units.m
    gamma_deg                                                = (np.arctan2(Δh_m, Δx_m)) * 1.01
    acceleration                                             = ((airspeed_end - airspeed_start) / t_des) * Units['m/s**2']  

    # 값 패킹
    segment.altitude_start                                   = altitude_start
    segment.altitude_end                                     = altitude_end
    segment.air_speed                                        = airspeed_start
    segment.acceleration                                     = acceleration
    segment.climb_angle                                      = gamma_deg
    segment.pitch_initial                                    = pitch_initial
    segment.pitch_final                                      = pitch_final
    
    segment.process.iterate.unknowns.mission                 = SUAVE.Methods.skip
    segment = vehicle.networks.lift_cruise.add_transition_unknowns_and_residuals_to_segment(segment)
    
    # add to misison
    mission.append_segment(segment)
    
    
    # -------------------------------------------------------------------------------------------------------
    #  Hover Descent
    # -------------------------------------------------------------------------------------------------------
    segment                                            = Segments.Hover.Descent(base_segment)
    segment.tag                                        = "hover_descent"
    segment.analyses.extend(analyses)    
    segment.altitude_start                            = 50.  * Units.ft
    segment.altitude_end                              = 0.
    segment.descent_rate                              = 400 * Units['ft/min'] 
    segment.process.iterate.unknowns.mission          = SUAVE.Methods.skip
    segment = vehicle.networks.lift_cruise.add_lift_unknowns_and_residuals_to_segment(segment)

    # add to misison
    mission.append_segment(segment)          

    return mission