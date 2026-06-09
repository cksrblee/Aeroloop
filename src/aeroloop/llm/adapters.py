import os
import warnings
from typing import Any, Dict, List
from aeroloop.llm.base import BaseLLMAdapter

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    warnings.warn("langchain-openai 패키지가 설치되지 않았습니다. 기본 LangChain 모듈을 시도합니다.")
    from langchain.chat_models import ChatOpenAI

try:
    from langfuse.callback import CallbackHandler
    HAS_LANGFUSE = True
except ImportError:
    HAS_LANGFUSE = False


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI 모델(gpt-5.4-mini 등)을 사용하기 위한 구체화된 어댑터입니다.
    """
    def __init__(self, model_name: str, temperature: float = 0.0, **kwargs):
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        self.langfuse_handler = None
        if HAS_LANGFUSE and os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            try:
                self.langfuse_handler = CallbackHandler()
            except Exception as e:
                warnings.warn(f"Langfuse 초기화 실패: {e}")

    def _get_config(self) -> dict:
        config = {}
        if self.langfuse_handler:
            config["callbacks"] = [self.langfuse_handler]
        return config

    def _initialize_client(self) -> Any:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            warnings.warn("OPENAI_API_KEY 환경변수가 설정되지 않았습니다. API 호출 시 에러가 발생할 수 있습니다.")
            
        return ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            openai_api_key=api_key,
            **self.kwargs
        )

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.invoke(prompt, config=self._get_config())
        return str(response.content)

    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # LangChain에 맞게 메시지 포맷 변환 (role, content 튜플 리스트)
        formatted_messages = [(msg["role"], msg["content"]) for msg in messages]
        response = self.client.invoke(formatted_messages, config=self._get_config())
        return str(response.content)

    def generate_structured(self, messages: List[Dict[str, str]], schema: Any, **kwargs) -> Any:
        formatted_messages = [(msg["role"], msg["content"]) for msg in messages]
        structured_llm = self.client.with_structured_output(schema)
        response = structured_llm.invoke(formatted_messages, config=self._get_config())
        return response
