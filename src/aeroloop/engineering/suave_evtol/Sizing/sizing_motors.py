## @ingroup Methods-Sizing
# sizing_motors.py
#
# Created:  2025-09-10, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------
import numpy as np

from SUAVE.Core import Data, Units
from SUAVE.Components.Energy.Converters import Motor
from copy import deepcopy

# SUAVE 공식 모터 사이징 루틴
from SUAVE.Methods.Propulsion.electric_motor_sizing import (
    size_optimal_motor,
    size_from_kv,  
)

# =========================================================================
# Purpose : Size thrust & lift motors using SUAVE's motor sizing pipeline:
#           1) size_optimal_motor (KV/Res optimization)
#           2) size_from_kv       (mass/i0/Res regression from KV)
# I/O:
#   motors = sizing_motors(params, lift_rotor, thrust_prop)
#   -> motors.thrust_motors : [Motor]
#      motors.lift_motors   : [Motor]
# Notes:
# - prop/rotor에 design_torque, angular_velocity가 없으면 rpm/TipMach/shaft     
#   power 등으로 보강
# - 크루즈 프롭은 단일 객체 또는 None, 리프트 로터는 list/tuple/단일 모두 허용
# ======================================================================


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _ensure_prop_design_kinematics(prop, default_tip_mach=0.7, a_snd=340.0):
    """
    모터 사이징에 필요한 최소 설계치 보강:
      - angular_velocity [rad/s]
      - design_torque    [N·m] (없으면 power/ω 또는 보수 추정)
    prop 필수/권장 필드:
      tip_radius [m], (권장) design_tip_mach, rpm, design_power, P_shaft, shaft_power, design_thrust
    """
    # ---- 각속도 보장 ----
    omega = getattr(prop, 'angular_velocity', None)

    if omega in (None, 0.0):
        # rpm → ω
        rpm = getattr(prop, 'rpm', None)
        if rpm not in (None, 0.0):
            omega = 2.0 * np.pi * float(rpm) / 60.0

    if omega in (None, 0.0):
        # tip Mach → ω ( M_tip * a / R_tip )
        tip_mach = getattr(prop, 'design_tip_mach', default_tip_mach)
        R_tip    = float(getattr(prop, 'tip_radius', 0.0) or 0.0)
        if R_tip > 0.0 and tip_mach not in (None, 0.0):
            omega = (float(tip_mach) * float(a_snd)) / R_tip

    if omega in (None, 0.0):
        # 최후방어: 1800 rpm
        omega = 2.0 * np.pi * 1800.0 / 60.0

    prop.angular_velocity = float(omega)

    # ---- 설계 토크 보장 ----
    if not hasattr(prop, 'design_torque') or prop.design_torque in (None, 0.0):
        # power가 있으면 Q = P/ω
        P = None
        for cand in ('design_power', 'shaft_power', 'P_shaft', 'power'):
            val = getattr(prop, cand, None)
            if val not in (None, 0.0):
                P = float(val)
                break

        if P is not None:
            prop.design_torque = float(P) / max(prop.angular_velocity, 1e-9)
        else:
            # 추력과 반경에서 대략 추정 (Q ≈ k·T·R, k≈0.35)
            T = getattr(prop, 'design_thrust', None)
            R = float(getattr(prop, 'tip_radius', 0.0) or 0.0)
            if T not in (None, 0.0) and R > 0.0:
                prop.design_torque = 0.35 * float(T) * R
            else:
                # 정말 정보가 없으면 극소값
                prop.design_torque = 1.0

    return prop


def _build_motor_from_params(kind, params, bus_V, origin=None, prop_radius=None):
    """
    kind: 'thrust' | 'lift'
    params에서 효율/전압 분배/무부하전류/기어비/질량 초기치 등을 읽어 Motor 생성
    """
    m = Motor()

    # 효율
    if kind == 'thrust':
        m.efficiency = float(getattr(params, 'prop_motor_efficiency', 0.95))
    else:
        m.efficiency = float(getattr(params, 'lift_motor_efficiency', 0.85))

    # 전압(버스 분배)
    if kind == 'thrust':
        v_frac = float(getattr(params, 'prop_motor_voltage_frac', 1.00))  # = 100% of bus
    else:
        v_frac = float(getattr(params, 'lift_motor_voltage_frac', 0.75))  # = 75% of bus
    m.nominal_voltage = float(bus_V) * v_frac

    # 무부하 전류 초기치(i0 guess) — size_from_kv가 갱신 가능
    if kind == 'thrust':
        m.no_load_current = float(getattr(params, 'prop_motor_no_load_A', 2.0))
        m.mass_properties.mass = float(getattr(params, 'prop_motor_mass_guess_kg', 2.0)) * Units.kg
    else:
        m.no_load_current = float(getattr(params, 'lift_motor_no_load_A', 4.0))
        m.mass_properties.mass = float(getattr(params, 'lift_motor_mass_guess_kg', 3.0)) * Units.kg

    # 기어비(기본 직결)
    m.gear_ratio = float(getattr(params, 'motor_gear_ratio', 1.0))

    # 배치용 참조
    if origin is not None:
        m.origin = origin
    if prop_radius is not None:
        m.propeller_radius = float(prop_radius)

    return m


def _optimize_and_size_mass(motor, prop, params):
    """
    SUAVE 파이프라인:
      1) size_optimal_motor(motor, prop) → KV/Res 최적화
      2) size_from_kv(motor)             → KV로 mass/Res/i0 회귀식 반영

    keep_resistance: True면 size_from_kv 이후에도 최적화 결과의 저항을 유지
    keep_no_load_current: True면 size_from_kv 이후에도 사용자가 준 i0를 유지
    """
    # 1) 설계치 보강(필수)
    prop = _ensure_prop_design_kinematics(prop)

    # 2) KV/Res 최적화
    motor = size_optimal_motor(motor, prop, log_switch=False)   # 모터 로그 스위치

    # 3) (옵션) 보존 값 저장
    res_opt = float(getattr(motor, 'resistance', 0.0) or 0.0)
    i0_opt  = float(getattr(motor, 'no_load_current', 0.0) or 0.0)
    kv_opt  = float(getattr(motor, 'speed_constant', 0.0) or 0.0)

    # 4) KV 기반 질량 회귀 (기본)
    motor_mass_only = size_from_kv(deepcopy(motor))  # KV 동일 전제

    # 질량 결정 방식 선택: params.motor_mass_method = 'kv'|'empirical'
    method = str(getattr(params, 'motor_mass_method', 'empirical') or 'kv').lower()
    if method == 'empirical':
        # 경험식: W_lb = 0.3928 * Q_ftlb^0.8587  (Q: ft·lb), 결과를 kg로 변환
        Q_Nm = float(getattr(prop, 'design_torque', getattr(motor, 'design_torque', 1.0)) or 1.0)
        Q_ftlb = Q_Nm * 0.737562149
        W_lb = 0.3928 * (Q_ftlb ** 0.8587)
        W_kg = W_lb * 0.45359237
        motor.mass_properties.mass = W_kg * Units.kg
    else:
        # 기본 KV 회귀 결과 사용
        motor.mass_properties.mass = motor_mass_only.mass_properties.mass
    motor.resistance           = res_opt
    motor.no_load_current      = i0_opt
    motor.speed_constant       = kv_opt

    return motor


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def sizing_motors(params, lift_rotor, thrust_prop):
    """
    모터 사이징 엔트리 포인트
    """
    motors = Data()
    motors.thrust_motors = []
    motors.lift_motors   = []

    # 버스 전압
    bus_V = float(getattr(params, 'bus_voltage_V', 400.0))  # [V]

    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)

    # ---------------- Thrust motor (크루즈 프롭) ----------------
    if thrust_prop is not None:
        m_prop = _build_motor_from_params(
            'thrust',
            params,
            bus_V,
            origin=getattr(thrust_prop, 'origin', None),
            prop_radius=getattr(thrust_prop, 'tip_radius', None),
        )
        # KV/Res 최적화 + KV 회귀 질량
        m_prop = _optimize_and_size_mass(m_prop, thrust_prop, params)
        # 태그 정리
        m_prop.tag = getattr(m_prop, 'tag', 'propeller_motor')
        motors.thrust_motors.append(m_prop)

    # ---------------- Lift motors (리프트 로터들) ----------------
    lift_list = lift_rotor if isinstance(lift_rotor, (list, tuple)) else [lift_rotor]

    for i, lr in enumerate(lift_list, start=1):
        m_lift = _build_motor_from_params(
            'lift',
            params,
            bus_V,
            origin=getattr(lr, 'origin', None),
            prop_radius=getattr(lr, 'tip_radius', None),
        )
        m_lift = _optimize_and_size_mass(m_lift, lr, params)
        m_lift.tag = f"lift_motor_{i}"
        motors.lift_motors.append(m_lift)



    # --- 간단 요약 출력  ---
    try:
        # Cruise prop summary
        if len(motors.thrust_motors) > 0:
            n_props = len(motors.thrust_motors)
            D_prop = 2.0 * float(getattr(thrust_prop, 'tip_radius', 0.0) or 0.0) if thrust_prop is not None else 0.0
            T_prop = float(getattr(thrust_prop, 'design_thrust', 0.0) or 0.0) if thrust_prop is not None else 0.0
            omega_prop = float(getattr(thrust_prop, 'angular_velocity', 0.0) or 0.0) if thrust_prop is not None else 0.0
            _log(f"[prop motor] N={n_props}, D={D_prop:.3f} m, T/rot={T_prop:.1f} N, ω={omega_prop:.1f} rad/s")

        # Lift motors summary
        if len(motors.lift_motors) > 0:
            n_lifts = len(motors.lift_motors)
            # extract geometry from input lift_rotor list (lr)
            xs, ys, zs, Ds, Ts, omegas = [], [], [], [], [], []
            for lr in lift_list:
                orig = getattr(lr, 'origin', None)
                try:
                    o = orig[0] if isinstance(orig, (list, tuple)) and len(orig) > 0 else orig
                    ox = float(o[0]); oy = float(o[1]); oz = float(o[2])
                except Exception:
                    ox = oy = oz = 0.0
                xs.append(ox); ys.append(oy); zs.append(oz)
                D = 2.0 * float(getattr(lr, 'tip_radius', 0.0) or 0.0)
                Ds.append(D)
                Ts.append(float(getattr(lr, 'design_thrust', 0.0) or 0.0))
                omegas.append(float(getattr(lr, 'angular_velocity', 0.0) or 0.0))

            D_mean = float(np.mean(Ds)) if len(Ds) > 0 else 0.0
            R_mean = 0.5 * D_mean
            T_mean = float(np.mean(Ts)) if len(Ts) > 0 else 0.0
            x_front = float(min(xs)) if len(xs) > 0 else 0.0
            x_back  = float(max(xs)) if len(xs) > 0 else 0.0
            y_base  = float(np.mean(np.abs(ys))) if len(ys) > 0 else 0.0
            try:
                uniq = np.unique(np.sort(np.round(np.abs(np.array(ys)),6)))
                dy = float(np.mean(np.diff(uniq))) if uniq.size > 1 else 0.0
            except Exception:
                dy = 0.0
            z_mean = float(np.mean(zs)) if len(zs) > 0 else 0.0
            omega_mean = float(np.mean([v for v in omegas if v > 0])) if any(v > 0 for v in omegas) else 0.0

            # per-side count guessed as half if symmetric
            per_side = int(n_lifts/2) if n_lifts >= 2 else n_lifts
            _log(f"[lift motor] N={n_lifts} (front/back={per_side}/{per_side}), D={D_mean:.3f} m, R={R_mean:.3f} m, T/rot={T_mean:.1f} N, x: front={x_front:.3f}, back={x_back:.3f}, y_base={y_base:.3f}, dy={dy:.3f}, z={z_mean:.3f}, ω={omega_mean:.1f} rad/s")
    except Exception:
        pass

    return motors
