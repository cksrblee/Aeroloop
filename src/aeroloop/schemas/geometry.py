from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

VehicleType = Literal[
    "multirotor",
    "helicopter",
    "small_aircraft",
    "fixed_wing",
    "lift_cruise_vtol",
    "tiltrotor_vtol",
    "tiltwing_vtol",
    "compound_helicopter"
]

class ParameterSource(BaseModel):
    parameter_name: str
    source_type: str
    source_id: str

class ComplianceContext(BaseModel):
    ccl_item_ids: List[str] = []
    moc_candidates: List[str] = []

class GeometryExportOptions(BaseModel):
    export_vsp3: bool = True
    export_stl: bool = True
    export_step: bool = False
    export_iges: bool = False
    export_obj: bool = False
    export_preview_png: bool = True

class GeometryValidationOptions(BaseModel):
    validate_mesh: bool = True
    strict_watertight: bool = False
    check_bounding_box: bool = True

class GeometryDesignRequest(BaseModel):
    geometry_request_id: str
    run_id: str
    mission_id: str
    candidate_id: str
    configuration_id: Optional[str] = None

    vehicle_type: VehicleType
    geometry_template: str
    fidelity_level: Literal["conceptual", "low", "medium"] = "low"

    design_parameters: Dict[str, Any]
    parameter_sources: List[ParameterSource] = []

    compliance_context: Optional[ComplianceContext] = None
    export_options: GeometryExportOptions = Field(default_factory=GeometryExportOptions)
    validation_options: GeometryValidationOptions = Field(default_factory=GeometryValidationOptions)

    output_directory: str

class GeometryArtifacts(BaseModel):
    vsp3_file_path: Optional[str] = None
    stl_file_path: Optional[str] = None
    step_file_path: Optional[str] = None
    iges_file_path: Optional[str] = None
    obj_file_path: Optional[str] = None
    preview_png_path: Optional[str] = None
    geometry_manifest_path: Optional[str] = None

class GeometryComponent(BaseModel):
    component_id: str
    component_type: str
    name: str
    parameters: Dict[str, Any]

class MeshValidationReport(BaseModel):
    stl_exists: bool
    loadable_by_open3d: bool
    file_size_bytes: Optional[int] = None
    vertex_count: Optional[int] = None
    triangle_count: Optional[int] = None
    is_watertight: Optional[bool] = None
    bbox_dimensions_m: Optional[Dict[str, float]] = None
    validation_status: Literal["passed", "passed_with_warnings", "failed"]
    warnings: List[str] = []
    errors: List[str] = []

class TraceLink(BaseModel):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relation_type: str

class ComplianceArtifactLink(BaseModel):
    ccl_item_id: str
    moc_type: str
    artifact_ids: List[str]
    evidence_role: str

class ErrorInfo(BaseModel):
    error_code: str
    message: str
    field: Optional[str] = None
    recoverable: bool = False

class GeometryDesignResult(BaseModel):
    geometry_result_id: str
    geometry_request_id: str
    run_id: str
    candidate_id: str
    configuration_id: Optional[str]

    status: Literal["success", "failed", "success_with_warnings"]

    geometry_artifacts: GeometryArtifacts
    generated_components: List[GeometryComponent] = []
    mesh_validation: Optional[MeshValidationReport] = None

    trace_links: List[TraceLink] = []
    compliance_artifact_links: List[ComplianceArtifactLink] = []

    warnings: List[str] = []
    errors: List[ErrorInfo] = []
    log: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
