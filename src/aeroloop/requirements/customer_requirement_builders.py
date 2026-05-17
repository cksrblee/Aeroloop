from typing import List
from pydantic import BaseModel

from aeroloop.schemas.mission import MissionProfile
from aeroloop.schemas.requirement import CandidateRequirement
from aeroloop.utils.ids import make_id

class CustomerRequirementConfig(BaseModel):
    default_battery_reserve_percent: float = 20.0
    default_low_noise_threshold_db: float = 55.0
    default_max_mission_time_sec: float | None = None

    enable_default_battery_reserve: bool = True
    enable_noise_assumption: bool = True
    enable_comfort_requirements: bool = True

    min_confidence_for_candidate: float = 0.4

class CustomerRequirementBuilders:
    def __init__(self, config: CustomerRequirementConfig):
        self.config = config

    def build_capacity_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if mission.passenger_count is None:
            return None

        return CandidateRequirement(
            candidate_id=make_id("CAND-CUST-CAP"),
            proposed_by="CustomerRequirementAgent",
            source_type="customer_requirement",
            source_refs=["MissionProfile.passenger_count"],
            category="capacity",
            title="Passenger capacity requirement",
            raw_requirement_text=f"The aircraft must carry {mission.passenger_count} passengers.",
            normalized_requirement=f"The aircraft shall support at least {mission.passenger_count} passengers.",
            requirement_type="hard_constraint",
            variable_name="passenger_capacity",
            operator=">=",
            threshold=mission.passenger_count,
            unit="person",
            verification_target="aircraft_candidate",
            priority="critical",
            severity="critical",
            confidence=0.96,
            rationale="Passenger count is explicitly specified in the mission profile."
        )

    def build_payload_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if mission.payload_kg is None:
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-PAYLOAD-MISSING"),
                proposed_by="CustomerRequirementAgent",
                source_type="system_assumption",
                source_refs=[],
                category="payload",
                title="Payload information required",
                raw_requirement_text="The mission payload is unspecified.",
                normalized_requirement="Payload requirement needs clarification.",
                requirement_type="needs_clarification",
                verification_target="engineering_calculation",
                priority="high",
                severity="medium",
                confidence=0.4,
                rationale="Payload weight is not specified.",
                unresolved_issues=["Payload weight is not specified in the mission profile."]
            )

        return CandidateRequirement(
            candidate_id=make_id("CAND-CUST-PAYLOAD"),
            proposed_by="CustomerRequirementAgent",
            source_type="customer_requirement",
            source_refs=["MissionProfile.payload_kg"],
            category="payload",
            title="Payload capacity requirement",
            raw_requirement_text=f"The aircraft must carry a payload of {mission.payload_kg} kg.",
            normalized_requirement=f"The aircraft shall support a payload of at least {mission.payload_kg} kg.",
            requirement_type="hard_constraint",
            variable_name="payload_capacity_kg",
            operator=">=",
            threshold=mission.payload_kg,
            unit="kg",
            verification_target="aircraft_candidate",
            priority="critical",
            severity="critical",
            confidence=0.95,
            rationale="Payload is explicitly specified in the mission profile."
        )

    def build_mission_success_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if not mission.origin or not mission.destination:
            return None
            
        return CandidateRequirement(
            candidate_id=make_id("CAND-CUST-MSN"),
            proposed_by="CustomerRequirementAgent",
            source_type="customer_requirement",
            source_refs=["MissionProfile.origin", "MissionProfile.destination"],
            category="mission_success",
            title="Destination reachability",
            raw_requirement_text=f"The aircraft must reach {mission.destination} from {mission.origin}.",
            normalized_requirement="The aircraft shall reach the specified destination from the specified origin.",
            requirement_type="hard_constraint",
            variable_name="destination_reached",
            operator="==",
            threshold=True,
            unit=None,
            verification_target="runtime_simulation",
            priority="critical",
            severity="critical",
            confidence=0.99,
            rationale="Mission origin and destination are specified."
        )

    def build_range_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if mission.mission_distance_m is not None:
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-RANGE"),
                proposed_by="CustomerRequirementAgent",
                source_type="customer_requirement",
                source_refs=["MissionProfile.mission_distance_m"],
                category="range",
                title="Mission range requirement",
                raw_requirement_text=f"The mission distance is {mission.mission_distance_m} m.",
                normalized_requirement="The aircraft shall have sufficient range to complete the mission distance.",
                requirement_type="hard_constraint",
                variable_name="estimated_range_m",
                operator=">=",
                threshold=mission.mission_distance_m,
                unit="m",
                verification_target="engineering_calculation",
                priority="high",
                severity="high",
                confidence=0.9,
                rationale="Mission distance is specified."
            )
        elif mission.range_requirement_m is not None:
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-RANGE"),
                proposed_by="CustomerRequirementAgent",
                source_type="customer_requirement",
                source_refs=["MissionProfile.range_requirement_m"],
                category="range",
                title="Mission range requirement",
                raw_requirement_text=f"The aircraft must have a range of at least {mission.range_requirement_m} m.",
                normalized_requirement="The aircraft shall have sufficient range.",
                requirement_type="hard_constraint",
                variable_name="estimated_range_m",
                operator=">=",
                threshold=mission.range_requirement_m,
                unit="m",
                verification_target="engineering_calculation",
                priority="high",
                severity="high",
                confidence=0.9,
                rationale="Range requirement is explicitly specified."
            )
        return None

    def build_energy_preference_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        # Check explicit battery reserve first
        if mission.battery_reserve_at_destination_percent is not None:
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-ENERGY"),
                proposed_by="CustomerRequirementAgent",
                source_type="customer_requirement",
                source_refs=["MissionProfile.battery_reserve_at_destination_percent"],
                category="energy_reserve",
                title="Battery reserve preference",
                raw_requirement_text=f"The aircraft should arrive with {mission.battery_reserve_at_destination_percent}% battery reserve.",
                normalized_requirement="The aircraft should arrive at the destination with sufficient battery reserve.",
                requirement_type="hard_constraint",
                variable_name="battery_percent_at_arrival",
                operator=">=",
                threshold=mission.battery_reserve_at_destination_percent,
                unit="%",
                verification_target="runtime_simulation",
                priority="high",
                severity="critical",
                confidence=0.95,
                rationale="Battery reserve is explicitly specified in the mission profile."
            )
        elif self.config.enable_default_battery_reserve:
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-ENERGY-DEFAULT"),
                proposed_by="CustomerRequirementAgent",
                source_type="system_assumption",
                source_refs=["CustomerRequirementConfig.default_battery_reserve_percent"],
                category="energy_reserve",
                title="Battery reserve preference",
                raw_requirement_text="The aircraft should retain sufficient battery after mission completion.",
                normalized_requirement=f"The aircraft should arrive at the destination with at least {self.config.default_battery_reserve_percent}% battery remaining.",
                requirement_type="hard_constraint",
                variable_name="battery_percent_at_arrival",
                operator=">=",
                threshold=self.config.default_battery_reserve_percent,
                unit="%",
                verification_target="runtime_simulation",
                priority="high",
                severity="critical",
                confidence=0.58,
                rationale="A battery reserve requirement is operationally useful, but it was not explicitly specified by the user.",
                assumptions=[f"Default battery reserve is set to {self.config.default_battery_reserve_percent}% for PoC."],
                unresolved_issues=["The user did not specify the required battery reserve."]
            )
        return None

    def build_noise_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if mission.noise_constraints:
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-NOISE"),
                proposed_by="CustomerRequirementAgent",
                source_type="customer_requirement",
                source_refs=["MissionProfile.noise_constraints"],
                category="noise",
                title="Low-noise operation preference",
                raw_requirement_text="The mission requests low-noise operation.",
                normalized_requirement="The aircraft should minimize estimated noise exposure near noise-sensitive zones.",
                requirement_type="soft_objective",
                variable_name="estimated_noise_db",
                operator="<=",
                threshold=self.config.default_low_noise_threshold_db,
                unit="dB",
                verification_target="runtime_simulation",
                priority="medium",
                severity="medium",
                confidence=0.72,
                rationale="The mission includes a low-noise preference, but no exact noise threshold is provided.",
                assumptions=[f"Low-noise operation is approximated as estimated_noise_db <= {self.config.default_low_noise_threshold_db} dB for PoC."],
                unresolved_issues=["Exact noise threshold should be provided by the user or local operation rule."]
            )
        return None

    def build_safety_preference_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if mission.minimum_building_clearance_m is not None:
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-SAFE"),
                proposed_by="CustomerRequirementAgent",
                source_type="customer_requirement",
                source_refs=["MissionProfile.minimum_building_clearance_m"],
                category="obstacle_clearance",
                title="Minimum building clearance requirement",
                raw_requirement_text=f"The aircraft should maintain at least {mission.minimum_building_clearance_m}m clearance from buildings.",
                normalized_requirement=f"The aircraft shall maintain at least {mission.minimum_building_clearance_m}m distance from mapped buildings and obstacles.",
                requirement_type="hard_constraint",
                variable_name="distance_to_nearest_obstacle_m",
                operator=">=",
                threshold=mission.minimum_building_clearance_m,
                unit="m",
                verification_target="runtime_simulation",
                priority="critical",
                severity="critical",
                confidence=0.9,
                rationale="The mission profile includes an explicit safety constraint for building clearance."
            )
        return None

    def build_time_preference_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if mission.flight_time_limit_s is not None:
             return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-TIME"),
                proposed_by="CustomerRequirementAgent",
                source_type="customer_requirement",
                source_refs=["MissionProfile.flight_time_limit_s"],
                category="travel_time",
                title="Flight time limit",
                raw_requirement_text=f"The flight time must not exceed {mission.flight_time_limit_s} seconds.",
                normalized_requirement="The system should prefer routes and aircraft candidates that reduce total mission time.",
                requirement_type="hard_constraint",
                variable_name="estimated_mission_time_sec",
                operator="<=",
                threshold=mission.flight_time_limit_s,
                unit="sec",
                verification_target="engineering_calculation",
                priority="medium",
                severity="low",
                confidence=0.9,
                rationale="Flight time limit is explicitly specified."
            )
        return None

    def build_comfort_requirement(self, mission: MissionProfile) -> CandidateRequirement | None:
        if self.config.enable_comfort_requirements and mission.mission_type == "passenger":
            return CandidateRequirement(
                candidate_id=make_id("CAND-CUST-COMFORT"),
                proposed_by="CustomerRequirementAgent",
                source_type="system_assumption",
                source_refs=["CustomerRequirementConfig.enable_comfort_requirements", "MissionProfile.mission_type"],
                category="passenger_comfort",
                title="Passenger comfort preference",
                raw_requirement_text="The flight should be comfortable for passengers.",
                normalized_requirement="The aircraft should minimize abrupt turns, climbs, descents, and speed changes.",
                requirement_type="soft_objective",
                variable_name="maneuver_aggressiveness_score",
                operator="<=",
                threshold="scenario_defined_limit",
                unit="score",
                verification_target="runtime_simulation",
                priority="low",
                severity="low",
                confidence=0.5,
                rationale="Comfort requirement assumed for passenger mission type."
            )
        return None

    def build_unresolved_questions(self, mission: MissionProfile) -> List[str]:
        questions = []
        if mission.payload_kg is None:
            questions.append("What is the expected payload weight?")
        if mission.mission_distance_m is None and mission.range_requirement_m is None:
            questions.append("What is the estimated mission distance?")
        if mission.battery_reserve_at_destination_percent is None:
            questions.append("Should the aircraft maintain a specific battery reserve at arrival?")
        if not mission.noise_constraints:
            questions.append("Is there a specific noise threshold for the mission?")
        return questions
