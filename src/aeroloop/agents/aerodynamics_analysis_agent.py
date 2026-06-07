import os
import sys
from typing import Dict, Any

from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.analysis import AerodynamicsAnalysisRequest, AerodynamicsAnalysisResult

class AerodynamicsAnalysisAgent(BaseAIAgent):
    """
    Executes low-fidelity aerodynamic and mass properties analysis on the generated geometry.
    """
    def __init__(self, **kwargs):
        super().__init__(
            name="Aerodynamics Analysis Agent",
            description="Analyzes OpenVSP geometries to compute mass, volume, and aerodynamic properties.",
            **kwargs
        )

    def process_request(self, request: AerodynamicsAnalysisRequest) -> AerodynamicsAnalysisResult:
        try:
            import openvsp as vsp
        except ImportError:
            return AerodynamicsAnalysisResult(status="failed", error="OpenVSP Python API is not available.")

        if not os.path.exists(request.geometry_vsp3_path):
            return AerodynamicsAnalysisResult(status="failed", error=f"File not found: {request.geometry_vsp3_path}")

        try:
            vsp.VSPRenew()
            vsp.ReadVSPFile(request.geometry_vsp3_path)
            
            metrics = {}
            if request.analysis_type == "mass_props":
                # Compute Mass Properties
                vsp.ComputeMassProps(0, 100, 0)
                results = vsp.GetResults("Mass_Props")
                try:
                    metrics["Volume"] = round(vsp.GetDoubleResults(results, "Total_Volume")[0], 2)
                    metrics["Wetted_Area"] = round(vsp.GetDoubleResults(results, "Total_Wetted_Area")[0], 2)
                    metrics["CG_X"] = round(vsp.GetDoubleResults(results, "CG_X")[0], 2)
                except Exception as e:
                    return AerodynamicsAnalysisResult(status="failed", error=f"Failed to extract mass props: {e}")
            else:
                return AerodynamicsAnalysisResult(status="failed", error=f"Unsupported analysis type: {request.analysis_type}")
                
            return AerodynamicsAnalysisResult(status="success", metrics=metrics)
            
        except Exception as e:
            return AerodynamicsAnalysisResult(status="failed", error=str(e))

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
