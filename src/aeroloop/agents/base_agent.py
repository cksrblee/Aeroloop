from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from aeroloop.llm.factory import LLMFactory
from aeroloop.llm.base import BaseLLMAdapter
from aeroloop.utils.prompt_provider import PromptProvider

try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = Any


class BaseAgent(ABC):
    """
    Top-level abstract base class for all AeroLoop agents.
    Provides a standardized interface to process an input state and return an updated state.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the core logic of the agent.
        
        Args:
            state (Dict[str, Any]): Current workflow state dictionary.
            
        Returns:
            Dict[str, Any]: Updated workflow state dictionary after execution.
        """
        pass


# =====================================================================
# 1. Orchestration Pipeline Base Class
# =====================================================================
class BaseOrchestratorAgent(BaseAgent):
    """
    Abstract base class for orchestrator agents responsible for system flow control,
    sub-agent routing, and state lifecycle management.
    """
    def __init__(self, name: str = "Orchestrator Agent", description: str = "System workflow manager"):
        super().__init__(name, description)

    @abstractmethod
    def route(self, state: Dict[str, Any]) -> str:
        """
        Determines the next agent/node to execute based on the current state.
        """
        pass


# =====================================================================
# 2. AI / Requirements Pipeline Base Class
# =====================================================================
class BaseAIAgent(BaseAgent):
    """
    Base class for LLM-powered agents performing reasoning, requirement extraction,
    conflict synthesis, and report generation.
    """
    def __init__(
        self, 
        name: str, 
        description: str, 
        llm_model: Optional[BaseLLMAdapter] = None, 
        model_config: Optional[Dict[str, Any]] = None,
        prompt_provider: Optional[PromptProvider] = None,
        langfuse_client: Optional[Langfuse] = None
    ):
        super().__init__(name, description)
        
        self.prompt_provider = prompt_provider or PromptProvider(langfuse_client)
        self.langfuse_client = langfuse_client or self.prompt_provider.client
        
        # Use injected model if provided, otherwise instantiate via factory if config exists
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
    Base class for simulation pipeline agents handling flight dynamics,
    environment creation, and scenario synthesis.
    """
    def __init__(self, name: str, description: str, simulator_config: Optional[Dict] = None):
        super().__init__(name, description)
        self.simulator_config = simulator_config


# =====================================================================
# 4. Planning Pipeline Base Class
# =====================================================================
class BasePlanningAgent(BaseAgent):
    """
    Base class for planning pipeline agents performing 3D cost map trajectory generation
    and real-time replanning.
    """
    def __init__(self, name: str, description: str):
        super().__init__(name, description)

    @abstractmethod
    def update_cost_map(self, environment_data: Dict[str, Any]) -> None:
        """
        Updates the 3D cost map prior to flight or dynamically during mission execution.
        """
        pass


# =====================================================================
# 5. Verification Pipeline Base Class
# =====================================================================
class BaseVerificationAgent(BaseAgent):
    """
    Base class for verification pipeline agents monitoring whether flight telemetry
    and design outputs satisfy regulatory and mission constraints.
    """
    def __init__(self, name: str, description: str):
        super().__init__(name, description)

    @abstractmethod
    def monitor(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Monitors simulation telemetry and evaluates violation states.
        """
        pass
