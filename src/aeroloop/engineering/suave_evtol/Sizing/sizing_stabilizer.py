## @ingroup Methods-Sizing
# sizing_stabilizer.py 

# Created:  09.09 2025, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import numpy as np
from SUAVE.Core import Data

# ======================================================================
#  sizing_stabilizer.py
#  - Horizontal tail (rectangular) + twin Vertical tails (taper+swept)
#  - Constraints:
#      * c_HT == c_VT_tip
#      * HT tip meets VT top (z align), and VT quarter-chord aligns with HT QC (x align)
#      * Common tail arm l used for HT/VT
#      * Rotor clearance on VT root leading edge
#  - Outputs sizes + SUAVE component-ready fields (area, AR, taper, sweep, origin)
# ======================================================================
def sizing_stabilizer(params, main_wing, lift_rotors, fuselage_design, max_iter=30):
    """
    미익 사이징(HT/VT) — 형상/배치 원칙
      1) HT chord == VT tip chord  (HT는 직사각형)
      2) HT 팁이 VT 최상단과 z로 맞닿음  (z_ht = z_w + b_v)
      3) x 정렬: VT root QC = HT QC (공통 테일암 l 사용)
      4) VT는 테이퍼(t_v) + 1/4현 스윕(sweep_v_deg)
      5) VT 루트 LE는 후방 리프트로터 + 여유와 간섭 금지

    입력
      - main_wing: wing_area, spans, MAC, origin[[x,y,z]]
      - lift_rotors: SUAVE Lift_Rotor 객체 리스트 (origin, tip_radius 필요)
      - fuselage_design: lengths.total, segments[-1].height 등
      - params: 아래 “필요 파라미터 정리” 참고

    반환
      stab: Data()
        .horizontal  (HT)
        .vertical    (R+L 합산 성능/보고용)
        .vertical_R  (오른쪽 VT)
        .vertical_L  (왼쪽 VT)
      내부 필드들은 SUAVE Horizontal_Tail / Vertical_Tail 생성에 바로 매핑 가능
    """

    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)

    # ---------------- 0) 주익/기준 치수 ----------------
    Sw   = float(main_wing.wing_area)
    bw   = float(main_wing.spans)
    cbar = float(main_wing.MAC)
    x_le = float(main_wing.origin[0][0])
    z_w  = float(main_wing.origin[0][2])
    x_ref = x_le + 0.25 * cbar                          # 주익 1/4현 기준 x

    L_fuse = float(getattr(getattr(fuselage_design, 'lengths', Data()), 'total',
                           getattr(params, 'fuselage_length', 6.5)))

    # ---------------- 1) HT 스팬: 항상 'inner 로터' 기준 ----------------
    Ypos = sorted({round(float(r.origin[0][1]), 6) for r in lift_rotors if r.origin[0][1] > 0})
    Yneg = sorted({round(float(r.origin[0][1]), 6) for r in lift_rotors if r.origin[0][1] < 0})
    if not Ypos or not Yneg:
        raise ValueError("좌/우 리프트 로터가 모두 필요합니다(HT 스팬 산정용).")

    y_R_inner = Ypos[0]
    y_L_inner = Yneg[-1]
    y_R_sel = y_R_inner                                    # ← 항상 inner
    y_L_sel = y_L_inner

    b_h = float(y_R_sel - y_L_sel)                         # HT span
    if b_h <= 0:
        raise ValueError("선택된 좌/우 VT y가 비정상입니다.")
    y_center_ht = 0.5 * (y_R_sel + y_L_sel)

    # ---------------- 2) 목표/제약 파라미터 ----------------
    Vh_tgt = float(getattr(params, 'Vh_target', 0.65))
    Vv_tgt = float(getattr(params, 'Vv_target', 0.028))
    eta_h  = float(getattr(params, 'eta_h', 0.90))
    eta_v  = float(getattr(params, 'eta_v', 0.95))

    cmin_h = float(getattr(params, 'ht_c_root_min_m', 0.25))
    cmax_h = float(getattr(params, 'ht_c_root_max_m', 1.20))

    t_v    = float(getattr(params, 'taper_v', 0.90))
    sweep_min_deg  = float(getattr(params, 'sweep_v_quarter_min_deg', 0.0))
    sweep_max_deg  = float(getattr(params, 'sweep_v_quarter_max_deg', 35.0))
    user_sweep_deg = getattr(params, 'sweep_v_user_deg', None)  # 지정 시 우선

    lh_frac_guess = float(getattr(params, 'lh_frac_guess', 0.55))
    lh_min_frac   = float(getattr(params, 'lh_min_frac', 0.35))
    lh_max_frac   = float(getattr(params, 'lh_max_frac', 0.95))

    margin_m_opt  = getattr(params, 'vt_rotor_clear_margin_m', None)
    margin_fracD  = float(getattr(params, 'vt_rotor_clear_margin_frac_of_D', 0.15))

    # ---------------- 3) VT-로터 간섭 하한 x 계산 ----------------
    def _rear_x_and_R(side_positive=True):
        side = [r for r in lift_rotors if (r.origin[0][1] > 0) == bool(side_positive)]
        if not side:
            return None, None
        x_rear = max(float(r.origin[0][0]) for r in side)                  # 그 측 최후방 로터 x
        R_max  = max(float(getattr(r, 'tip_radius', 0.0)) for r in side)   # 최대 반경
        return x_rear, R_max

    xR, RR = _rear_x_and_R(True)
    xL, RL = _rear_x_and_R(False)
    x_rear_max = max(v for v in [xR, xL] if v is not None)
    R_max      = max(v for v in [RR, RL] if v is not None)
    margin_m   = float(margin_m_opt) if (margin_m_opt is not None) else (margin_fracD * (2.0 * R_max))
    x_clear_min = x_rear_max + R_max + margin_m                              # VT 루트 LE x ≥ 이 값

    # ---------------- 4) HT chord & 공통 테일암 l 수렴 ----------------
    # HT=직사각형 → Vh로 필요한 면적 → chord = S_h / b_h
    def _ht_chord_from_Vh_rect(lh, span):
        S_req = (Vh_tgt * Sw * cbar) / max(eta_h * lh, 1e-9)
        return S_req / max(span, 1e-9)

    l_h = float(np.clip(lh_frac_guess * L_fuse, lh_min_frac * L_fuse, lh_max_frac * L_fuse))
    for _ in range(int(max_iter)):
        c_try = _ht_chord_from_Vh_rect(l_h, b_h)
        if cmin_h <= c_try <= cmax_h:
            break
        if c_try > cmax_h:   # chord가 큼 → l 증가
            l_h = min(l_h * 1.08, lh_max_frac * L_fuse)
        else:                # chord가 작음 → l 감소
            l_h = max(l_h * 0.92, lh_min_frac * L_fuse)

    # VT 루트 QC 하한(간섭회피)로 인한 l_clr 강제, c_tip_v = c_ht_rect 로 묶어 고정점 수렴
    for _ in range(10):
        c_ht_rect = float(np.clip(_ht_chord_from_Vh_rect(l_h, b_h), cmin_h, cmax_h))
        c_tip_v   = c_ht_rect                              # 조건 1) c_HT == c_VT_tip
        c_root_v  = float(c_tip_v / max(t_v, 1e-9))

        x_root_QC_min = x_clear_min + 0.25 * c_root_v
        l_clr = x_root_QC_min - x_ref

        l_common = max(l_h, l_clr)
        if abs(l_common - l_h) < 1e-6:
            l_h = l_common
            break
        l_h = l_common

    # 공통 테일암 확정
    l = float(l_h)
    x_QC_common = x_ref + l                                # HT/VT QC x

    # ---------------- 5) VT 스팬 & 스윕 ----------------
    # Vv로 필요한 VT 합산 면적
    S_v_req = (Vv_tgt * Sw * bw) / max(eta_v * l, 1e-9)
    avg_c_v = 0.5 * (c_root_v + c_tip_v)
    b_v_vv  = S_v_req / max(avg_c_v, 1e-9)

    x_vt_QC_root = max(x_QC_common, x_root_QC_min)         # 간섭 하한 재확인
    x_ht_QC_tip  = x_QC_common

    # (a) 사용자 스윜 고정 —> 정렬 강제 span 먼저 계산
    if user_sweep_deg is not None:
        sweep_deg = float(np.clip(float(user_sweep_deg), sweep_min_deg, sweep_max_deg))
        sweep_rad = np.deg2rad(sweep_deg)
        tan_sw    = max(np.tan(sweep_rad), 1e-9)
        # 정렬 강제: VT tip QC = VT root QC + b_v * tan(sweep) = HT tip QC
        b_v_align = max((x_ht_QC_tip - x_vt_QC_root) / tan_sw, 1e-4)
        # Vv 충족도 보장: 둘 중 큰 값 채택
        b_v = max(b_v_align, b_v_vv)
        S_v_req = avg_c_v * b_v                               # 면적 갱신(보고/지표용)
    else:
        # (b) 자동: Vv로 얻은 b_v_vv에서 필요한 스윕 추정 → 한계 밖이면 스윕을 클램프하고 span 재조정
        sweep_req = np.rad2deg(np.arctan2(max(x_ht_QC_tip - x_vt_QC_root, 0.0),
                                          max(b_v_vv, 1e-9)))
        if sweep_min_deg <= sweep_req <= sweep_max_deg:
            sweep_deg = float(sweep_req)
            b_v = b_v_vv
        else:
            sweep_deg = float(np.clip(sweep_req, sweep_min_deg, sweep_max_deg))
            sweep_rad = np.deg2rad(sweep_deg)
            tan_sw    = max(np.tan(sweep_rad), 1e-9)
            b_v = max((x_ht_QC_tip - x_vt_QC_root) / tan_sw, 1e-4)
            S_v_req = avg_c_v * b_v
            


    # >>> 추가: 사용자 스윕 지정 시 VT를 x-방향으로 슬라이드해 HT 팁과 정렬@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    if user_sweep_deg is not None:
        sweep_rad = np.deg2rad(sweep_deg)
        tan_sw    = max(np.tan(sweep_rad), 1e-9)

        # HT 팁의 1/4현 x (직사각형 HT라 QC는 span 전역 동일)
        x_ht_QC_tip  = x_QC_common

        # 목표: x_vt_QC_root_new + b_v * tan(sweep) == x_ht_QC_tip
        x_vt_QC_root_target = x_ht_QC_tip - b_v * tan_sw

        # 충돌 여유 하한은 반드시 유지
        x_vt_QC_root = max(x_vt_QC_root_target, x_root_QC_min)
    else:
        # 기존 동작(루트 QC는 공통 l 또는 충돌하한에 맞춤)
        x_vt_QC_root = max(x_QC_common, x_root_QC_min)
    # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    

    # ---------------- 6) 최종 면적/AR을 chord·span에서 역산(정합 강제) ----------------
    c_ht = float(c_tip_v)                     # HT 직사각형 chord (== VT tip chord)
    S_h  = c_ht * b_h
    AR_h = (b_h**2) / max(S_h, 1e-9)

    S_v_side  = 0.5 * (c_root_v + c_tip_v) * b_v
    AR_v_side = (b_v**2) / max(S_v_side, 1e-9)
    MAC_v     = (2.0/3.0) * c_root_v * (1.0 + t_v + t_v**2) / (1.0 + t_v)  # 보고용

    # ---------------- 7) 위치(origin) ----------------
    # HT 루트 LE
    x_ht_root_LE = x_QC_common - 0.25 * c_ht
    y_ht_root    = 0.0
    z_ht_plane   = z_w + b_v
    ht_origin = [x_ht_root_LE, y_ht_root, z_ht_plane]

    # VT 루트 LE (좌/우)
    x_vt_root_LE = x_vt_QC_root - 0.25 * c_root_v
    vtR_origin = [x_vt_root_LE, float(y_R_sel), float(z_w)]
    vtL_origin = [x_vt_root_LE, float(y_L_sel), float(z_w)]

    # ---------------- 8) 패키징 ----------------
    stab = Data()

    # HT (직사각형)
    ht = Data()
    ht.tag                      = 'horizontal_tail'
    ht.area                     = float(S_h)                  # wing_planform 입력용
    ht.span                     = float(b_h)                  # (보고용)
    ht.root_chord               = float(c_ht)                 # (보고용)
    ht.tip_chord                = float(c_ht)                 # (보고용)
    ht.aspect_ratio             = float(AR_h)
    ht.taper                    = 1.0
    ht.sweeps = Data(); ht.sweeps.quarter_chord = 0.0
    ht.thickness_to_chord       = float(getattr(params, 'ht_t_c', 0.12))
    ht.dihedral                 = float(getattr(params, 'ht_dihedral_deg', 0.0))
    ht.origin                   = [ht_origin]
    ht.tail_arm_QC_x            = float(x_QC_common)
    ht.y_center                 = float(y_center_ht)
    ht.SM_achieved              = float(eta_h * (S_h * l) / max(Sw * cbar, 1e-9))
    stab.horizontal = ht

    # VT (개별) — 태그 소문자 고정(분석기 내부 키와 일치)
    def _vt_side(tag, origin):
        v = Data()
        v.tag                      = tag
        v.area                     = float(S_v_side)          # wing_planform 입력용
        v.height                   = float(b_v)
        v.root_chord               = float(c_root_v)          # (보고용)
        v.tip_chord                = float(c_tip_v)           # (보고용) == c_ht
        v.aspect_ratio             = float(AR_v_side)
        v.taper                    = float(t_v)
        v.sweeps = Data(); v.sweeps.quarter_chord = float(sweep_deg)
        v.thickness_to_chord       = float(getattr(params, 'vt_t_c', 0.12))
        v.dihedral                 = 0.0
        v.origin                   = [origin]
        v.tail_arm_QC_x            = float(x_vt_QC_root)
        v.MAC                      = float(MAC_v)             # (보고용)
        v.x_root_LE                = float(x_vt_root_LE)      # (검증용)
        v.x_clear_min              = float(x_clear_min)       # (검증용)
        return v

    stab.vertical_R = _vt_side('vertical_tail_r', vtR_origin)
    stab.vertical_L = _vt_side('vertical_tail_l', vtL_origin)

    # VT 합산(보고용)
    vt_c = Data()
    vt_c.tag                      = 'vertical_tail_pair'
    vt_c.area                     = float(2.0 * S_v_side)
    vt_c.height                   = float(b_v)
    vt_c.root_chord               = float(c_root_v)
    vt_c.tip_chord                = float(c_tip_v)
    vt_c.aspect_ratio             = float((b_v**2) / max(2.0 * S_v_side, 1e-9))
    vt_c.taper                    = float(t_v)
    vt_c.sweeps = Data(); vt_c.sweeps.quarter_chord = float(sweep_deg)
    vt_c.thickness_to_chord       = float(getattr(params, 'vt_t_c', 0.12))
    vt_c.origin_root_LE_x         = float(x_vt_root_LE)
    vt_c.tail_arm_QC_x            = float(x_vt_QC_root)
    vt_c.Cn_beta_achieved         = float(eta_v * ((2.0 * S_v_side) * l) / max(Sw * bw, 1e-9))
    vt_c.x_clear_min              = float(x_clear_min)
    vt_c.MAC                      = float(MAC_v)
    stab.vertical = vt_c

    # --- 간단 요약 출력 ---
    try:
        ht_o = ht.origin[0] if hasattr(ht, 'origin') and len(ht.origin) > 0 else [x_ht_root_LE, 0.0, z_ht_plane]
        sweep_deg_print = float(getattr(vt_c.sweeps, 'quarter_chord', sweep_deg))
        _log(f"[stabilizer] HT: span={b_h:.3f} m, c_ht={c_ht:.3f} m, S_h={S_h:.3f} m^2, AR_h={AR_h:.2f}, origin=({ht_o[0]:.3f},{ht_o[1]:.3f},{ht_o[2]:.3f}); "
             f"VT pair: S={vt_c.area:.3f} m^2, height={vt_c.height:.3f} m, c_root={vt_c.root_chord:.3f} m, c_tip={vt_c.tip_chord:.3f} m, sweep={sweep_deg_print:.1f} deg, l={l:.3f} m")
    except Exception:
        pass

    return stab