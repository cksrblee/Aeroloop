import os
import uuid
import tempfile
from typing import Dict, Any

from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.aerodynamics import (
    AerodynamicsAnalysisRequest,
    AerodynamicsAnalysisResult,
    AeroAnalysisSetup,
    AerodynamicSummary,
    AeroFeasibilityAssessment,
    AeroAnalysisArtifacts
)
from aeroloop.aerodynamics.vspaero_runner import VSPAeroRunner
from aeroloop.aerodynamics.vspaero_result_parser import parse_vspaero_results
from aeroloop.aerodynamics.mass_properties_runner import run_mass_properties
from aeroloop.schemas.common import ErrorInfo

class AerodynamicsAnalysisAgent(BaseAIAgent):
    """
    Executes low-fidelity aerodynamic and mass properties analysis on the generated geometry using OpenVSP/VSPAERO.
    """
    def __init__(self, **kwargs):
        super().__init__(
            name="Aerodynamics Analysis Agent",
            description="Analyzes OpenVSP geometries to compute mass, volume, and aerodynamic properties using VSPAERO.",
            **kwargs
        )

    def process_request(self, request: AerodynamicsAnalysisRequest) -> AerodynamicsAnalysisResult:
        result = AerodynamicsAnalysisResult(
            aero_analysis_result_id=f"AERO-RESULT-{uuid.uuid4().hex[:8]}",
            aero_analysis_request_id=request.aero_analysis_request_id,
            run_id=request.run_id,
            mission_id=request.mission_id,
            candidate_id=request.candidate_id,
            status="failed"
        )
        
        # 1. Validate Geometry Input
        vsp3_path = request.geometry_artifacts.vsp3_file_path
        if not os.path.exists(vsp3_path):
            result.errors.append(ErrorInfo(error_id="GEOMETRY_FILE_NOT_FOUND", module_name="AerodynamicsAnalysisAgent", message=f"File not found: {vsp3_path}", recoverable=False))
            return result
            
        try:
            # 2. Initialize VSPAeroRunner
            runner = VSPAeroRunner() # Attempts to load vsp module
            runner.load_or_generate_vsp3(vsp3_path)
            
            # Setup Analysis Record
            result.analysis_setup = AeroAnalysisSetup(
                analysis_backend=request.analysis_config.analysis_backend,
                analysis_fidelity=request.analysis_config.analysis_fidelity,
                aircraft_type=request.aircraft_candidate.aircraft_type,
                angle_of_attack_deg=request.analysis_config.angle_of_attack_deg,
                sideslip_deg=request.analysis_config.sideslip_deg,
                speed_mps=request.analysis_config.speed_mps,
                altitude_m=request.analysis_config.altitude_m
            )
            
            # Resolve Reference Geometry (Optional depending on how sizing passed it)
            # For simplicity, fallback to OpenVSP's wing if not explicitly given
            wing_name = "Wing"
            wing_id = None
            geom_ids = runner.vsp.FindGeomsWithName(wing_name)
            if geom_ids:
                wing_id = geom_ids[0]
            else:
                # Find any wing
                all_geoms = runner.vsp.FindGeoms()
                for gid in all_geoms:
                    if runner.vsp.GetGeomTypeName(gid) == "Wing":
                        wing_id = gid
                        break
            
            if request.analysis_config.run_mass_properties:
                # 3. Run Mass Properties
                mass_result = run_mass_properties(runner.vsp, num_slices=request.analysis_config.mass_property_num_slices)
                result.mass_properties = mass_result
                if mass_result.warnings:
                    result.warnings.extend(mass_result.warnings)
                    
                if not mass_result.mass_analysis_available:
                    result.errors.append(ErrorInfo(error_id="MASS_PROPS_FAILED", module_name="AerodynamicsAnalysisAgent", message="Mass properties computation failed or returned empty results.", recoverable=False))
            
            if request.analysis_config.run_vspaero:
                # 5. Run Sweep and Compute Geometry
                out_dir = request.output_directory
                os.makedirs(out_dir, exist_ok=True)
                
                # Copy VSP3 file to out_dir so OpenVSP generates output files here
                local_vsp3_path = os.path.join(out_dir, os.path.basename(vsp3_path))
                import shutil
                shutil.copy2(vsp3_path, local_vsp3_path)
                
                # Reload the VSP3 from the new location so its base path becomes out_dir
                runner.load_or_generate_vsp3(local_vsp3_path)
                
                log_file = os.path.join(out_dir, "vspaero.log")
                
                # Change CWD so vspaero binary (if it relies on CWD) and our parser look in out_dir
                old_cwd = os.getcwd()
                os.chdir(out_dir)
                
                try:
                    # 4. Compute Geometry
                    runner.run_compute_geometry()
                    
                    # Calculate Mach number (approximate, assuming sea level sound speed ~340 m/s)
                    mach_num = 0.0
                    if request.analysis_config.speed_mps:
                        speed = request.analysis_config.speed_mps
                        speed_val = speed[0] if isinstance(speed, list) else speed
                        mach_num = speed_val / 340.0
                        
                    base_name = os.path.basename(local_vsp3_path).replace(".vsp3", "")
                    
                    print("\n[AerodynamicsAnalysisAgent] Starting VSPAERO Solver... (OpenVSP blocking, please wait or tail the .history file in another terminal)")
                    
                    import signal
                    # OpenVSP C++ waitpid() hangs if Python's asyncio/multiprocessing intercepts SIGCHLD
                    try:
                        old_handler = signal.signal(signal.SIGCHLD, signal.SIG_DFL)
                    except Exception:
                        old_handler = None
                        
                    try:
                        sweep_res_id = runner.run_vspaero_sweep(
                            alpha_range=request.analysis_config.angle_of_attack_deg,
                            mach_range=[mach_num],
                            geom_set=0,
                            wing_id=wing_id,
                            redirect_file=log_file
                        )
                    finally:
                        if old_handler is not None:
                            signal.signal(signal.SIGCHLD, old_handler)
                    
                    runner.run_vsploads(base_name=base_name, cwd=".")
                        
                    # 6. Parse Results
                    parsed_data = parse_vspaero_results(runner.vsp, sweep_res_id, cwd=".")
                finally:
                    os.chdir(old_cwd)
                        
                    result.aerodynamic_coefficients = parsed_data.get("coefficients", [])
                    
                    if parsed_data.get("warnings"):
                        result.warnings.extend(parsed_data.get("warnings"))
                        
                    # Calculate basic summary
                    coeffs = result.aerodynamic_coefficients
                    if coeffs:
                        cd_min = min((c.cd for c in coeffs if c.cd is not None), default=None)
                        ld_ratios = [(c.cl / c.cd) for c in coeffs if c.cl is not None and c.cd is not None and c.cd > 0]
                        max_ld = max(ld_ratios) if ld_ratios else None
                        
                        result.aerodynamic_summary = AerodynamicSummary(
                            cd_min=cd_min,
                            max_lift_to_drag=max_ld
                        )
                        
                    # Write load distribution to CSV if present
                    import csv
                    if result.aerodynamic_coefficients:
                        csv_path = os.path.join(request.output_directory, "load_distribution.csv")
                        wrote_csv = False
                        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
                            writer = csv.writer(csvfile)
                            writer.writerow(["Case_ID", "Alpha_deg", "Y_Span_m", "Chord_m", "Area_m2", "Cl", "Cd", "Cm"])
                            for case in result.aerodynamic_coefficients:
                                if case.load_distribution:
                                    wrote_csv = True
                                    for ld in case.load_distribution:
                                        for y, ch, ar, cl, cd, cm in zip(ld.y_span, ld.chord, ld.area, ld.cl, ld.cd, ld.cm):
                                            writer.writerow([case.case_id, case.alpha_deg, y, ch, ar, cl, cd, cm])
                        if not wrote_csv:
                            if os.path.exists(csv_path):
                                os.remove(csv_path)
                        else:
                            if result.analysis_artifacts is None:
                                result.analysis_artifacts = AeroAnalysisArtifacts()
                            result.analysis_artifacts.load_distribution_csv_path = csv_path
                        
            # Determine Final Status
            if result.errors:
                result.status = "failed"
            elif result.warnings:
                result.status = "success_with_warnings"
            else:
                result.status = "success"
                
            return result
            
        except Exception as e:
            result.errors.append(ErrorInfo(error_id="RUNTIME_EXCEPTION", module_name="AerodynamicsAnalysisAgent", message=str(e), recoverable=False))
            result.status = "failed"
            return result

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        req_dict = state.get("analysis_request")
        if isinstance(req_dict, dict):
            req = AerodynamicsAnalysisRequest(**req_dict)
        elif isinstance(req_dict, AerodynamicsAnalysisRequest):
            req = req_dict
        else:
            state["analysis_result"] = None
            return state
            
        result = self.process_request(req)
        state["analysis_result"] = result
        return state
