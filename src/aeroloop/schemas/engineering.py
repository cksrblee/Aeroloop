from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from .mission import MissionProfile
from .aircraft import AircraftCandidate
from .requirement import FinalRequirement
from .traceability import TraceLink

class SizingConfig(BaseModel):
    passenger_mass_kg: float = 85.0
    baggage_mass_per_passenger_kg: float = 10.0
    default_payload_margin_kg: float = 20.0

    default_battery_reserve_percent: float = 20.0
    battery_specific_energy_wh_per_kg: float = 220.0

    structural_weight_fraction: float = 0.42
    propulsion_weight_fraction: float = 0.12
    avionics_weight_fraction: float = 0.05
    margin_fraction: float = 0.10

    max_iterations: int = 50
    convergence_tolerance_kg: float = 5.0

    allow_template_fallback: bool = False

class ComplianceContext(BaseModel):
    ccl_item_ids: List[str] = Field(default_factory=list)
    moc_candidates: List[str] = Field(default_factory=list)

class SizingRequest(BaseModel):
    sizing_request_id: str
    run_id: str
    mission_id: str
    candidate_id: str

    mission_profile: MissionProfile
    aircraft_candidate: AircraftCandidate
    final_requirements: List[FinalRequirement] = Field(default_factory=list)

    sizing_config: SizingConfig = Field(default_factory=SizingConfig)
    compliance_context: Optional[ComplianceContext] = None

class SizingTemplate(BaseModel):
    template_id: str
    aircraft_type: Literal[
        "lift_cruise_vtol",
        "small_helicopter",
        "small_aircraft",
        "multirotor"
    ]

    default_cruise_speed_mps: float
    default_max_speed_mps: float
    default_max_climb_rate_mps: float
    default_min_turn_radius_m: float

    energy_consumption_kwh_per_km_base: Optional[float] = None
    hover_power_loading_kg_per_kw: Optional[float] = None
    cruise_power_loading_kg_per_kw: Optional[float] = None
    climb_margin: Optional[float] = 1.2
    power_margin: Optional[float] = 1.2

    wing_loading_kg_per_m2: Optional[float] = None
    disk_loading_kg_per_m2: Optional[float] = None

    default_rotor_count: Optional[int] = None
    default_aspect_ratio: Optional[float] = None

    takeoff_landing_energy_kwh: float = 0.0
    noise_coefficient_base: float

class WeightBreakdown(BaseModel):
    payload_kg: float
    passenger_weight_kg: float
    baggage_weight_kg: float
    empty_weight_kg: float
    battery_weight_kg: float
    propulsion_weight_kg: float
    avionics_weight_kg: float
    margin_weight_kg: float
    mtow_kg: float

class SizingResult(BaseModel):
    sizing_id: str
    candidate_id: str
    aircraft_type: str
    template_id: str
    mtow_kg: float
    weight_breakdown: WeightBreakdown
    iterations: int
    converged: bool

class EnergySizingResult(BaseModel):
    energy_sizing_id: str
    candidate_id: str
    mission_distance_km: float
    cruise_energy_kwh: float
    hover_energy_kwh: Optional[float] = None
    climb_energy_kwh: Optional[float] = None
    reserve_energy_kwh: float
    total_mission_energy_kwh: float
    required_battery_capacity_kwh: float
    selected_battery_capacity_kwh: float
    estimated_arrival_battery_percent: float
    estimated_battery_weight_kg: float

class PowerSizingResult(BaseModel):
    power_sizing_id: str
    candidate_id: str
    required_hover_power_kw: Optional[float] = None
    required_cruise_power_kw: Optional[float] = None
    required_climb_power_kw: Optional[float] = None
    installed_power_kw: float
    power_loading_kg_per_kw: float
    thrust_to_weight_ratio: Optional[float] = None

class GeometryParameterSet(BaseModel):
    geometry_param_id: str
    candidate_id: str
    aircraft_type: str
    fuselage_length_m: Optional[float] = None
    fuselage_diameter_m: Optional[float] = None
    wing_area_m2: Optional[float] = None
    wingspan_m: Optional[float] = None
    root_chord_m: Optional[float] = None
    tip_chord_m: Optional[float] = None
    aspect_ratio: Optional[float] = None
    rotor_count: Optional[int] = None
    rotor_radius_m: Optional[float] = None
    total_disk_area_m2: Optional[float] = None
    source_sizing_id: str

class SimulationParameterSet(BaseModel):
    sim_param_id: str
    candidate_id: str
    sizing_id: str
    max_speed_mps: float
    cruise_speed_mps: float
    max_climb_rate_mps: float
    max_descent_rate_mps: Optional[float] = None
    min_turn_radius_m: float
    battery_capacity_kwh: float
    energy_consumption_kwh_per_km: float
    initial_battery_percent: float = 100.0
    safety_distance_m: float
    noise_coefficient: float
    mtow_kg: float
    payload_kg: float

class PerformanceEstimate(BaseModel):
    performance_id: str
    candidate_id: str
    estimated_range_km: float
    estimated_mission_energy_kwh: float
    estimated_arrival_battery_percent: float
    estimated_flight_time_min: float
    climb_feasibility: bool
    turn_feasibility: bool
    mission_feasible: bool
    limitations: List[str] = Field(default_factory=list)

class FeasibilityCheck(BaseModel):
    check_id: str
    requirement_id: Optional[str] = None
    name: str
    passed: bool
    measured_value: float
    required_value: float
    unit: str

class FeasibilityReport(BaseModel):
    overall_feasible: bool
    checks: List[FeasibilityCheck] = Field(default_factory=list)
    blocking_issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class ComplianceArtifactLink(BaseModel):
    ccl_item_id: str
    moc_type: str
    artifact_ids: List[str] = Field(default_factory=list)
    evidence_role: str

class SizingAgentResult(BaseModel):
    sizing_agent_result_id: str
    sizing_request_id: str
    run_id: str
    mission_id: str
    candidate_id: str
    status: Literal["success", "success_with_warnings", "failed", "requires_template_selection"]
    
    sizing_result: Optional[SizingResult] = None
    energy_sizing_result: Optional[EnergySizingResult] = None
    power_sizing_result: Optional[PowerSizingResult] = None
    geometry_parameter_set: Optional[GeometryParameterSet] = None
    performance_estimate: Optional[PerformanceEstimate] = None
    simulation_parameter_set: Optional[SimulationParameterSet] = None
    feasibility_report: Optional[FeasibilityReport] = None
    
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    
    trace_links: List[TraceLink] = Field(default_factory=list)
    compliance_artifact_links: List[ComplianceArtifactLink] = Field(default_factory=list)
