from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAgent(ABC):
    """
    모든 에이전트의 최상위 부모 클래스입니다.
    상태(state)를 입력받아 처리하고, 업데이트된 상태를 반환하는 기본 인터페이스를 가집니다.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        에이전트의 핵심 실행 로직을 구현합니다.
        
        Args:
            state (Dict[str, Any]): 현재 워크플로우의 상태
            
        Returns:
            Dict[str, Any]: 에이전트 실행 후 업데이트된 상태
        """
        pass


# =====================================================================
# 1. Orchestration Pipeline Base Class
# =====================================================================
class BaseOrchestratorAgent(BaseAgent):
    """
    전체 시스템 흐름 제어, 하위 에이전트 라우팅 및 상태 관리를 담당하는 오케스트레이터의 부모 클래스입니다.
    """
    def __init__(self, name: str = "Orchestrator Agent", description: str = "System workflow manager"):
        super().__init__(name, description)

    @abstractmethod
    def route(self, state: Dict[str, Any]) -> str:
        """
        현재 상태를 기반으로 다음으로 호출할 에이전트(노드)를 결정합니다.
        """
        pass


from aeroloop.llm.factory import LLMFactory
from aeroloop.llm.base import BaseLLMAdapter

# =====================================================================
# 2. AI / Requirements Pipeline Base Class
# =====================================================================
class BaseAIAgent(BaseAgent):
    """
    LLM 기반의 추론, 텍스트 분석, 요구도 정제 등을 수행하는 AI 파이프라인 에이전트의 부모 클래스입니다.
    임무 파싱, 고객 요구도, 인증 요구도, 요구도 정제, 보고서 생성 에이전트 등이 상속받습니다.
    """
    def __init__(self, name: str, description: str, llm_model: Optional[BaseLLMAdapter] = None, model_config: Optional[Dict[str, Any]] = None):
        super().__init__(name, description)
        
        # 외부에서 주입받은 모델이 있으면 사용하고, 없으면 config를 기반으로 Factory를 통해 생성합니다.
        if llm_model:
            self.llm_model = llm_model
        elif model_config:
            self.llm_model = LLMFactory.create_from_config(model_config)
        else:
            self.llm_model = None


# =====================================================================
# 3. Environment & Simulation Pipeline Base Class
# =====================================================================
class BaseSimulationAgent(BaseAgent):
    """
    비행 동역학 모델링, 환경 구축, 시나리오 생성 등 시뮬레이션 파이프라인 에이전트의 부모 클래스입니다.
    비행 시뮬레이션 에이전트, 시나리오 생성 에이전트 등이 상속받습니다.
    """
    def __init__(self, name: str, description: str, simulator_config: Optional[Dict] = None):
        super().__init__(name, description)
        self.simulator_config = simulator_config


# =====================================================================
# 4. Planning Pipeline Base Class
# =====================================================================
class BasePlanningAgent(BaseAgent):
    """
    3D Cost Map 기반 경로 생성 및 실시간 재계획을 수행하는 플래닝 파이프라인 에이전트의 부모 클래스입니다.
    경로 계획 및 재계획 에이전트가 상속받습니다.
    """
    def __init__(self, name: str, description: str):
        super().__init__(name, description)

    @abstractmethod
    def update_cost_map(self, environment_data: Dict[str, Any]) -> None:
        """
        비행 중 또는 사전 계획 시 Cost Map을 업데이트합니다.
        """
        pass


# =====================================================================
# 5. Verification Pipeline Base Class
# =====================================================================
class BaseVerificationAgent(BaseAgent):
    """
    비행 중 또는 설계 결과가 규정 및 요구도를 만족하는지 모니터링하는 검증 파이프라인 에이전트의 부모 클래스입니다.
    비행 중 요구도 검증 에이전트 등이 상속받습니다.
    """
    def __init__(self, name: str, description: str):
        super().__init__(name, description)

    @abstractmethod
    def monitor(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        현재 시뮬레이션 상태를 모니터링하여 위반 여부를 검사합니다.
        """
        pass
