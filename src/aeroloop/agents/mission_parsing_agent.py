import json
from typing import Any, Dict

try:
    from langfuse.decorators import observe
except ImportError:
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.mission import MissionParsingInput, MissionParsingResult

class MissionParsingAgent(BaseAIAgent):
    """
    Parses the mission entered by the user in natural language and converts it into a structured MissionParsingResult.
    """
    def __init__(self, **kwargs):
        super().__init__(
            name="Mission Parsing Agent",
            description="Parses natural language mission facts into structured MissionParsingResult.",
            **kwargs
        )

    def _build_default_prompt(self) -> str:
        return """
You are the MissionParsingAgent for the AeroLoop conceptual design and simulation environment.
Your task is to parse a natural language mission description and produce a fully structured JSON output.

### Core Responsibilities:
1. Extract explicit mission information (operation area, origin, destination, payload, etc.).
2. Normalize ALL numeric values to SI units (m, m/s, kg, s, %, dB). Always store both original and normalized values.
3. Distinguish explicit constraints (stated directly) from implicit constraint candidates (inferred from context).
4. Detect missing fields critical for sizing, routing, or simulation. For each missing field, provide a suggested_question.
5. Identify ambiguous expressions (e.g., "fast", "safe", "close to buildings") and record them as Ambiguity objects.
6. Provide EvidenceSpan for each extracted field with source_text and character positions.
7. Generate RequirementSeed objects for each extracted constraint or operational fact.
8. Generate RuntimeMonitoringCandidate for EVERY explicit constraint so it can be monitored during simulation.

### MANDATORY: Requirement Seeds & Runtime Monitoring Candidates
For every constraint you extract (e.g., "altitude <= 120m"), you MUST:
- Create a RequirementSeed with: seed_id (RS-001, RS-002, ...), source ("user_input"), category, raw_statement, parsed_variable, parsed_condition, target_downstream_agent list, confidence.
- Create a RuntimeMonitoringCandidate with: requirement_seed_id matching the seed, monitorable (true/false), simulation_variable, violation_condition (the inverted form e.g. "altitude > 120"), required_data_source list.

Example for "altitude <= 120m":
  RequirementSeed: seed_id="RS-001", category="operational_safety", parsed_variable="altitude", parsed_condition="<= 120 m", target_downstream_agent=["CustomerRequirementAgent", "AirspaceEnvironmentAgent", "RuntimeRequirementVerificationAgent"]
  RuntimeMonitoringCandidate: requirement_seed_id="RS-001", monitorable=true, simulation_variable="altitude", violation_condition="altitude > 120", required_data_source=["flight_log.altitude"]

Example for "obstacle clearance >= 10m":
  RequirementSeed: seed_id="RS-002", category="operational_safety", parsed_variable="aircraft_obstacle_distance", parsed_condition=">= 10 m", target_downstream_agent=["CustomerRequirementAgent", "AirspaceEnvironmentAgent", "RuntimeRequirementVerificationAgent"]
  RuntimeMonitoringCandidate: requirement_seed_id="RS-002", monitorable=true, simulation_variable="aircraft_obstacle_distance", violation_condition="aircraft_obstacle_distance < 10", required_data_source=["aircraft_position", "building_proxy_map", "occupancy_grid"]

### CRITICAL RULES:
- DO NOT invent or assume values not present in the input. Use null and create a MissingField instead.
- DO NOT act as a final Requirement Generator. You are a Mission Understanding & Structuring Agent.
- DO NOT make design decisions (e.g., choosing a specific aircraft model).
- ALWAYS produce requirement_seed_candidates and runtime_monitoring_candidates for every explicit constraint.

The output must strictly follow the schema structure provided.
"""


    @observe()
    def parse(self, raw_input: MissionParsingInput, previous_result: MissionParsingResult = None, human_input: str = None) -> MissionParsingResult:
        """
        Extracts explicit mission facts from the user's natural language mission description.
        """
        # 1. Fetch LLM prompt
        try:
            prompt_template = self.prompt_provider.get_prompt("aeroloop/mission-parsing-agent", label="staging")
            system_prompt = self._build_default_prompt()
        except Exception:
            system_prompt = self._build_default_prompt()

        user_content = f"User Input: {raw_input.raw_user_input}\n"
        if raw_input.user_context:
            user_content += f"User Context: {json.dumps(raw_input.user_context, ensure_ascii=False)}\n"
        
        system_msg = {"role": "system", "content": system_prompt}
        user_msg = {"role": "user", "content": user_content}
        
        messages = [system_msg, user_msg]

        if not self.llm_model:
            raise ValueError("LLM model is not configured for MissionParsingAgent.")

        if previous_result and human_input:
            messages.append({
                "role": "assistant",
                "content": previous_result.model_dump_json()
            })
            if human_input.strip().lower() == 'skip':
                messages.append({
                    "role": "system",
                    "content": "The user has chosen to skip providing the missing information. You MUST now INFER the most likely reasonable default values for all missing fields based on standard domain knowledge (e.g. Urban Air Mobility, eVTOL operations). Populate the missing fields in the mission_profile, completely empty the missing_fields list (return an empty array []), and create a corresponding Assumption object for each inferred field stating the assumed value and reason."
                })
            else:
                messages.append({
                    "role": "user",
                    "content": human_input
                })
                
        result = self.llm_model.generate_structured(messages, MissionParsingResult)
        
        # Ensure the input references match
        if result.mission_id != raw_input.mission_id:
            result.mission_id = raw_input.mission_id
        if result.raw_input != raw_input.raw_user_input:
            result.raw_input = raw_input.raw_user_input
        
        # Programmatic safeguard
        if previous_result and human_input and human_input.strip().lower() == 'skip' and result.missing_fields:
            print("\n[MissionParsingAgent] Warning: LLM did not empty missing_fields. Forcing it to be empty to proceed.")
            result.missing_fields = []
            
        return result

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Method maintained for compatibility with existing systems (like LangGraph).
        """
        # Extract MissionParsingInput from state
        raw_input = state.get("raw_input")
        if isinstance(raw_input, dict):
            raw_input = MissionParsingInput(**raw_input)
        elif not isinstance(raw_input, MissionParsingInput):
            # Create a fallback or raise depending on workflow rules
            # Here we just assume it's missing and skip or error out
            if "raw_text" in state:
                raw_input = MissionParsingInput(
                    mission_id=state.get("mission_id", "unknown_mission"),
                    raw_user_input=state["raw_text"]
                )
            else:
                return state

        result = self.parse(raw_input)
        state["mission_parsing_result"] = result
        return state

