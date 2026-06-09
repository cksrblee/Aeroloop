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
            
            if request.analysis_config.run_vspaero:
                # 4. Compute Geometry
                runner.run_compute_geometry()
                
                # 5. Run Sweep
                with tempfile.TemporaryDirectory() as temp_dir:
                    log_file = os.path.join(temp_dir, "vspaero.log")
                    
                    sweep_res_id = runner.run_vspaero_sweep(
                        alpha_range=request.analysis_config.angle_of_attack_deg,
                        mach_range=[0.0] if not request.analysis_config.speed_mps else request.analysis_config.speed_mps, # Simplified Mach for PoC
                        geom_set=0,
                        wing_id=wing_id,
                        redirect_file=log_file
                    )
                    
                    # 6. Parse Results
                    parsed_data = parse_vspaero_results(runner.vsp, sweep_res_id)
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
