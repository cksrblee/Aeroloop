from typing import Any, Dict
from aeroloop.agents.base_agent import BaseAIAgent

class MissionParsingAgent(BaseAIAgent):
    """
    사용자가 자연어로 입력한 임무(Mission)를 분석하여 엔지니어링 요구항목 후보로 분해합니다.
    """
    def __init__(self, **kwargs):
        super().__init__(
            name="Mission Parsing Agent",
            description="Parses natural language mission into engineering requirements.",
            **kwargs
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        임무 파싱 에이전트 실행 로직
        """
        # TODO: Implement LLM parsing logic
        return state
