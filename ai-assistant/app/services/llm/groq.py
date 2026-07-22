from typing import List, Dict, Tuple
from groq import AsyncGroq
from app.services.llm.base import LLMProvider
from app.config import settings
from app.utils.logger import api_logger, error_logger
from app.utils.retry import async_retry

class GroqProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.groq_api_key)

    @async_retry(tries=3, delay=1.0, backoff=2.0)
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> Tuple[str, int, int, int]:
        """
        Sends messages to Groq API using AsyncGroq client.
        """
        try:
            api_logger.info(f"Sending request to Groq API using model: {model}")
            completion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            choice = completion.choices[0]
            content = choice.message.content or ""
            
            usage = completion.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            
            api_logger.info(
                f"Groq generation successful. Prompt tokens: {prompt_tokens}, "
                f"Completion tokens: {completion_tokens}, Total tokens: {total_tokens}"
            )
            
            return content, prompt_tokens, completion_tokens, total_tokens
        except Exception as e:
            error_logger.error(f"Failed to generate completion from Groq: {e}")
            raise e
