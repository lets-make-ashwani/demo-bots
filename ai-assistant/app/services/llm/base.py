from abc import ABC, abstractmethod
from typing import List, Dict, Tuple

class LLMProvider(ABC):
    """
    Abstract LLM Provider interface defining generation method.
    """
    @abstractmethod
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> Tuple[str, int, int, int]:
        """
        Sends message history to the LLM.
        Returns:
            Tuple[response_text, prompt_tokens, completion_tokens, total_tokens]
        """
        pass
