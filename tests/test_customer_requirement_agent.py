import pytest
from aeroloop.schemas.mission import MissionProfile
from aeroloop.agents.customer_requirement_agent import CustomerRequirementAgent
from aeroloop.schemas.requirement import CustomerRequirementResult

def test_capacity_requirement():
    mission = MissionProfile(passenger_count=2)
    agent = CustomerRequirementAgent()
    result = agent.analyze(mission)
    
    cap_reqs = [r for r in result.candidate_requirements if r.category == "capacity"]
    assert len(cap_reqs) == 1
    req = cap_reqs[0]
    assert req.variable_name == "passenger_capacity"
    assert req.operator == ">="
    assert req.threshold == 2
    assert req.verification_target == "aircraft_candidate"

def test_mission_success_requirement():
    mission = MissionProfile(origin="dormitory", destination="library")
    agent = CustomerRequirementAgent()
    result = agent.analyze(mission)
    
    msn_reqs = [r for r in result.candidate_requirements if r.category == "mission_success"]
    assert len(msn_reqs) == 1
    req = msn_reqs[0]
    assert req.variable_name == "destination_reached"
    assert req.operator == "=="
    assert req.threshold is True

def test_noise_requirement():
    mission = MissionProfile(noise_constraints=["low_noise"])
    agent = CustomerRequirementAgent()
    result = agent.analyze(mission)
    
    noise_reqs = [r for r in result.candidate_requirements if r.category == "noise"]
    assert len(noise_reqs) == 1
    req = noise_reqs[0]
    assert req.requirement_type == "soft_objective"
    assert req.variable_name == "estimated_noise_db"
    assert req.operator == "<="
    assert req.threshold == 55
    assert "noise_threshold_assumed" in result.quality_flags

def test_payload_missing():
    mission = MissionProfile(payload_kg=None)
    agent = CustomerRequirementAgent()
    result = agent.analyze(mission)
    
    payload_reqs = [r for r in result.candidate_requirements if r.category == "payload"]
    assert len(payload_reqs) == 1
    req = payload_reqs[0]
    assert req.requirement_type == "needs_clarification"
    assert req.threshold is None
    
    assert "What is the expected payload weight?" in result.unresolved_questions
    assert "payload_kg_missing" in result.quality_flags

def test_no_certification_requirements():
    mission = MissionProfile(passenger_count=4, origin="A", destination="B")
    agent = CustomerRequirementAgent()
    result = agent.analyze(mission)
    
    for req in result.candidate_requirements:
        assert req.source_type != "certification_db"

def test_schema_validation():
    mission = MissionProfile(
        passenger_count=2,
        origin="dormitory",
        destination="library",
        noise_constraints=["low_noise"]
    )
    agent = CustomerRequirementAgent()
    result = agent.analyze(mission)
    
    # Validation by pydantic automatically ensures the output matches CustomerRequirementResult schema.
    # If the output can be parsed, schema validation passes.
    assert isinstance(result, CustomerRequirementResult)
    # Ensure there are no validation errors added as quality flags
    assert "validation_errors_present" not in result.quality_flags
