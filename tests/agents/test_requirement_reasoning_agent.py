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

if __name__ == "__main__":
    import json
    import argparse
    from pathlib import Path
    from aeroloop.schemas.requirement import CustomerRequirementResult
    from aeroloop.config import config
    from aeroloop.llm.adapters import OpenAIAdapter

    parser = argparse.ArgumentParser(description="Test RequirementReasoningAgent behavior")
    parser.add_argument("--run_id", default="RUN-9af7e667", help="Run ID to test (e.g. RUN-9af7e667)")
    args = parser.parse_args()
    
    run_id = args.run_id
    base_dir = Path(f"/root/projects/AeroLoop/results/default_user/{run_id}")
    cr_file = base_dir / "customer_requirements_result.json"
    mp_file = base_dir / "mission_parsing_result.json"
    
    if not cr_file.exists():
        print(f"File not found: {cr_file}")
        import sys
        sys.exit(1)
        
    print(f"Loading Customer Requirements from {cr_file.name}")
    with open(cr_file, "r", encoding="utf-8") as f:
        cr_data = json.load(f)
    req_result = CustomerRequirementResult(**cr_data)
    
    if mp_file.exists():
        print(f"Loading Mission Profile from {mp_file.name}")
        with open(mp_file, "r", encoding="utf-8") as f:
            mp_data = json.load(f)
            mission_profile = MissionProfile(**mp_data.get("mission_profile", {}))
    else:
        print("Mission profile not found, creating empty.")
        mission_profile = MissionProfile(mission_id=req_result.mission_id)
        
    print(f"\nInitial Mission Profile Passenger Count: {mission_profile.passenger_count}")
        
    reasoning_input = RequirementReasoningInput(
        run_id=run_id,
        mission_profile=mission_profile,
        candidate_requirements=req_result.candidate_requirements,
        unresolved_questions=req_result.unresolved_questions
    )
    
    adapter = OpenAIAdapter(model_name=config.llm_model_name, temperature=config.llm_temperature)
    agent = RequirementReasoningAgent(llm_model=adapter)
    
    print("\nRunning RequirementReasoningAgent.refine()...")
    result = agent.refine(reasoning_input)
    
    print("\n--- Reasoning Result ---")
    if result.concept_baseline:
        print(f"Final Concept Baseline Passenger Count: {result.concept_baseline.passenger_count}")
    else:
        print("Final Concept Baseline is None.")
    
    print(f"\nResolved Assumptions: {len(result.resolved_assumptions)}")
    for a in result.resolved_assumptions:
        print(f" - Q: {a.question}")
        print(f"   Assumed: {a.assumed_value}")
