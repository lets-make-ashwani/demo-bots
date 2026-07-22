from app.database.repositories import (
    UserRepository, 
    ConversationRepository, 
    MessageRepository, 
    SettingsRepository, 
    AnalyticsRepository
)
from app.services.user_service import UserService
from app.services.memory import MemoryService
from app.services.prompts import PromptService
from app.services.analytics import AnalyticsService
from app.services.llm.groq import GroqProvider
from app.orchestrators.chat_orchestrator import ChatOrchestrator

# Initialize repositories
user_repo = UserRepository()
conv_repo = ConversationRepository()
msg_repo = MessageRepository()
settings_repo = SettingsRepository()
analytics_repo = AnalyticsRepository()

# Initialize services
user_service = UserService(user_repo)
memory_service = MemoryService(msg_repo)
prompt_service = PromptService()
analytics_service = AnalyticsService(analytics_repo)

# Initialize LLM Provider (Groq by default)
llm_provider = GroqProvider()

# Initialize Chat Orchestrator
orchestrator = ChatOrchestrator(
    user_service=user_service,
    memory_service=memory_service,
    prompt_service=prompt_service,
    analytics_service=analytics_service,
    conversation_repo=conv_repo,
    settings_repo=settings_repo,
    llm_provider=llm_provider
)
