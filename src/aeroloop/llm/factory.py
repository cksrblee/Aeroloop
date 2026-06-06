from typing import Optional, Any
from aeroloop.llm.base import BaseLLMAdapter
from aeroloop.llm.adapters import OpenAIAdapter

class LLMFactory:
    """
    설정된 모델 프로바이더에 따라 적절한 LLM 어댑터를 생성하여 반환하는 팩토리(Factory) 및 라우터 클래스입니다.
    """
    
    @staticmethod
    def create(provider: str, model_name: str, temperature: float = 0.0, **kwargs) -> BaseLLMAdapter:
        """
        주어진 provider 문자열에 기반하여 어댑터 인스턴스를 생성합니다.
        
        Args:
            provider (str): "openai", "anthropic", "gemini", "local" 등
            model_name (str): 사용할 실제 모델명 (예: "gpt-5.4-mini")
            temperature (float): 생성 온도
            
        Returns:
            BaseLLMAdapter: 초기화된 LLM 어댑터
        """
        provider = provider.lower()
        
        if provider == "openai":
            return OpenAIAdapter(model_name=model_name, temperature=temperature, **kwargs)
            
        # 추후 다른 모델이 추가될 때 아래 주석을 해제하고 구현합니다.
        # elif provider == "anthropic":
        #     return AnthropicAdapter(model_name=model_name, temperature=temperature, **kwargs)
        # elif provider == "gemini":
        #     return GeminiAdapter(model_name=model_name, temperature=temperature, **kwargs)
            
        else:
            raise ValueError(f"지원하지 않는 LLM 프로바이더입니다: {provider}")

    @staticmethod
    def create_from_config(config_dict: dict) -> BaseLLMAdapter:
        """
        YAML 등의 설정 딕셔너리로부터 직접 어댑터를 생성합니다.
        """
        provider = config_dict.get("provider", "openai")
        model_name = config_dict.get("model", "gpt-5.4-mini")
        temperature = config_dict.get("temperature", 0.0)
        
        return LLMFactory.create(
            provider=provider, 
            model_name=model_name, 
            temperature=temperature
        )
