import time
from typing import Dict, Any, Optional
from bson import ObjectId
from app.orchestrators.base import BaseOrchestrator
from app.services.user_service import UserService
from app.services.memory.memory_service import MemoryService
from app.services.prompts.prompt_service import PromptService
from app.services.analytics.analytics_service import AnalyticsService
from app.services.llm.base import LLMProvider
from app.database.repositories.conversation_repository import ConversationRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.utils.logger import api_logger, error_logger

class ChatOrchestrator(BaseOrchestrator):
    """
    Main orchestration class coordinating state, settings, token-pruned memory,
    the active LLM, repository writes, and performance tracking.
    """
    def __init__(
        self,
        user_service: UserService,
        memory_service: MemoryService,
        prompt_service: PromptService,
        analytics_service: AnalyticsService,
        conversation_repo: ConversationRepository,
        settings_repo: SettingsRepository,
        llm_provider: LLMProvider
    ):
        self.user_service = user_service
        self.memory_service = memory_service
        self.prompt_service = prompt_service
        self.analytics_service = analytics_service
        self.conversation_repo = conversation_repo
        self.settings_repo = settings_repo
        self.llm_provider = llm_provider

    async def handle_message(self, user_id: int, text: str) -> str:
        start_time = time.time()

        # 1. Heartbeat check for user last seen
        await self.user_service.update_last_seen(user_id)

        # 2. Retrieve user preferences
        user_settings = await self.settings_repo.get_by_user_id(user_id)
        preferred_model = user_settings.get("preferred_model")
        temperature = user_settings.get("temperature", 0.7)
        max_history_tokens = user_settings.get("max_history_tokens", 12000)
        system_prompt_profile = user_settings.get("system_prompt", "assistant")

        # Resolve system prompt string content
        system_prompt_content = self.prompt_service.get_prompt_content(system_prompt_profile)

        # 3. Retrieve or create active conversation session
        conversation = await self.conversation_repo.get_last_active_conversation(user_id)
        if not conversation:
            conv_id = await self.conversation_repo.create_conversation(user_id, preferred_model)
        else:
            conv_id = conversation["_id"]
            # Align model in active conversation if changed in user preferences
            if conversation.get("model") != preferred_model:
                await self.conversation_repo.update_one(
                    {"_id": conv_id}, 
                    {"$set": {"model": preferred_model}}
                )

        # 4. Pull token-pruned message logs
        history = await self.memory_service.get_messages_for_llm(
            conversation_id=conv_id,
            system_prompt=system_prompt_content,
            max_history_tokens=max_history_tokens
        )

        # Append current user prompt to message payload passed to LLM provider
        llm_payload = list(history)
        llm_payload.append({"role": "user", "content": text})

        # 5. Invoke selected LLM provider
        try:
            response_text, prompt_tokens, completion_tokens, total_tokens = await self.llm_provider.generate(
                model=preferred_model,
                messages=llm_payload,
                temperature=temperature
            )
        except Exception as e:
            error_logger.error(f"Failed to generate answer via LLM: {e}")
            raise e

        latency = time.time() - start_time

        # 6. Save current user message into database logs
        await self.memory_service.add_message(
            conversation_id=conv_id,
            user_id=user_id,
            role="user",
            content=text,
            model=preferred_model
        )

        # 7. Save model response message into database logs
        await self.memory_service.add_message(
            conversation_id=conv_id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            model=preferred_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_time=latency
        )

        # 8. Mark conversation session update time
        await self.conversation_repo.update_timestamp(conv_id)

        # 9. Update aggregated usage telemetry for user
        await self.user_service.increment_user_stats(user_id, total_tokens)

        # 10. Record performance metrics in global analytics
        await self.analytics_service.track_api_call(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency=latency
        )

        api_logger.info(
            f"Successfully processed message for User {user_id}. "
            f"Latency: {latency:.2f}s | Tokens used: {total_tokens}"
        )

        return response_text
