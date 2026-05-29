import sys
import unittest
from unittest.mock import patch, MagicMock

from aeroloop.agents.mission_parsing_agent import MissionParsingAgent
from aeroloop.schemas.mission import MissionParsingInput, MissionParsingResult, MissionProfile
from aeroloop.schemas.common import MissingField

class MockLLM:
    def __init__(self):
        self.call_count = 0

    def generate_structured(self, messages, schema):
        self.call_count += 1
        
        if self.call_count == 1:
            # First call returns missing fields
            return MissionParsingResult(
                mission_id="mock_mission",
                raw_input="dummy",
                mission_profile=MissionProfile(
                    operation_area="City",
                    origin="A", destination="B",
                    payload_kg=None, passenger_count=None,
                    vehicle_type_hint=None,
                    max_range_km=None, max_altitude_m=None, cruise_speed_m_s=None
                ),
                explicit_constraints=[],
                implicit_constraint_candidates=[],
                requirement_seed_candidates=[],
                runtime_monitoring_candidates=[],
                ambiguities=[],
                missing_fields=[
                    MissingField(field_name="payload_kg", description="Payload needed", suggested_question="What is the payload in kg?", severity="high", reason="Not found")
                ],
                assumptions=[]
            )
        else:
            # Second call returns success
            return MissionParsingResult(
                mission_id="mock_mission",
                raw_input="dummy",
                mission_profile=MissionProfile(
                    operation_area="City",
                    origin="A", destination="B",
                    payload_kg=50.0, passenger_count=None,
                    vehicle_type_hint=None,
                    max_range_km=None, max_altitude_m=None, cruise_speed_m_s=None
                ),
                explicit_constraints=[],
                implicit_constraint_candidates=[],
                requirement_seed_candidates=[],
                runtime_monitoring_candidates=[],
                ambiguities=[],
                missing_fields=[],
                assumptions=[]
            )

class TestInteractiveAgent(unittest.TestCase):
    @patch('builtins.input', return_value="50kg")
    def test_interactive_loop(self, mock_input):
        agent = MissionParsingAgent()
        agent.llm_model = MockLLM()
        
        raw_input = MissionParsingInput(mission_id="mock_mission", raw_user_input="fly A to B")
        result = agent.parse(raw_input)
        
        # Verify it called the LLM twice
        self.assertEqual(agent.llm_model.call_count, 2)
        # Verify there are no missing fields in final result
        self.assertEqual(len(result.missing_fields), 0)
        # Verify input was called once
        self.assertEqual(mock_input.call_count, 1)

if __name__ == '__main__':
    unittest.main()
