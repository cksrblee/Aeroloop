"""
evtol_sizing_api.py

설명: 
evtol_sizing_main_v1.0.0.py 의 로직을 모듈화하여,
외부 시스템(예: aero 가상환경)에서 JSON 입출력을 통해 
사이징 루프를 실행할 수 있도록 만든 API 래퍼입니다.
"""

import sys
import json
import argparse
from pathlib import Path

try:
    import SUAVE
    # SUAVE 버전 검증 (2.5.2)
    try:
        assert SUAVE.__version__ == '2.5.2'
    except AssertionError:
        print(f"Warning: Expected SUAVE version 2.5.2, but found {SUAVE.__version__}")

    from SUAVE.Input_Output.Excel.Excel_Reader import mission_profile_reader, model_input_reader 
    from aeroloop.engineering.suave_evtol.Sizing.sizing_iteration import sizing_iteration
    from SUAVE.Analyses.setup_analyses import setup_analyses
    from SUAVE.Plots.make_plots import make_plots
    from aeroloop.engineering.suave_evtol.Missions.setup_mission import setup_mission
    SUAVE_AVAILABLE = True
    SUAVE_IMPORT_ERROR = None
except ImportError as e:
    SUAVE_AVAILABLE = False
    SUAVE_IMPORT_ERROR = str(e)


# 제약조건 해석 임포트 
# (주의: convert_sweep 등의 의존성 문제가 있을 경우 오류가 발생할 수 있습니다.)
try:
    from aeroloop.engineering.suave_evtol.Optimization.fixed_mode_Constraints_analysis import fixed_mode_Constraints_analysis
    from aeroloop.engineering.suave_evtol.Optimization.vtol_mode_Constraints_analysis import vtol_mode_Constraints_analysis
    CONSTRAINTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Constraints analysis modules are not fully available. ({e})")
    CONSTRAINTS_AVAILABLE = False


def load_inputs(base_path: Path, param_overrides: dict = None):
    """엑셀 파일로부터 요구도와 파라미터를 읽어옵니다. 필요 시 파라미터를 오버라이드 할 수 있습니다."""
    requirements, params = model_input_reader(base_path / "model_input.xlsx")
    mission_profile = mission_profile_reader(base_path / "mission_input_new.xlsx")
    
    # 기본 파라미터 오버라이드
    params.aspect_ratio                = 11.4     
    params.battery_power_margin_frac   = 0.5
    params.Log_print                   = True   
    
    # 외부 입력값(JSON)에 의한 오버라이드
    if param_overrides:
        for k, v in param_overrides.items():
            if hasattr(params, k):
                setattr(params, k, v)
                
    return requirements, params, mission_profile


def analyze_constraints(vehicle, requirements, params, plot=False):
    """제약 조건 분석을 수행합니다."""
    if not CONSTRAINTS_AVAILABLE:
        print("Skipping constraints analysis due to missing SUAVE modules.")
        return None, None
        
    fixed_opt_points = fixed_mode_Constraints_analysis(vehicle, requirements, params, plot=plot)
    vtol_opt_points  = vtol_mode_Constraints_analysis(vehicle, requirements, params, plot=plot)
    return fixed_opt_points, vtol_opt_points


def size_vehicle(requirements, params, mission_profile):
    """사이징 반복 루프를 실행하여 차량 형상과 MTOW를 계산합니다."""
    vehicle, MTOW = sizing_iteration(requirements, params, mission_profile)
    return vehicle, MTOW


def evaluate_mission(vehicle, params, mission_profile):
    """설계된 기체의 미션을 해석합니다."""
    analyses = setup_analyses(vehicle)
    analyses.finalize()
    mission  = setup_mission(params, vehicle, analyses, mission_profile)
    mission_result = mission.evaluate()
    return mission_result, analyses, mission


def run_sizing_workflow(base_path: Path, param_overrides: dict = None, plot: bool = False):
    """전체 사이징 워크플로우를 관장하는 메인 파이프라인 함수입니다."""
    # 1. 입력 로드
    requirements, params, mission_profile = load_inputs(base_path, param_overrides)
    
    # 2. 제약 조건 분석 (선택사항)
    vehicle = None
    analyze_constraints(vehicle, requirements, params, plot=plot)
    
    # 3. 사이징 반복 루프
    vehicle, MTOW = size_vehicle(requirements, params, mission_profile)
    
    # 4. 미션 해석
    mission_result, analyses, mission = evaluate_mission(vehicle, params, mission_profile)
    
    # 5. 결과 플로팅
    if plot:
        make_plots(mission_result, vehicle, show_plots=True)
        
    return vehicle, MTOW, mission_result


def cli_main():
    """CLI 환경에서 JSON 파라미터를 읽어 실행하는 엔트리포인트입니다."""
    parser = argparse.ArgumentParser(description="eVTOL Sizing API")
    parser.add_argument('--input', type=str, help="Path to input JSON file containing parameter overrides")
    parser.add_argument('--output', type=str, help="Path to output JSON file to save sizing results")
    parser.add_argument('--plot', action='store_true', help="Show plots after execution")
    args = parser.parse_args()

    base_path = Path(__file__).resolve().parent
    param_overrides = {}
    
    if args.input:
        with open(args.input, 'r') as f:
            param_overrides = json.load(f)
            
    if not SUAVE_AVAILABLE:
        output_data = {
            "status": "error",
            "message": f"SUAVE import failed: {SUAVE_IMPORT_ERROR}"
        }
    else:
        try:
            # 워크플로우 실행
            vehicle, MTOW, mission_result = run_sizing_workflow(
                base_path=base_path, 
                param_overrides=param_overrides, 
                plot=args.plot
            )
            
            # 출력 데이터 구성 (기본적으로 MTOW, 배터리 질량 등 주요 파라미터 반환)
            output_data = {
                "status": "success",
                "MTOW_kg": float(MTOW) if hasattr(MTOW, '__float__') else float(MTOW),
                "wing_area": float(vehicle.wings.main_wing.areas.reference) if vehicle and hasattr(vehicle, 'wings') else None,
                # 필요한 추가 결과 데이터가 있다면 여기에 매핑합니다.
            }
            
        except Exception as e:
            output_data = {
                "status": "error",
                "message": str(e)
            }
            print(f"Error during sizing workflow: {e}")
            # CLI 실행 중 에러가 발생하더라도 JSON 결과는 반환하여 호출 측에서 예외를 처리할 수 있게 함

        
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=4)
    else:
        # 출력 파일이 없으면 콘솔에 출력
        print(json.dumps(output_data, indent=4))


if __name__ == "__main__":
    cli_main()
