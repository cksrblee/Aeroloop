## @ingroup Methods-Sizing
# sizing_boom.py 

# Created:  09.09 2025, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import numpy as np
import SUAVE

# ======================================================================
# sizing_boom.py
#  - Lift rotor 배치로부터 붐(Fuselage) 자동 생성
#  - 로터 수: 4 / 8 / 12 지원
#    * 4  : 측별 1개 라인 → 1개 붐(미익 지지)
#    * 8  : 측별 2개 라인 → 안쪽은 미익 지지, 바깥은 모터만 지지
#    * 12 : 측별 3개 라인 → 안쪽 2개는 미익 지지, 바깥은 모터만 지지
#  - 끝단 형상: 원통 직경 일정 + 앞/뒤 돔(cap) 길이
#  - SUAVE.Components.Fuselages.Fuselage 리스트 반환
# ======================================================================
def sizing_boom(params, main_wing, stabilizer, lift_rotors):
    """
    입력
      - params
          boom_diameter_frac_of_lift_rotor_D : (선택) 로터 지름 대비 붐 지름 비
          boom_diameter_m                    : (선택) 고정 붐 지름 [m] (frac 미지정 시 사용)
          boom_diameter_min_m                : (선택) 붐 지름 하한 [m], 기본 0.05
          boom_nose_len_m                    : (선택) 앞 돔 길이 [m], 기본 0.20
          boom_tail_len_m                    : (선택) 뒤 돔 길이 [m], 기본 0.20
          boom_min_total_len_m               : (선택) 최소 전체 길이 [m], 기본 0.50
      - main_wing
          .origin[[x,y,z]] : 날개 루트 LE 기준 → 붐 z 기준에 사용
      - stabilizer
          .vertical_R / .vertical_L  중 하나에
              x_root_LE, root_chord  가 있으면 이를 사용해 루트 TE x 계산
          (없으면 수평미익의 tail_arm_QC_x 를 받아서 보수적 폴백)
      - lift_rotors : list of Lift_Rotor (origin, tip_radius 필수)

    반환
      - list[SUAVE.Components.Fuselages.Fuselage]
    """
    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)

    # ---------------- 0) 붐 지름/형상 상수 ----------------
    frac_D  = getattr(params, 'boom_diameter_frac_of_lift_rotor_D', None)
    d_fixed = float(getattr(params, 'boom_diameter_m', 0.15))
    d_min   = float(getattr(params, 'boom_diameter_min_m', 0.05))

    nose_len = float(getattr(params, 'boom_nose_len_m', 0.20))
    tail_len = float(getattr(params, 'boom_tail_len_m', 0.20))
    min_len  = float(getattr(params, 'boom_min_total_len_m', 0.50))

    # ---------------- 1) 붐 z 기준 (날개 z) ----------------
    if hasattr(main_wing, "origin") and main_wing.origin and len(main_wing.origin[0]) >= 3:
        z_boom = float(main_wing.origin[0][2])
    else:
        z_boom = 0.0

    # ---------------- 2) 로터 수 / 측별 y-라인 추출 ----------------
    N_rot = len(lift_rotors)
    if N_rot not in (4, 8, 12):
        raise ValueError("현재 붐 사이징은 로터 수 4/8/12에 최적화되어 있습니다.")

    # 로직: 전/후 2열, 측별(±y) 여러 'y-라인' 존재 → 각 라인에서 x_front, x_back 산출
    right = [r for r in lift_rotors if r.origin[0][1] > 0]
    left  = [r for r in lift_rotors if r.origin[0][1] < 0]

    def _lines_for_side(rotors_side):
        """해당 측에서 |y| 기준으로 라인 정렬 + (front/back x, 대표 D_rot) 뽑기"""
        if not rotors_side:
            return []

        # 고유 y 값(라인) 정렬: |y| 오름차순 (inner → outer)
        y_vals = sorted({round(float(r.origin[0][1]), 6) for r in rotors_side}, key=lambda v: abs(v))

        lines = []
        for y in y_vals:
            members = [r for r in rotors_side if abs(float(r.origin[0][1]) - y) < 1e-6]
            members = sorted(members, key=lambda r: float(r.origin[0][0]))  # x로 정렬
            x_front = float(members[0].origin[0][0])        # 가장 앞
            x_back  = float(members[-1].origin[0][0])       # 가장 뒤
            # 해당 라인의 대표 로터 지름(중앙값)
            d_list = []
            for r in members:
                R = float(getattr(r, 'tip_radius', 0.0))
                if R > 0.0: d_list.append(2.0 * R)
            D_rep = float(np.median(d_list)) if d_list else 0.0
            lines.append(dict(y=float(y), x_front=x_front, x_back=x_back, D_rep=D_rep))
        return lines

    lines_R = _lines_for_side(right)  # e.g., 4→1개, 8→2개, 12→3개
    lines_L = _lines_for_side(left)

    # ---------------- 3) 수직미익 루트 TE x (측별) ----------------
    def _vt_root_TE_x(side):
        vt = getattr(stabilizer, 'vertical_R' if side=='R' else 'vertical_L', None)
        if vt is None:
            vt = getattr(stabilizer, 'vertical', None)  # pair (좌우 동일 가정)
        # 선호: x_root_LE + root_chord
        if vt is not None and hasattr(vt, 'x_root_LE') and hasattr(vt, 'root_chord'):
            return float(vt.x_root_LE) + float(vt.root_chord)
        # 보수적 폴백: 수평미익 QC x
        ht = getattr(stabilizer, 'horizontal', None)
        if ht is not None and hasattr(ht, 'tail_arm_QC_x'):
            return float(ht.tail_arm_QC_x) + 0.25 * float(getattr(ht, 'root_chord', getattr(ht, 'tip_chord', 0.0)))
        # 최후 폴백: 해당 측 라인의 x_back
        side_lines = lines_R if side=='R' else lines_L
        return max((ln['x_back'] for ln in side_lines), default=0.0)

    x_te_R = _vt_root_TE_x('R')
    x_te_L = _vt_root_TE_x('L')

    # ---------------- 4) 붐 지름 결정 (라인 대표 D 기반) ----------------
    # 전체 로터에서 대표 D 취함 → frac_D가 있으면 스케일, 아니면 d_fixed
    all_D = []
    for r in lift_rotors:
        R = float(getattr(r, 'tip_radius', 0.0))
        if R > 0.0: all_D.append(2.0 * R)
    D_ref = float(np.median(all_D)) if all_D else d_fixed

    if frac_D is not None:
        d_boom = float(frac_D) * D_ref
    else:
        d_boom = d_fixed
    d_boom = max(d_boom, d_min)
    r_boom = 0.5 * d_boom

    # ---------------- 5) 라인 역할 결정 (미익 지지 개수) ----------------
    # 측별 '안쪽부터' tail-support 라인을 몇 개 쓸지 결정
    if N_rot == 4:
        n_tail_support_per_side = 1
    elif N_rot == 8:
        n_tail_support_per_side = 1
    elif N_rot == 12:
        n_tail_support_per_side = 1
    else:
        n_tail_support_per_side = 1

    # ---------------- 6) 붐 생성 헬퍼 ----------------
    def _make_boom(tag, x_front, x_back, y):
        """x축 정렬 붐 1개 생성 (전방점 origin) — 앞/뒤 돔"""
        if x_back < x_front:
            x_front, x_back = x_back, x_front
        length_total = max(x_back - x_front, min_len)

        boom = SUAVE.Components.Fuselages.Fuselage()
        boom.tag                                = tag
        boom.origin                             = [[float(x_front), float(y), float(z_boom)]]
        boom.lengths.nose                       = float(nose_len)
        boom.lengths.tail                       = float(tail_len)
        boom.lengths.total                      = float(length_total)

        # 원통 단면(전 구간 일정)
        boom.width                              = float(d_boom)
        boom.heights.maximum                    = float(d_boom)
        boom.heights.at_quarter_length          = float(d_boom)
        boom.heights.at_three_quarters_length   = float(d_boom)
        boom.heights.at_wing_root_quarter_chord = float(d_boom)
        boom.effective_diameter                 = float(d_boom)

        # 간단한 원통 근사 면적/지표
        cyl_len = max(length_total - (nose_len + tail_len), 0.0)
        boom.areas.wetted                       = 2.0 * np.pi * r_boom * (cyl_len + nose_len + tail_len*0.8)
        boom.areas.front_projected              = np.pi * r_boom**2

        boom.fineness = SUAVE.Core.Data()
        boom.fineness.nose                      = float(d_boom / max(nose_len, 1e-6))
        boom.fineness.tail                      = float(d_boom / max(tail_len, 1e-6))

        return boom

    # ---------------- 7) 측별로 붐 생성 ----------------
    def _build_side(tag_prefix, lines_side, x_te_side):
        booms = []
        # 안쪽→바깥쪽 순서로 index 부여
        for idx, ln in enumerate(lines_side, start=1):
            y = ln['y']
            x_front = ln['x_front']
            # 미익 지지 대상인지 판단
            if idx <= n_tail_support_per_side:
                x_back = max(ln['x_back'], x_te_side)  # 미익 루트 TE까지
                role = 'tail'
            else:
                x_back = ln['x_back']                  # 모터만
                role = 'motor'
            tag = f"{tag_prefix}_{role}_{idx}"
            booms.append(_make_boom(tag, x_front, x_back, y))
        return booms

    booms = []
    booms += _build_side('boom_R', lines_R, x_te_R)
    booms += _build_side('boom_L', lines_L, x_te_L)

    # 디버그 출력(선택)
    _log(f"[booms] N_rot={N_rot}, d_boom={d_boom:.3f} m, "
         f"R_lines={len(lines_R)}(tail {n_tail_support_per_side}), "
         f"L_lines={len(lines_L)}(tail {n_tail_support_per_side})")
 
    return booms
