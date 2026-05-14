from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseLLMAdapter(ABC):
    """
    다양한 LLM 프로바이더를 일관된 인터페이스로 추상화하기 위한 기본 어댑터 클래스입니다.
    나중에 Anthropic, Google Gemini, 로컬 오픈소스 모델 등을 쉽게 추가할 수 있도록 설계되었습니다.
    """
    def __init__(self, model_name: str, temperature: float = 0.0, **kwargs):
        self.model_name = model_name
        self.temperature = temperature
        self.kwargs = kwargs
        self.client = self._initialize_client()

    @abstractmethod
    def _initialize_client(self) -> Any:
        """실제 LLM 클라이언트(예: LangChain Chat 모델)를 초기화합니다."""
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """단일 텍스트 프롬프트에 대한 응답을 생성합니다."""
        pass

    @abstractmethod
    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        채팅 메시지 목록에 대한 응답을 생성합니다.
        messages 예시: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        """
        pass
        
    def get_langchain_model(self) -> Any:
        """
        LangGraph나 LangChain 체인에 직접 주입할 수 있도록 
        초기화된 LangChain 클라이언트 객체를 반환합니다.
        """
        return self.client
