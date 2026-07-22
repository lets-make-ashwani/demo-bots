import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from app.orchestrators.chat_orchestrator import ChatOrchestrator

@pytest.mark.asyncio
async def test_orchestrator_flow() -> None:
    # Set up mocks for services and repos
    user_service = MagicMock()
    user_service.update_last_seen = AsyncMock()
    user_service.increment_user_stats = AsyncMock()
    
    memory_service = MagicMock()
    memory_service.get_messages_for_llm = AsyncMock(
        return_value=[{"role": "system", "content": "You are a helpful AI assistant."}]
    )
    memory_service.add_message = AsyncMock()
    
    prompt_service = MagicMock()
    prompt_service.get_prompt_content = MagicMock(return_value="You are a helpful AI assistant.")
    
    analytics_service = MagicMock()
    analytics_service.track_api_call = AsyncMock()
    
    conversation_repo = MagicMock()
    conversation_repo.get_last_active_conversation = AsyncMock(
        return_value={"_id": ObjectId(), "model": "llama-3.3-70b-versatile"}
    )
    conversation_repo.update_timestamp = AsyncMock()
    
    settings_repo = MagicMock()
    settings_repo.get_by_user_id = AsyncMock(return_value={
        "preferred_model": "llama-3.3-70b-versatile",
        "temperature": 0.7,
        "max_history_tokens": 12000,
        "system_prompt": "assistant"
    })
    
    llm_provider = MagicMock()
    llm_provider.generate = AsyncMock(
        return_value=("Hi there! How can I help you today?", 10, 15, 25)
    )
    
    # Initialize orchestrator with mocked dependencies
    orchestrator = ChatOrchestrator(
        user_service=user_service,
        memory_service=memory_service,
        prompt_service=prompt_service,
        analytics_service=analytics_service,
        conversation_repo=conversation_repo,
        settings_repo=settings_repo,
        llm_provider=llm_provider
    )
    
    # Perform handling
    user_id = 99999
    text = "Hello"
    response = await orchestrator.handle_message(user_id, text)
    
    # Validate calls and responses
    assert response == "Hi there! How can I help you today?"
    user_service.update_last_seen.assert_called_once_with(user_id)
    llm_provider.generate.assert_called_once()
    memory_service.add_message.assert_called()
    user_service.increment_user_stats.assert_called_once_with(user_id, 25)
    analytics_service.track_api_call.assert_called_once()
