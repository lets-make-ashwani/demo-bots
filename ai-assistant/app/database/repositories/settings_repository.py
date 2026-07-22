from typing import Optional, Dict, Any
from app.database.repositories.base import BaseRepository
from app.utils.constants import (
    DEFAULT_MODEL, 
    DEFAULT_TEMPERATURE, 
    DEFAULT_MAX_HISTORY_TOKENS, 
    DEFAULT_LANGUAGE
)

class SettingsRepository(BaseRepository):
    def __init__(self):
        super().__init__("settings")

    async def get_by_user_id(self, user_id: int) -> Dict[str, Any]:
        """
        Gets a user's settings. Creates default settings if none exist.
        """
        settings_doc = await self.find_one({"user_id": user_id})
        if not settings_doc:
            default_settings = {
                "user_id": user_id,
                "system_prompt": "You are a helpful AI assistant.",
                "preferred_model": DEFAULT_MODEL,
                "temperature": DEFAULT_TEMPERATURE,
                "max_history_tokens": DEFAULT_MAX_HISTORY_TOKENS,
                "language": DEFAULT_LANGUAGE
            }
            await self.insert_one(default_settings)
            settings_doc = default_settings
        return settings_doc

    async def update_settings(
        self,
        user_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Updates user-specific setting fields asynchronously.
        """
        valid_fields = ["system_prompt", "preferred_model", "temperature", "max_history_tokens", "language"]
        update_data = {k: v for k, v in kwargs.items() if k in valid_fields and v is not None}
        
        if update_data:
            await self.collection.update_one(
                {"user_id": user_id},
                {"$set": update_data},
                upsert=True
            )
        return await self.get_by_user_id(user_id)

    async def reset_settings(self, user_id: int) -> Dict[str, Any]:
        """
        Resets user settings to system defaults.
        """
        await self.delete_many({"user_id": user_id})
        return await self.get_by_user_id(user_id)
