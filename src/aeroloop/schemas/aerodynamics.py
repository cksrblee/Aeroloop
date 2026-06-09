from typing import Dict, Any, Optional, List, Tuple, Literal
from pydantic import BaseModel, Field

from aeroloop.schemas.common import ErrorInfo

class AeroAnalysisConfig(BaseModel):
    analysis_backend: Literal[
        "openvsp_vspaero",
        "openvsp_massprop_only",
        "external_cfd",
        "mock"
    ] = "openvsp_vspaero"

    analysis_fidelity: Literal[
        "conceptual",
        "low",
        "medium",
        "high"
    ] = "low"

    run_vspaero: bool = True
    run_mass_properties: bool = True
    run_parasite_drag: bool = False

    angle_of_attack_deg: List[float] = [-4, 0, 4, 8, 12]
    sideslip_deg: List[float] = [0]
    speed_mps: List[float] = [25.0]
    altitude_m: List[float] = [120.0]

    reference_area_source: Optional[str] = None
    reference_span_source: Optional[str] = None
    reference_chord_source: Optional[str] = None

    mass_property_num_slices: int = 20
    strict_solver_success: bool = False
    allow_aircraft_type_fallback: bool = False


class AerodynamicCoefficientCase(BaseModel):
    case_id: str
    alpha_deg: float
    beta_deg: float
    speed_mps: Optional[float] = None
    altitude_m: Optional[float] = None

    cl: Optional[float] = None
    cd: Optional[float] = None
    cm: Optional[float] = None
    cy: Optional[float] = None
    cl_roll: Optional[float] = None
    cn_yaw: Optional[float] = None

    source: str


class AerodynamicSummary(BaseModel):
    cl_alpha_per_deg: Optional[float] = None
    cd_min: Optional[float] = None
    max_lift_to_drag: Optional[float] = None
    estimated_trim_alpha_deg: Optional[float] = None
    stall_estimation_available: bool = False
    notes: List[str] = []


class MassPropertiesResult(BaseModel):
    mass_analysis_available: bool
    total_mass_kg: Optional[float] = None
    center_of_gravity_m: Optional[Tuple[float, float, float]] = None

    moments_of_inertia_kg_m2: Optional[Dict[str, float]] = None
    component_mass_breakdown: List[Dict[str, Any]] = []

    assumptions: List[str] = []
    warnings: List[str] = []


class AeroAnalysisSetup(BaseModel):
    analysis_backend: str
    analysis_fidelity: str
    aircraft_type: Optional[str] = None
    reference_area_m2: Optional[float] = None
    reference_span_m: Optional[float] = None
    reference_chord_m: Optional[float] = None
    moment_reference_point_m: Optional[Tuple[float, float, float]] = None
    angle_of_attack_deg: List[float] = []
    sideslip_deg: List[float] = []
    speed_mps: List[float] = []
    altitude_m: List[float] = []


class ConsistencyCheck(BaseModel):
    check_id: str
    name: str
    passed: bool
    reference_value: Optional[float] = None
    measured_value: Optional[float] = None
    unit: Optional[str] = None
    tolerance_percent: Optional[float] = None


class AeroFeasibilityAssessment(BaseModel):
    overall_status: str
    blocking_issues: List[str] = []
    warnings: List[str] = []


class AeroAnalysisArtifacts(BaseModel):
    vspaero_input_path: Optional[str] = None
    vspaero_result_path: Optional[str] = None
    mass_properties_result_path: Optional[str] = None
    drag_polar_plot_path: Optional[str] = None
    lift_curve_plot_path: Optional[str] = None
    analysis_summary_path: Optional[str] = None


class TraceLink(BaseModel):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relation_type: str


class ComplianceArtifactLink(BaseModel):
    ccl_item_id: str
    moc_type: str
    artifact_ids: List[str] = []
    evidence_role: str


class AerodynamicsAnalysisResult(BaseModel):
    aero_analysis_result_id: str
    aero_analysis_request_id: str
    run_id: str
    mission_id: str
    candidate_id: str

    status: Literal[
        "success",
        "success_with_warnings",
        "failed"
    ]

    analysis_setup: Optional[AeroAnalysisSetup] = None
    aerodynamic_coefficients: List[AerodynamicCoefficientCase] = []
    aerodynamic_summary: Optional[AerodynamicSummary] = None
    mass_properties: Optional[MassPropertiesResult] = None
    consistency_checks: List[ConsistencyCheck] = []
    feasibility_assessment: Optional[AeroFeasibilityAssessment] = None

    analysis_artifacts: Optional[AeroAnalysisArtifacts] = None

    trace_links: List[TraceLink] = []
    compliance_artifact_links: List[ComplianceArtifactLink] = []

    assumptions: List[str] = []
    limitations: List[str] = []
    warnings: List[str] = []
    errors: List[ErrorInfo] = []


class AircraftCandidate(BaseModel):
    candidate_id: str
    aircraft_type: str
    template_id: str


class GeometryArtifacts(BaseModel):
    vsp3_file_path: str
    stl_file_path: Optional[str] = None
    geometry_manifest_path: Optional[str] = None


class FinalRequirement(BaseModel):
    requirement_id: str
    title: str
    verification_target: str


class ComplianceContext(BaseModel):
    ccl_item_ids: List[str] = []
    moc_candidates: List[str] = []


class GeometryParameterSet(BaseModel):
    geometry_param_id: str
    aircraft_type: str
    wing_area_m2: Optional[float] = None
    wingspan_m: Optional[float] = None
    root_chord_m: Optional[float] = None
    tip_chord_m: Optional[float] = None
    rotor_count: Optional[int] = None
    rotor_radius_m: Optional[float] = None
    fuselage_length_m: Optional[float] = None
    fuselage_diameter_m: Optional[float] = None


class SizingResult(BaseModel):
    sizing_id: str
    mtow_kg: Optional[float] = None
    payload_kg: Optional[float] = None
    battery_weight_kg: Optional[float] = None
    installed_power_kw: Optional[float] = None


class SimulationParameterSet(BaseModel):
    sim_param_id: str
    cruise_speed_mps: Optional[float] = None
    max_speed_mps: Optional[float] = None
    max_climb_rate_mps: Optional[float] = None
    min_turn_radius_m: Optional[float] = None
    battery_capacity_kwh: Optional[float] = None


class AerodynamicsAnalysisRequest(BaseModel):
    aero_analysis_request_id: str
    run_id: str
    mission_id: str
    candidate_id: str

    geometry_result_id: str
    sizing_result_id: Optional[str] = None

    aircraft_candidate: AircraftCandidate
    geometry_artifacts: GeometryArtifacts
    geometry_parameter_set: Optional[GeometryParameterSet] = None
    sizing_result: Optional[SizingResult] = None
    simulation_parameter_set: Optional[SimulationParameterSet] = None
    final_requirements: List[FinalRequirement] = []

    analysis_config: AeroAnalysisConfig
    compliance_context: Optional[ComplianceContext] = None
    output_directory: str
