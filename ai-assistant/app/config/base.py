import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", validation_alias="GROQ_MODEL")
    mongodb_uri: str = Field(
        default=os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://localhost:27017"
    )
    database_name: str = Field(default="telegram_ai_bot", validation_alias="DATABASE_NAME")
    max_history_tokens: int = Field(default=12000, validation_alias="MAX_HISTORY_TOKENS")
    temperature: float = Field(default=0.7, validation_alias="TEMPERATURE")
    max_tokens: int = Field(default=2048, validation_alias="MAX_TOKENS")
    rate_limit_seconds: int = Field(default=2, validation_alias="RATE_LIMIT_SECONDS")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
