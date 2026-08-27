## @ingroup Methods-Sizing
# sizing_fuselage.py 

# Created:  09.09 2025, Chanyoung Joo
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
from SUAVE.Core import Data
import numpy as np

# ======================================================================
#  sizing_fuselage.py 
#  - Fuselage sizing driven only by cabin geometry + length ratio
#  - Legacy / fine-tuning params removed
#  - Outputs SUAVE-friendly Data object (segments for Lofted_Body)
# ======================================================================
def sizing_fuselage(requirements, params):
    """
    좌석/복도/여유치 기반 캐빈 단면 계산 → 등가직경 비율(len_to_cabinDia_ratio)로 총길이 결정 →
    노즈/캐빈/테일 종분할(fuse_nose_frac, fuse_tail_frac; 캐빈 비율은 자동계산) →
    SUAVE Lofted_Body용 세그먼트 생성.

    [필수 입력]
      requirements.number_of_seats              [-]
      params.seat_width_m                       [m]
      params.aisle_width_m                      [m]
      params.seat_pitch_m                       [m]
      params.luggage_allow_m                    [m]
      params.cabin_head_clear_m                 [m]
      params.floor_ceiling_thk_m                [m]
      params.wall_thickness_m                   [m]
      params.len_to_cabinDia_ratio              [-]   # 총길이 / 등가직경(√(W*H))
      params.fuse_nose_frac                     [-]   # 노즈 길이 비
      params.fuse_tail_frac                     [-]   # 테일 길이 비

    [선택 입력]
      params.fuse_segments_n                    [-]   # Lofted_Body 세그먼트 개수(기본 12)

    반환(Data):
      fus.tag = 'fuselage_sizing'
      fus.lengths.total/nose/cabin/tail [m], fus.width [m], fus.heights.maximum [m]
      fus.areas.front_projected/wetted [m^2], fus.effective_diameter [m]
      fus.fineness.nose/tail [-], fus.segments (Lofted_Body_Segment용 리스트)
      fus.params_used.(fuse_nose_frac/fuse_cabin_frac/fuse_tail_frac)
    """

    # 로깅 헬퍼: params.Log_print이 True일 때만 출력
    def _log(*args, **kwargs):
        if getattr(params, 'Log_print', True):
            print(*args, **kwargs)

    # ---------------- 0) 필수 입력 로드 ----------------
    N_seats   = int(requirements.number_of_seats)

    seat_w    = float(params.seat_width_m)
    aisle_w   = float(params.aisle_width_m)
    seat_pitch= float(params.seat_pitch_m)
    wall_clr  = float(params.luggage_allow_m)
    head_clr  = float(params.cabin_head_clear_m)
    floor_thk = float(params.floor_ceiling_thk_m)
    wall_thk  = float(params.wall_thickness_m)

    L_ratio   = float(params.len_to_cabinDia_ratio)
    f_n       = float(params.fuse_nose_frac)
    f_t       = float(params.fuse_tail_frac)

    # 선택 입력
    Nseg      = int(getattr(params, 'fuse_segments_n', 12))
    differential_pressure = float(getattr(params, 'differential_pressure', 0.0))  # [Pa], 동체 압력차(필요시)

    # ---------------- 검증/가드 ----------------
    if not (0.0 < f_n < 0.9):
        raise ValueError("fuse_nose_frac 범위 오류(0~0.9).")
    if not (0.0 < f_t < 0.9):
        raise ValueError("fuse_tail_frac 범위 오류(0~0.9).")
    if (f_n + f_t) >= 0.98:
        raise ValueError("노즈+테일 비율 합이 과도합니다(합<0.98 권장).")

    f_c = 1.0 - (f_n + f_t)
    if f_c <= 0.02:
        raise ValueError("자동계산된 fuse_cabin_frac이 너무 작습니다.")

    # ---------------- 1) 캐빈 단면/길이 ----------------
    # 좌석 배열: 2-열(2 abreast) 가정
    seats_abreast = 2
    n_rows = int(np.ceil(N_seats / seats_abreast))

    # 캐빈 최대 폭/높이
    cabin_width  = seats_abreast*seat_w + aisle_w + 2.0*(wall_thk + wall_clr)  # [m]
    seated_h     = 1.00
    cabin_height = max(seated_h + floor_thk + head_clr, 1.20)                  # [m]
    cabin_len    = n_rows * seat_pitch + 0.50                                   # [m]

    # 등가 직경
    eff_diam = float(np.sqrt(cabin_width * cabin_height))

    # ---------------- 2) 총 길이(단일 드라이버) ----------------
    # 캐빈이 반드시 들어가도록 L_total_min 보장
    L_total_min = cabin_len / f_c
    L_total     = max(L_ratio * eff_diam, L_total_min)

    L_nose  = f_n * L_total
    L_cabin = f_c * L_total
    L_tail  = f_t * L_total

    # ---------------- 3) 형상 함수(필수값만; 내부 상수로 단순화) ----------------
    # 노즈/테일 기본 곡률만 반영(튜닝 파라미터 제거)
    nose_exp   = 0.60
    tail_w_end = 0.50
    tail_h_end = 0.45
    tail_exp   = 1.40

    def shape_w(x_norm: float) -> float:
        """정규화 길이 x_norm∈[0,1]에서 폭 스케일(캐빈=1)."""
        if x_norm <= f_n:  # 노즈
            xi   = (x_norm / f_n)**(0.9 * nose_exp) if f_n > 1e-9 else 1.0
            base = 0.40 + (1.0 - 0.40) * xi     # 노즈 팁 폭비 0.40 → 캐빈 1.0
            return base
        elif x_norm <= (f_n + f_c):  # 캐빈
            return 1.0
        else:  # 테일
            xt = (x_norm - (f_n + f_c)) / f_t if f_t > 1e-9 else 1.0  # 0~1
            return 1.0 - (1.0 - tail_w_end) * (xt**tail_exp)

    def shape_h(x_norm: float) -> float:
        """정규화 길이 x_norm∈[0,1]에서 높이 스케일(캐빈=1)."""
        if x_norm <= f_n:  # 노즈
            xi   = (x_norm / f_n)**(0.9 * nose_exp) if f_n > 1e-9 else 1.0
            base = 0.34 + (1.0 - 0.34) * xi     # 노즈 팁 높이비 0.34 → 캐빈 1.0
            return base
        elif x_norm <= (f_n + f_c):  # 캐빈
            return 1.0
        else:  # 테일
            xt = (x_norm - (f_n + f_c)) / f_t if f_t > 1e-9 else 1.0
            return 1.0 - (1.0 - tail_h_end) * (xt**tail_exp)

    width_at  = lambda x: shape_w(x) * cabin_width
    height_at = lambda x: shape_h(x) * cabin_height

    # ---------------- 4) Lofted_Body 세그먼트 생성 ----------------
    px = np.linspace(0.0, 1.0, Nseg)  # percent_x_location
    pz = np.zeros_like(px)            # 중심선 z 오프셋(0 고정)

    segs = []
    for i, x in enumerate(px):
        s = Data()
        s.tag                 = f'segment_{i}'
        s.percent_x_location  = float(x)
        s.percent_z_location  = float(pz[i])
        s.width               = float(width_at(x))
        s.height              = float(height_at(x))
        segs.append(s)

    # ---------------- 5) 간이 치수/면적 계산 ----------------
    area_front = (np.pi/4.0) * cabin_width * cabin_height
    a, b = cabin_width/2.0, cabin_height/2.0
    ellipse_perim = float(np.pi * (3*(a+b) - np.sqrt((3*a+b)*(a+3*b))))
    wetted        = ellipse_perim * L_total * 0.95   # 타원둘레×L×경험계수

    # ---------------- 6) 패키징 ----------------
    fus = Data()
    fus.tag = 'fuselage_sizing'

    fus.seats_abreast = seats_abreast

    fus.lengths = Data()
    fus.lengths.total = float(L_total)
    fus.lengths.nose  = float(L_nose)
    fus.lengths.cabin = float(L_cabin)
    fus.lengths.tail  = float(L_tail)

    fus.width = float(cabin_width)
    fus.heights = Data()
    fus.heights.maximum = float(cabin_height)

    fus.areas = Data()
    fus.areas.front_projected = float(area_front)
    fus.areas.wetted          = float(wetted)

    fus.effective_diameter = float(eff_diam)
    fus.fineness = Data()
    fus.fineness.nose = float(L_nose / max(eff_diam, 1e-9))
    fus.fineness.tail = float(L_tail / max(eff_diam, 1e-9))

    fus.segments = segs

    fus.params_used = Data()
    fus.params_used.fuse_nose_frac  = float(f_n)
    fus.params_used.fuse_cabin_frac = float(f_c)
    fus.params_used.fuse_tail_frac  = float(f_t)
    fus.differential_pressure = float(differential_pressure)

    # --- human-friendly single-line summary (예: lift rotor 로그 스타일) ---
    try:
        _log(
            f"[fuselage sizing] seats={N_seats}, "
            f"L_total={fus.lengths.total:.3f} m (nose={fus.lengths.nose:.3f}, cabin={fus.lengths.cabin:.3f}, tail={fus.lengths.tail:.3f}), "
            f"width={fus.width:.3f} m, height={fus.heights.maximum:.3f} m, "
            f"eff_diam={fus.effective_diameter:.3f} m, front_area={fus.areas.front_projected:.3f} m^2, wetted={fus.areas.wetted:.3f} m^2, "
            f"fineness(n/t)={fus.fineness.nose:.2f}/{fus.fineness.tail:.2f}, diffP={fus.differential_pressure:.1f} Pa"
        )
    except Exception:
        pass

    return fus
