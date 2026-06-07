import pytest
from aeroloop.agents.sizing_agent import SizingAgent
from aeroloop.schemas.mission import MissionProfile
from aeroloop.schemas.aircraft import AircraftCandidate
from aeroloop.schemas.requirement import FinalRequirement
from aeroloop.schemas.engineering import SizingRequest, SizingConfig, ComplianceContext

@pytest.fixture
def agent():
    return SizingAgent()

@pytest.fixture
def base_request():
    return SizingRequest(
        sizing_request_id="REQ-123",
        run_id="RUN-123",
        mission_id="MIS-123",
        candidate_id="CAN-123",
        mission_profile=MissionProfile(
            passenger_count=2,
            mission_distance_m=5000.0,
            max_altitude_m=120.0
        ),
        aircraft_candidate=AircraftCandidate(
            candidate_id="CAN-123",
            aircraft_type="lift_cruise_vtol",
            passenger_capacity=2
        ),
        final_requirements=[],
        sizing_config=SizingConfig()
    )

def test_normal_lift_cruise_vtol(agent, base_request):
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert res.status == "success"
    assert res.sizing_result.mtow_kg > 0
    assert res.geometry_parameter_set.rotor_count == 8
    assert res.geometry_parameter_set.wing_area_m2 is not None

def test_small_helicopter(agent, base_request):
    base_request.aircraft_candidate.aircraft_type = "small_helicopter"
    base_request.mission_profile.mission_distance_m = 3000.0
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert res.status == "success"
    assert res.geometry_parameter_set.rotor_count == 1
    assert res.geometry_parameter_set.wing_area_m2 is None

def test_small_aircraft(agent, base_request):
    base_request.aircraft_candidate.aircraft_type = "small_aircraft"
    base_request.mission_profile.mission_distance_m = 30000.0
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert res.status == "success"
    assert res.geometry_parameter_set.rotor_count is None
    assert res.geometry_parameter_set.wing_area_m2 is not None

def test_missing_mission_distance(agent, base_request):
    base_request.mission_profile.mission_distance_m = None
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert "success" in res.status
    assert "missing" in str(res.warnings).lower()

def test_unknown_aircraft_type_fails(agent, base_request):
    base_request.aircraft_candidate.aircraft_type = "spaceship"
    base_request.sizing_config.allow_template_fallback = False
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert res.status == "failed"

def test_unknown_aircraft_type_fallback(agent, base_request):
    base_request.aircraft_candidate.aircraft_type = "spaceship"
    base_request.sizing_config.allow_template_fallback = True
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert res.status == "success_with_warnings"

def test_negative_distance(agent, base_request):
    base_request.mission_profile.mission_distance_m = -5000.0
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert res.status == "failed"

def test_battery_reserve_too_high(agent, base_request):
    base_request.sizing_config.default_battery_reserve_percent = 90.0
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert "High battery reserve" in res.warnings[0]

def test_non_converging_mtow(agent, base_request):
    base_request.sizing_config.structural_weight_fraction = 0.9 # Unrealistic, won't converge
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert not res.sizing_result.converged
    assert "converge" in str(res.warnings).lower()

def test_requirement_traceability(agent, base_request):
    base_request.final_requirements = [
        FinalRequirement(
            mission_id="MIS-123",
            requirement_id="REQ-CAP",
            title="Passenger Capacity",
            description="Must carry at least 2 passengers.",
            category="performance",
            requirement_type="hard_constraint",
            verification_target="aircraft_candidate",
            priority="high",
            severity="medium",
            source_candidate_ids=["CAND-1"],
            runtime_rule_ready=False,
            rationale="User request",
            variable_name="passenger_capacity",
            operator=">=",
            threshold=2.0
        ),
        FinalRequirement(
            mission_id="MIS-123",
            requirement_id="REQ-ENERGY",
            title="Battery Reserve",
            description="Must have 20% reserve.",
            category="safety",
            requirement_type="hard_constraint",
            verification_target="aircraft_candidate",
            priority="high",
            severity="critical",
            source_candidate_ids=["CAND-2"],
            runtime_rule_ready=False,
            rationale="Safety rules",
            variable_name="battery_percent_at_arrival",
            operator=">=",
            threshold=20.0
        )
    ]
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert len(res.trace_links) >= 2
    assert res.feasibility_report.overall_feasible

def test_ccl_context_provided(agent, base_request):
    base_request.compliance_context = ComplianceContext(
        ccl_item_ids=["CCL-1"]
    )
    state = {"sizing_request": base_request}
    res = agent.run(state)["sizing_agent_result"]
    assert len(res.compliance_artifact_links) > 0
    assert res.compliance_artifact_links[0].ccl_item_id == "CCL-1"
