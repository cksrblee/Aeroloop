import json
from datetime import datetime
from typing import Any, Dict

try:
    from langfuse.decorators import observe
except ImportError:
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.mission import MissionProfile
from aeroloop.schemas.requirement import CustomerRequirementResult, CandidateRequirement
from aeroloop.utils.ids import make_id

from aeroloop.requirements.customer_requirement_builders import (
    CustomerRequirementConfig,
    CustomerRequirementBuilders
)
from aeroloop.requirements.customer_requirement_validator import CustomerRequirementValidator

class CustomerRequirementAgent(BaseAIAgent):
    """
    Generates customer and operational perspective CandidateRequirements based on the parsed MissionProfile.
    """
    def __init__(self, agent_version: str = "v0.1", config: CustomerRequirementConfig | None = None, **kwargs):
        super().__init__(
            name="Customer Requirement Agent",
            description="Derives customer and operational requirement candidates from the MissionProfile.",
            **kwargs
        )
        self.agent_version = agent_version
        self.config = config or CustomerRequirementConfig()
        self.builders = CustomerRequirementBuilders(self.config)
        self.validator = CustomerRequirementValidator()

    def _build_default_prompt(self) -> str:
        return """
You are CustomerRequirementAgent for AeroLoop.

Your task is to refine and generate additional customer and operational requirement candidates from a structured MissionProfile.

You must focus only on customer and operational requirements.
Do not generate certification or legal requirements.
Do not cite aviation regulations.
Do not invent missing numerical values as facts.

Return only valid JSON matching the CandidateRequirement list schema.

For each requirement:
- Identify whether it is a hard_constraint, soft_objective, report_only, or needs_clarification.
- Use measurable variables whenever possible.
- If a value is missing, set threshold to null or use an explicit assumption.
- Record assumptions and unresolved issues.
- Assign verification_target.
- Assign priority, severity, and confidence.

Allowed categories:
- capacity
- payload
- mission_success
- range
- energy_reserve
- noise
- safety_preference
- obstacle_clearance
- travel_time
- passenger_comfort
- operation_area
- usability

Do not output markdown.
Do not include explanations outside JSON.
"""

    @observe()
    def analyze(self, mission_profile: MissionProfile) -> CustomerRequirementResult:
        """
        Analyzes the MissionProfile to generate customer-specific and operational requirements.
        """
        candidates = []
        assumptions = []
        unresolved_questions = []
        quality_flags = []

        # 1. Deterministic Rule Builders
        req = self.builders.build_capacity_requirement(mission_profile)
        if req: candidates.append(req)
        
        req = self.builders.build_payload_requirement(mission_profile)
        if req:
            candidates.append(req)
            if req.requirement_type == "needs_clarification":
                quality_flags.append("payload_kg_missing")
                
        req = self.builders.build_mission_success_requirement(mission_profile)
        if req: candidates.append(req)
        
        req = self.builders.build_range_requirement(mission_profile)
        if req:
            candidates.append(req)
        else:
            quality_flags.append("mission_distance_missing")
            
        req = self.builders.build_energy_preference_requirement(mission_profile)
        if req:
            candidates.append(req)
            if req.source_type == "system_assumption":
                assumptions.extend([{"assumption_id": make_id("ASM"), "text": a, "source": "System"} for a in req.assumptions])

        req = self.builders.build_noise_requirement(mission_profile)
        if req:
            candidates.append(req)
            if req.assumptions:
                quality_flags.append("noise_threshold_assumed")
                assumptions.extend([{"assumption_id": make_id("ASM"), "text": a, "source": "System"} for a in req.assumptions])

        req = self.builders.build_safety_preference_requirement(mission_profile)
        if req: candidates.append(req)

        req = self.builders.build_time_preference_requirement(mission_profile)
        if req: candidates.append(req)
        
        req = self.builders.build_comfort_requirement(mission_profile)
        if req:
            candidates.append(req)
            if req.source_type == "system_assumption":
                assumptions.extend([{"assumption_id": make_id("ASM"), "text": a, "source": "System"} for a in req.assumptions])

        unresolved_questions.extend(self.builders.build_unresolved_questions(mission_profile))

        # 2. LLM Reasoning (Optional enhancement if configured, but for now we rely on deterministic baseline with placeholders for LLM logic if needed)
        # To truly integrate LLM, we would format mission_profile to JSON and request CandidateRequirement[] list.
        # For this version, deterministic generation is sufficient per requirements. We will just use the LLM if specifically requested to parse ambiguities.
        
        # 3. Validation
        validation_errors = self.validator.validate(candidates)
        if validation_errors:
            # If invalid, we could try to fix or just log. We will add flags.
            quality_flags.extend(["validation_errors_present"])

        return CustomerRequirementResult(
            result_id=make_id("CUST-REQ-RESULT"),
            mission_id=mission_profile.mission_id if hasattr(mission_profile, "mission_id") else "UNKNOWN_MISSION",
            agent_version=self.agent_version,
            candidate_requirements=candidates,
            assumptions=assumptions,
            unresolved_questions=unresolved_questions,
            quality_flags=quality_flags,
            created_at=datetime.utcnow()
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        mission_profile = state.get("mission_profile")
        if isinstance(mission_profile, dict):
            mission_profile = MissionProfile(**mission_profile)
            
        if mission_profile:
            result = self.analyze(mission_profile)
            state["customer_requirements_result"] = result
        return state
