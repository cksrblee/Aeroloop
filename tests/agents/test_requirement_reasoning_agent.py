import pytest
from unittest.mock import MagicMock
from aeroloop.agents.requirement_reasoning_agent import RequirementReasoningAgent
from aeroloop.schemas.requirement import RequirementReasoningInput, CandidateRequirement
from aeroloop.schemas.mission import MissionProfile

@pytest.fixture
def mock_llm():
    mock = MagicMock()
    # Mock a valid JSON response from the LLM
    mock.generate.return_value = """
    {
      "final_requirements": [
        {
          "requirement_id": "REQ-001",
          "title": "Payload Requirement",
          "description": "The aircraft must carry the assumed payload.",
          "category": "performance",
          "requirement_type": "hard_constraint",
          "variable_name": "payload_kg",
          "operator": ">=",
          "threshold": 400,
          "source_candidate_ids": [],
          "rationale": "Derived from baseline assumptions."
        }
      ],
      "resolved_assumptions": [
        {
          "question": "What is the expected payload weight for a 4 passenger VTOL?",
          "assumed_value": "400 kg",
          "rationale": "Standard baseline of 100kg per passenger.",
          "confidence": 0.9
        }
      ],
      "remaining_unresolved_questions": [],
      "conflicts_detected": []
    }
    """
    return mock

def test_requirement_reasoning_success(mock_llm):
    # Setup agent with mocked LLM
    agent = RequirementReasoningAgent(llm_model=mock_llm)
    
    # Disable KB to prevent ChromaDB startup during tests
    agent.kb = None 

    mission = MissionProfile(
        mission_id="M-TEST",
        mission_type="passenger_transport"
    )

    req_input = RequirementReasoningInput(
        run_id="RUN-TEST",
        mission_profile=mission,
        candidate_requirements=[],
        unresolved_questions=[
            "What is the expected payload weight for a 4 passenger VTOL?"
        ]
    )

    # Execute
    result = agent.refine(req_input)

    # Verify
    assert result.status == "success"
    assert len(result.final_requirements) == 1
    assert result.final_requirements[0].variable_name == "payload_kg"
    assert result.final_requirements[0].threshold == 400

    assert len(result.resolved_assumptions) == 1
    assert result.resolved_assumptions[0].assumed_value == "400 kg"
    
    assert len(result.remaining_unresolved_questions) == 0

def test_requirement_reasoning_needs_hitl():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = """
    {
      "final_requirements": [],
      "resolved_assumptions": [],
      "remaining_unresolved_questions": ["Is this a military or civil aircraft?"],
      "conflicts_detected": []
    }
    """
    agent = RequirementReasoningAgent(llm_model=mock_llm)
    agent.kb = None 
    
    mission = MissionProfile(mission_id="M-TEST", mission_type="unknown")
    req_input = RequirementReasoningInput(
        run_id="RUN-TEST",
        mission_profile=mission,
        candidate_requirements=[],
        unresolved_questions=["Is this a military or civil aircraft?"]
    )
    
    result = agent.refine(req_input)
    
    # Verify it correctly routes to needs_hitl if questions remain
    assert result.status == "needs_hitl"
    assert len(result.remaining_unresolved_questions) == 1
    assert result.remaining_unresolved_questions[0] == "Is this a military or civil aircraft?"
