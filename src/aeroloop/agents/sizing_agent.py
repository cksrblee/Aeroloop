import uuid
import math
import hashlib
from typing import Any, Dict, List, Optional
from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.engineering import (
    SizingRequest, SizingAgentResult, SizingConfig, SizingTemplate,
    SizingResult, EnergySizingResult, PowerSizingResult,
    GeometryParameterSet, PerformanceEstimate, SimulationParameterSet,
    WeightBreakdown, FeasibilityReport, FeasibilityCheck,
    TraceLink, ComplianceArtifactLink
)
from aeroloop.schemas.mission import MissionProfile
from aeroloop.schemas.aircraft import AircraftCandidate

class SizingAgent(BaseAIAgent):
    """
    SizingAgent performs deterministic low-fidelity sizing estimation.
    """
    def __init__(self, **kwargs):
        super().__init__(
            name="SizingAgent",
            description="Performs iterative low-fidelity engineering sizing calculations.",
            **kwargs
        )
        self.prompt_version = "v0.2.0"
        
        self.templates = {
            "lift_cruise_vtol": SizingTemplate(
                template_id="TPL-LCV-001",
                aircraft_type="lift_cruise_vtol",
                default_cruise_speed_mps=25.0,
                default_max_speed_mps=35.0,
                default_max_climb_rate_mps=4.0,
                default_min_turn_radius_m=25.0,
                hover_power_loading_kg_per_kw=4.5,
                cruise_power_loading_kg_per_kw=8.0,
                wing_loading_kg_per_m2=75.0,
                disk_loading_kg_per_m2=55.0,
                default_rotor_count=8,
                default_aspect_ratio=8.0,
                energy_consumption_kwh_per_km_base=3.0,
                takeoff_landing_energy_kwh=3.0,
                noise_coefficient_base=0.65,
            ),
            "small_helicopter": SizingTemplate(
                template_id="TPL-HELI-001",
                aircraft_type="small_helicopter",
                default_cruise_speed_mps=22.0,
                default_max_speed_mps=32.0,
                default_max_climb_rate_mps=3.5,
                default_min_turn_radius_m=20.0,
                hover_power_loading_kg_per_kw=4.0,
                disk_loading_kg_per_m2=35.0,
                default_rotor_count=1,
                energy_consumption_kwh_per_km_base=4.2,
                takeoff_landing_energy_kwh=2.5,
                noise_coefficient_base=0.8,
            ),
            "small_aircraft": SizingTemplate(
                template_id="TPL-SMALL-AIRCRAFT-001",
                aircraft_type="small_aircraft",
                default_cruise_speed_mps=35.0,
                default_max_speed_mps=50.0,
                default_max_climb_rate_mps=3.0,
                default_min_turn_radius_m=60.0,
                cruise_power_loading_kg_per_kw=10.0,
                wing_loading_kg_per_m2=85.0,
                default_aspect_ratio=9.0,
                energy_consumption_kwh_per_km_base=1.5,
                takeoff_landing_energy_kwh=0.8,
                noise_coefficient_base=0.55,
            )
        }

    def _get_template(self, candidate: AircraftCandidate, config: SizingConfig, warnings: List[str]) -> SizingTemplate:
        ac_type = candidate.aircraft_type
        if ac_type in self.templates:
            return self.templates[ac_type]
        elif config.allow_template_fallback:
            warnings.append(f"Unknown aircraft type '{ac_type}'. Falling back to lift_cruise_vtol.")
            return self.templates["lift_cruise_vtol"]
        else:
            raise ValueError(f"Unknown aircraft type '{ac_type}' and allow_template_fallback is False.")

    def _generate_id(self, prefix: str, base_id: str, salt: str = "") -> str:
        """Generates a deterministic ID based on a base_id and salt."""
        hash_str = hashlib.md5(f"{base_id}-{salt}".encode()).hexdigest()[:8]
        return f"{prefix}-{hash_str}"

    def _compute_payload(self, mission: MissionProfile, candidate: AircraftCandidate, config: SizingConfig, assumptions: List[str]) -> float:
        passenger_count = getattr(mission, 'passenger_count', None)
        if passenger_count is None:
            passenger_count = getattr(candidate, 'passenger_capacity', None)
            if passenger_count is None:
                passenger_count = 1
                assumptions.append("Passenger count missing from mission and candidate. Defaulting to 1.")
            else:
                assumptions.append(f"Passenger count missing from mission. Falling back to candidate capacity ({passenger_count}).")
                
        passenger_weight = passenger_count * config.passenger_mass_kg
        baggage_weight = passenger_count * config.baggage_mass_per_passenger_kg
        return passenger_weight + baggage_weight + config.default_payload_margin_kg

    def _get_mission_distance(self, mission: MissionProfile, warnings: List[str]) -> float:
        dist_m = getattr(mission, 'mission_distance_m', None)
        if dist_m is not None:
            return dist_m / 1000.0
        
        warnings.append("Mission distance was missing. Default minimum mission distance 1.0km was used for preliminary sizing.")
        return 1.0

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes iterative SizingAgent on SizingRequest inside the state.
        Args:
            state: dictionary with sizing_request: SizingRequest
        Returns:
            Dict with sizing_agent_result: SizingAgentResult
        """
        request: SizingRequest = state.get("sizing_request")
        if not request:
            # Construct it from legacy inputs for backward compatibility during testing
            mission_profile = state.get("mission_profile")
            aircraft_candidate = state.get("aircraft_candidate")
            requirements = state.get("requirements", [])
            
            if not mission_profile or not aircraft_candidate:
                raise ValueError("SizingAgent requires 'sizing_request' or 'mission_profile'+'aircraft_candidate' in state.")
                
            req_id = self._generate_id("SIZ-REQ", mission_profile.mission_id if hasattr(mission_profile, "mission_id") else "UNKNOWN")
            request = SizingRequest(
                sizing_request_id=req_id,
                run_id="RUN-UNKNOWN",
                mission_id="MISSION-UNKNOWN",
                candidate_id=getattr(aircraft_candidate, 'candidate_id', 'AC-UNKNOWN'),
                mission_profile=mission_profile,
                aircraft_candidate=aircraft_candidate,
                final_requirements=requirements
            )
            
        return {"sizing_agent_result": self.size(request)}

    def size(self, request: SizingRequest) -> SizingAgentResult:
        assumptions = []
        warnings = []
        limitations = [
            "Low-fidelity template-based sizing.",
            "Wind and detailed transition energy are not modeled.",
            "Noise coefficient is not a certified noise prediction."
        ]
        trace_links = []
        compliance_artifact_links = []
        checks = []

        try:
            template = self._get_template(request.aircraft_candidate, request.sizing_config, warnings)
        except ValueError as e:
            return SizingAgentResult(
                sizing_agent_result_id=self._generate_id("SIZ-RESULT", request.sizing_request_id, "fail1"),
                sizing_request_id=request.sizing_request_id,
                run_id=request.run_id,
                mission_id=request.mission_id,
                candidate_id=request.candidate_id,
                status="failed",
                limitations=limitations,
                warnings=[str(e)]
            )
            
        distance_km = self._get_mission_distance(request.mission_profile, warnings)
        if distance_km < 0:
            return self._fail_result(request, "Negative mission distance provided.")
            
        payload = self._compute_payload(request.mission_profile, request.aircraft_candidate, request.sizing_config, assumptions)
        passenger_count = getattr(request.mission_profile, 'passenger_count', getattr(request.aircraft_candidate, 'passenger_capacity', 1)) or 1
        
        if passenger_count < 0:
            return self._fail_result(request, "Negative passenger count provided.")

        # Iterative weight loop
        mtow = payload * 3.0 # Initial guess
        converged = False
        final_energy = None
        final_breakdown = None
        
        for i in range(request.sizing_config.max_iterations):
            # Compute energy
            cruise_energy = distance_km * (template.energy_consumption_kwh_per_km_base or 0.0)
            hover_takeoff_energy = template.takeoff_landing_energy_kwh
            total_mission_energy = cruise_energy + hover_takeoff_energy
            
            reserve_fraction = request.sizing_config.default_battery_reserve_percent / 100.0
            if reserve_fraction >= 0.8:
                warnings.append("High battery reserve requirement.")
            
            battery_capacity = total_mission_energy / (1.0 - reserve_fraction)
            battery_weight = (battery_capacity * 1000.0) / request.sizing_config.battery_specific_energy_wh_per_kg
            
            empty_weight = request.sizing_config.structural_weight_fraction * mtow
            propulsion_weight = request.sizing_config.propulsion_weight_fraction * mtow
            avionics_weight = request.sizing_config.avionics_weight_fraction * mtow
            margin_weight = request.sizing_config.margin_fraction * mtow
            
            new_mtow = payload + battery_weight + empty_weight + propulsion_weight + avionics_weight + margin_weight
            
            if abs(new_mtow - mtow) < request.sizing_config.convergence_tolerance_kg:
                mtow = new_mtow
                converged = True
                final_energy = EnergySizingResult(
                    energy_sizing_id=self._generate_id("ENERGY", request.sizing_request_id, "success"),
                    candidate_id=request.candidate_id,
                    mission_distance_km=distance_km,
                    cruise_energy_kwh=cruise_energy,
                    hover_energy_kwh=hover_takeoff_energy,
                    reserve_energy_kwh=battery_capacity - total_mission_energy,
                    total_mission_energy_kwh=total_mission_energy,
                    required_battery_capacity_kwh=battery_capacity,
                    selected_battery_capacity_kwh=battery_capacity,
                    estimated_arrival_battery_percent=100.0 * (battery_capacity - total_mission_energy) / battery_capacity,
                    estimated_battery_weight_kg=battery_weight
                )
                final_breakdown = WeightBreakdown(
                    payload_kg=payload,
                    passenger_weight_kg=passenger_count * request.sizing_config.passenger_mass_kg,
                    baggage_weight_kg=passenger_count * request.sizing_config.baggage_mass_per_passenger_kg,
                    empty_weight_kg=empty_weight,
                    battery_weight_kg=battery_weight,
                    propulsion_weight_kg=propulsion_weight,
                    avionics_weight_kg=avionics_weight,
                    margin_weight_kg=margin_weight,
                    mtow_kg=mtow
                )
                break
                
            mtow = new_mtow

        if not converged:
            warnings.append("MTOW iteration did not converge.")
            # Build fallback final energy / breakdown using last iteration values
            final_energy = EnergySizingResult(
                energy_sizing_id=self._generate_id("ENERGY", request.sizing_request_id, "fallback"),
                candidate_id=request.candidate_id,
                mission_distance_km=distance_km,
                cruise_energy_kwh=cruise_energy,
                hover_energy_kwh=hover_takeoff_energy,
                reserve_energy_kwh=battery_capacity - total_mission_energy,
                total_mission_energy_kwh=total_mission_energy,
                required_battery_capacity_kwh=battery_capacity,
                selected_battery_capacity_kwh=battery_capacity,
                estimated_arrival_battery_percent=100.0 * (battery_capacity - total_mission_energy) / battery_capacity,
                estimated_battery_weight_kg=battery_weight
            )
            final_breakdown = WeightBreakdown(
                payload_kg=payload,
                passenger_weight_kg=passenger_count * request.sizing_config.passenger_mass_kg,
                baggage_weight_kg=passenger_count * request.sizing_config.baggage_mass_per_passenger_kg,
                empty_weight_kg=empty_weight,
                battery_weight_kg=battery_weight,
                propulsion_weight_kg=propulsion_weight,
                avionics_weight_kg=avionics_weight,
                margin_weight_kg=margin_weight,
                mtow_kg=mtow
            )

        # Power sizing
        hover_power = None
        cruise_power = None
        climb_power = None
        installed_power = 0.0
        
        if template.aircraft_type in ["lift_cruise_vtol", "small_helicopter", "multirotor"]:
            if template.hover_power_loading_kg_per_kw:
                hover_power = mtow / template.hover_power_loading_kg_per_kw
        
        if template.aircraft_type in ["lift_cruise_vtol", "small_aircraft"]:
            if template.cruise_power_loading_kg_per_kw:
                cruise_power = mtow / template.cruise_power_loading_kg_per_kw
                
        if template.aircraft_type == "small_helicopter" and hover_power:
            climb_power = hover_power * (template.climb_margin or 1.2)
            
        powers = [p for p in [hover_power, cruise_power, climb_power] if p is not None]
        if powers:
            installed_power = max(powers) * (template.power_margin or 1.2)

        power_result = PowerSizingResult(
            power_sizing_id=self._generate_id("POWER", request.sizing_request_id),
            candidate_id=request.candidate_id,
            required_hover_power_kw=hover_power,
            required_cruise_power_kw=cruise_power,
            required_climb_power_kw=climb_power,
            installed_power_kw=installed_power,
            power_loading_kg_per_kw=mtow / installed_power if installed_power > 0 else 0.0
        )

        # Geometry parameters
        wing_area = None
        wingspan = None
        root_chord = None
        tip_chord = None
        if template.aircraft_type in ["lift_cruise_vtol", "small_aircraft"] and template.wing_loading_kg_per_m2:
            wing_area = mtow / template.wing_loading_kg_per_m2
            aspect_ratio = template.default_aspect_ratio or 8.0
            wingspan = math.sqrt(wing_area * aspect_ratio)
            mean_chord = wing_area / wingspan
            root_chord = mean_chord * 1.2
            tip_chord = mean_chord * 0.8
            
        rotor_radius = None
        total_disk_area = None
        if template.aircraft_type in ["lift_cruise_vtol", "small_helicopter", "multirotor"] and template.disk_loading_kg_per_m2:
            total_disk_area = mtow / template.disk_loading_kg_per_m2
            rotor_count = template.default_rotor_count or 1
            single_rotor_area = total_disk_area / rotor_count
            rotor_radius = math.sqrt(single_rotor_area / math.pi)

        sizing_id = self._generate_id("SIZE", request.sizing_request_id)
        geom_result = GeometryParameterSet(
            geometry_param_id=self._generate_id("GEO", request.sizing_request_id),
            candidate_id=request.candidate_id,
            aircraft_type=template.aircraft_type,
            wing_area_m2=wing_area,
            wingspan_m=wingspan,
            root_chord_m=root_chord,
            tip_chord_m=tip_chord,
            aspect_ratio=template.default_aspect_ratio,
            rotor_count=template.default_rotor_count,
            rotor_radius_m=rotor_radius,
            total_disk_area_m2=total_disk_area,
            source_sizing_id=sizing_id
        )

        # Feasibility & Limitations
        overall_feasible = True
        
        for req in request.final_requirements:
            if req.variable_name == "passenger_capacity":
                passed = passenger_count >= req.threshold
                checks.append(FeasibilityCheck(
                    check_id=self._generate_id("CHK", request.sizing_request_id, f"req-{req.requirement_id}"),
                    requirement_id=req.requirement_id,
                    name="Passenger capacity",
                    passed=passed,
                    measured_value=float(passenger_count),
                    required_value=float(req.threshold),
                    unit="person"
                ))
                if not passed: overall_feasible = False
                
                trace_links.append(TraceLink(
                    trace_id=self._generate_id("TR", request.sizing_request_id, f"req-{req.requirement_id}"),
                    source_type="FinalRequirement",
                    source_id=req.requirement_id,
                    target_type="SizingResult",
                    target_id=sizing_id,
                    relation_type="derived_from"
                ))
                
            elif req.variable_name == "battery_percent_at_arrival":
                passed = final_energy.estimated_arrival_battery_percent >= req.threshold
                checks.append(FeasibilityCheck(
                    check_id=self._generate_id("CHK", request.sizing_request_id, f"req-{req.requirement_id}"),
                    requirement_id=req.requirement_id,
                    name="Arrival battery reserve",
                    passed=passed,
                    measured_value=final_energy.estimated_arrival_battery_percent,
                    required_value=float(req.threshold),
                    unit="%"
                ))
                if not passed: overall_feasible = False
                
                trace_links.append(TraceLink(
                    trace_id=self._generate_id("TR", request.sizing_request_id, f"req-{req.requirement_id}"),
                    source_type="FinalRequirement",
                    source_id=req.requirement_id,
                    target_type="EnergySizingResult",
                    target_id=final_energy.energy_sizing_id,
                    relation_type="derived_from"
                ))
                
        # CCL / MoC Context
        if request.compliance_context and request.compliance_context.ccl_item_ids:
            for ccl in request.compliance_context.ccl_item_ids:
                compliance_artifact_links.append(ComplianceArtifactLink(
                    ccl_item_id=ccl,
                    moc_type="analysis",
                    artifact_ids=[sizing_id, final_energy.energy_sizing_id],
                    evidence_role="preliminary_analysis_evidence"
                ))

        status = "success" if not warnings else "success_with_warnings"

        return SizingAgentResult(
            sizing_agent_result_id=self._generate_id("SIZ-RESULT", request.sizing_request_id),
            sizing_request_id=request.sizing_request_id,
            run_id=request.run_id,
            mission_id=request.mission_id,
            candidate_id=request.candidate_id,
            status=status,
            sizing_result=SizingResult(
                sizing_id=sizing_id,
                candidate_id=request.candidate_id,
                aircraft_type=template.aircraft_type,
                template_id=template.template_id,
                mtow_kg=mtow,
                weight_breakdown=final_breakdown,
                iterations=i + 1,
                converged=converged
            ),
            energy_sizing_result=final_energy,
            power_sizing_result=power_result,
            geometry_parameter_set=geom_result,
            performance_estimate=PerformanceEstimate(
                performance_id=self._generate_id("PERF", request.sizing_request_id),
                candidate_id=request.candidate_id,
                estimated_range_km=final_energy.required_battery_capacity_kwh / (template.energy_consumption_kwh_per_km_base or 3.0),
                estimated_mission_energy_kwh=final_energy.total_mission_energy_kwh,
                estimated_arrival_battery_percent=final_energy.estimated_arrival_battery_percent,
                estimated_flight_time_min=(distance_km / template.default_cruise_speed_mps) * 1000.0 / 60.0,
                climb_feasibility=True,
                turn_feasibility=True,
                mission_feasible=overall_feasible,
                limitations=limitations
            ),
            simulation_parameter_set=SimulationParameterSet(
                sim_param_id=self._generate_id("SIM", request.sizing_request_id),
                candidate_id=request.candidate_id,
                sizing_id=sizing_id,
                max_speed_mps=template.default_max_speed_mps,
                cruise_speed_mps=template.default_cruise_speed_mps,
                max_climb_rate_mps=template.default_max_climb_rate_mps,
                min_turn_radius_m=template.default_min_turn_radius_m,
                battery_capacity_kwh=final_energy.required_battery_capacity_kwh,
                energy_consumption_kwh_per_km=template.energy_consumption_kwh_per_km_base or 3.0,
                safety_distance_m=10.0,
                noise_coefficient=template.noise_coefficient_base,
                mtow_kg=mtow,
                payload_kg=payload
            ),
            feasibility_report=FeasibilityReport(
                overall_feasible=overall_feasible,
                checks=checks,
                warnings=warnings
            ),
            assumptions=assumptions,
            warnings=warnings,
            limitations=limitations,
            trace_links=trace_links,
            compliance_artifact_links=compliance_artifact_links
        )

    def _fail_result(self, request: SizingRequest, reason: str) -> SizingAgentResult:
        return SizingAgentResult(
            sizing_agent_result_id=self._generate_id("SIZ-RESULT", request.sizing_request_id, "fail_result"),
            sizing_request_id=request.sizing_request_id,
            run_id=request.run_id,
            mission_id=request.mission_id,
            candidate_id=request.candidate_id,
            status="failed",
            warnings=[reason],
            limitations=["Calculations aborted due to invalid inputs."]
        )
