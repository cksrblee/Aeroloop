import os
import warnings
from typing import Any, Dict, List
from aeroloop.llm.base import BaseLLMAdapter

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    warnings.warn("langchain-openai 패키지가 설치되지 않았습니다. 기본 LangChain 모듈을 시도합니다.")
    from langchain.chat_models import ChatOpenAI


class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI 모델(gpt-4o-mini 등)을 사용하기 위한 구체화된 어댑터입니다.
    """
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
        response = self.client.invoke(prompt)
        return str(response.content)

    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # LangChain에 맞게 메시지 포맷 변환 (role, content 튜플 리스트)
        formatted_messages = [(msg["role"], msg["content"]) for msg in messages]
        response = self.client.invoke(formatted_messages)
        return str(response.content)
