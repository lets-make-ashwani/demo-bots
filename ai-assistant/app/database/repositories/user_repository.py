from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.database.repositories.base import BaseRepository

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users")

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a user by their Telegram ID.
        """
        return await self.find_one({"telegram_id": telegram_id})

    async def create_or_update_user(
        self,
        telegram_id: int,
        username: Optional[str],
        first_name: str,
        last_name: Optional[str],
        language: str
    ) -> Dict[str, Any]:
        """
        Updates user metadata, creating the record if it doesn't already exist.
        """
        now = datetime.now(timezone.utc)
        user_data = {
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "language": language,
            "updated_at": now,
            "last_seen": now
        }
        
        await self.collection.update_one(
            {"telegram_id": telegram_id},
            {
                "$set": user_data,
                "$setOnInsert": {
                    "telegram_id": telegram_id,
                    "total_messages": 0,
                    "total_tokens": 0,
                    "created_at": now
                }
            },
            upsert=True
        )
        return await self.get_by_telegram_id(telegram_id)

    async def update_last_seen(self, telegram_id: int) -> None:
        """
        Updates the last_seen timestamp for a user.
        """
        await self.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"last_seen": datetime.now(timezone.utc)}}
        )

    async def increment_stats(self, telegram_id: int, tokens: int) -> None:
        """
        Increments the total messages and token counts for a user.
        """
        await self.update_one(
            {"telegram_id": telegram_id},
            {
                "$inc": {
                    "total_messages": 1,
                    "total_tokens": tokens
                },
                "$set": {"last_seen": datetime.now(timezone.utc)}
            }
        )
