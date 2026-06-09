import os
import time
import json
import warnings
from pathlib import Path
from typing import Any, Dict, List
from aeroloop.llm.base import BaseLLMAdapter

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    warnings.warn("langchain-openai 패키지가 설치되지 않았습니다. 기본 LangChain 모듈을 시도합니다.")
    from langchain.chat_models import ChatOpenAI

def _log_llm_call(prompt_or_messages, response_content, method_name):
    """Log LLM interactions to tmp/llm_logs directory."""
    try:
        log_dir = Path("tmp/llm_logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = log_dir / f"llm_log_{timestamp}_{method_name}.json"
        
        # Safely serialize pydantic objects if any
        if hasattr(response_content, "model_dump"):
            output_data = response_content.model_dump()
        else:
            output_data = response_content

        log_data = {
            "method": method_name,
            "timestamp": timestamp,
            "input": prompt_or_messages,
            "output": output_data
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        warnings.warn(f"Failed to log LLM call: {e}")

class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI 모델(gpt-5.4-mini 등)을 사용하기 위한 구체화된 어댑터입니다.
    """
    def __init__(self, model_name: str, temperature: float = 0.0, **kwargs):
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)

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
        content = str(response.content)
        _log_llm_call(prompt, content, "generate")
        return content

    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # LangChain에 맞게 메시지 포맷 변환 (role, content 튜플 리스트)
        formatted_messages = [(msg["role"], msg["content"]) for msg in messages]
        response = self.client.invoke(formatted_messages)
        content = str(response.content)
        _log_llm_call(messages, content, "generate_chat")
        return content

    def generate_structured(self, messages: List[Dict[str, str]], schema: Any, **kwargs) -> Any:
        formatted_messages = [(msg["role"], msg["content"]) for msg in messages]
        structured_llm = self.client.with_structured_output(schema)
        response = structured_llm.invoke(formatted_messages)
        _log_llm_call(messages, response, "generate_structured")
        return response
