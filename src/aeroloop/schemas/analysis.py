from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class AerodynamicsAnalysisRequest(BaseModel):
    geometry_vsp3_path: str = Field(..., description="Path to the .vsp3 geometry file")
    analysis_type: str = Field("mass_props", description="Type of analysis: 'mass_props', 'vspaero', etc.")

class AerodynamicsAnalysisResult(BaseModel):
    status: str = Field(..., description="'success' or 'failed'")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Key aerodynamic or mass metrics")
    error: Optional[str] = None
    note: Optional[str] = None
