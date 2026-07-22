from typing import List, Dict, Tuple
from app.services.llm.base import LLMProvider

class GeminiProvider(LLMProvider):
    """
    Placeholder implementation for Google Gemini.
    Provides structure for future multi-provider extension.
    """
    def __init__(self):
        pass

    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> Tuple[str, int, int, int]:
        raise NotImplementedError(
            "GeminiProvider is not configured or implemented yet. "
            "Please select a Groq model."
        )
