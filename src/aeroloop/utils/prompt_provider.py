import os
from typing import Any, Optional

try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None

class PromptProvider:
    """
    Wrapper for the Langfuse client to provide prompts.
    Centralizes prompt fetching and version/label management.
    """
    def __init__(self, langfuse_client: Optional[Any] = None):
        # Initialize with provided client or create a new one (relies on env variables)
        if langfuse_client is not None:
            self.client = langfuse_client
        elif Langfuse is not None:
            self.client = Langfuse()
        else:
            self.client = None

    def get_prompt(self, name: str, label: str = "staging"):
        """
        Fetches a prompt from Langfuse by name and label.
        
        Args:
            name (str): The name of the prompt (e.g., 'aeroloop/mission-parsing-agent')
            label (str): The label of the prompt (e.g., 'staging', 'production')
            
        Returns:
            The Langfuse prompt object, which can be compiled with variables.
        """
        if self.client is None:
            raise RuntimeError(
                "Langfuse is not installed or configured; provide a langfuse_client "
                "or install the optional langfuse dependency."
            )

        try:
            prompt = self.client.get_prompt(name, label=label)
            return prompt
        except Exception as e:
            # Fallback or logging could be added here
            print(f"Warning: Failed to fetch prompt '{name}' with label '{label}' from Langfuse. Error: {e}")
            raise

    def compile_prompt(self, name: str, label: str = "staging", **kwargs) -> str:
        """
        Fetches a prompt and compiles it with the given kwargs.
        
        Args:
            name (str): The name of the prompt
            label (str): The label of the prompt
            **kwargs: Variables to fill into the prompt template
            
        Returns:
            str: The compiled prompt string
        """
        prompt = self.get_prompt(name, label=label)
        return prompt.compile(**kwargs)
