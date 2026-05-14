from datetime import datetime

import pytest

from aeroloop.agents.airspace_environment_agent import AirspaceEnvironmentAgent
from aeroloop.agents.certification_requirement_agent import CertificationRequirementAgent
from aeroloop.agents.customer_requirement_agent import CustomerRequirementAgent
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent
from aeroloop.agents.orchestrator_agent import OrchestratorAgent
from aeroloop.agents.requirement_reasoning_agent import RequirementReasoningAgent
from aeroloop.schemas.certification import CertificationQueryContext
from aeroloop.schemas.mission import MissionProfile, MissionParsingInput
from aeroloop.schemas.requirement import CandidateRequirement
from aeroloop.schemas.workflow import RequirementBlackboard, WorkflowStage


class DummyLLM:
    def generate(self, prompt: str) -> str:
        return "{}"


@pytest.fixture
def raw_mission_input() -> MissionParsingInput:
    return MissionParsingInput(
        mission_id="input-001",
        raw_user_input="Konkuk campus medical supply delivery mission under 120 m altitude.",
        language="en",
        submitted_at=datetime(2026, 5, 14, 12, 0, 0),
    )


@pytest.fixture
def mission_profile(raw_mission_input: MissionParsingInput) -> MissionProfile:
    return MissionProfile(
        mission_id="mission-001",
        raw_input_id=raw_mission_input.mission_id,
        operation_area="Konkuk campus",
        operation_type="medical_delivery",
        payload_kg=2.5,
        max_altitude_m=120.0,
        priority=["safety", "delivery_time"],
    )


@pytest.fixture
def customer_candidate() -> CandidateRequirement:
    return CandidateRequirement(
        candidate_id="CUST-REQ-001",
        proposed_by="CustomerRequirementAgent",
        source_type="customer_requirement",
        source_refs=["input-001"],
        category="operations",
        title="Payload delivery",
        raw_requirement_text="The vehicle must carry 2.5 kg of medical supplies.",
        normalized_requirement="payload_kg >= 2.5",
        requirement_type="hard_constraint",
        variable_name="payload_kg",
        operator=">=",
        threshold=2.5,
        unit="kg",
        verification_target="aircraft_candidate",
        priority="high",
        severity="high",
        confidence=0.9,
        rationale="Payload is explicitly stated in the mission input.",
    )


def test_mission_parsing_agent_contract(raw_mission_input: MissionParsingInput) -> None:
    agent = MissionParsingAgent(llm_model=DummyLLM())

    assert agent.name == "Mission Parsing Agent"
    assert "MissionProfile" in agent.description
    assert isinstance(agent.llm_model, DummyLLM)

    with pytest.raises(NotImplementedError, match="LLM parsing logic"):
        agent.parse(raw_mission_input)

    state = {"raw_input": raw_mission_input, "current_stage": WorkflowStage.INITIALIZED}
    assert agent.run(state) is state


def test_customer_requirement_agent_contract(mission_profile: MissionProfile) -> None:
    agent = CustomerRequirementAgent(llm_model=DummyLLM())

    assert agent.name == "Customer Requirement Agent"
    assert "customer" in agent.description.lower()
    assert isinstance(agent.llm_model, DummyLLM)

    with pytest.raises(NotImplementedError, match="customer requirement analysis"):
        agent.analyze(mission_profile)

    state = {"mission_profile": mission_profile}
    assert agent.run(state) is state


def test_certification_requirement_agent_contract(mission_profile: MissionProfile) -> None:
    agent = CertificationRequirementAgent(llm_model=DummyLLM())
    context = CertificationQueryContext(
        jurisdiction_hint="KR",
        aircraft_category_hint="UAM",
        operation_type_hint="medical_delivery",
        candidate_aircraft_type="lift_cruise_vtol",
    )

    assert agent.name == "Certification Requirement Agent"
    assert "certification" in agent.description.lower()
    assert isinstance(agent.llm_model, DummyLLM)

    with pytest.raises(NotImplementedError, match="certification requirement analysis"):
        agent.analyze(mission_profile, context)

    state = {"mission_profile": mission_profile, "certification_context": context}
    assert agent.run(state) is state


def test_airspace_environment_agent_contract() -> None:
    agent = AirspaceEnvironmentAgent(llm_model=DummyLLM())

    assert agent.name == "Airspace & Environment Agent"
    assert "environmental constraints" in agent.description
    assert isinstance(agent.llm_model, DummyLLM)

    state = {
        "operation_area": "Konkuk campus",
        "candidate_requirements": [],
        "environment_requirement_candidates": [],
    }
    assert agent.run(state) is state


def test_requirement_reasoning_agent_contract(
    raw_mission_input: MissionParsingInput,
    mission_profile: MissionProfile,
    customer_candidate: CandidateRequirement,
) -> None:
    agent = RequirementReasoningAgent(llm_model=DummyLLM())
    blackboard = RequirementBlackboard(
        run_id="RUN-input-001",
        raw_input=raw_mission_input,
        mission_profile=mission_profile,
        customer_requirement_candidates=[customer_candidate],
    )

    assert agent.name == "Requirement Reasoning Agent"
    assert "finalrequirement" in agent.description.replace(" ", "").lower()
    assert isinstance(agent.llm_model, DummyLLM)

    with pytest.raises(NotImplementedError, match="requirement reasoning logic"):
        agent.refine(blackboard)

    state = {"blackboard": blackboard}
    assert agent.run(state) is state


@pytest.mark.parametrize(
    ("current_stage", "expected_next_agent"),
    [
        (WorkflowStage.INITIALIZED, "MissionParsingAgent"),
        (WorkflowStage.MISSION_PARSED, "CustomerRequirementAgent"),
        (WorkflowStage.CUSTOMER_REQUIREMENTS_GENERATED, "done"),
        (WorkflowStage.CERTIFICATION_REQUIREMENTS_GENERATED, "done"),
        (WorkflowStage.REQUIREMENTS_REASONED, "done"),
    ],
)
def test_orchestrator_routes_requirement_workflow_stages(
    current_stage: WorkflowStage,
    expected_next_agent: str,
) -> None:
    agent = OrchestratorAgent()

    assert agent.route({"current_stage": current_stage}) == expected_next_agent


def test_orchestrator_run_requirement_analysis_contract(
    raw_mission_input: MissionParsingInput,
) -> None:
    agent = OrchestratorAgent()

    with pytest.raises(NotImplementedError, match="Pipeline implementation"):
        agent.run_requirement_analysis(raw_mission_input)
