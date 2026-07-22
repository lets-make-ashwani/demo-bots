from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bson import ObjectId
from app.database.repositories.base import BaseRepository

class ConversationRepository(BaseRepository):
    def __init__(self):
        super().__init__("conversations")

    async def create_conversation(self, user_id: int, model: str, title: str = "New Conversation") -> ObjectId:
        """
        Creates a new conversation session record.
        """
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": user_id,
            "title": title,
            "model": model,
            "summary": "",
            "created_at": now,
            "updated_at": now
        }
        return await self.insert_one(doc)

    async def get_user_conversations(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Fetches all conversations for a specific user, sorted by last updated timestamp.
        """
        return await self.find_many({"user_id": user_id}, sort=[("updated_at", -1)])

    async def get_conversation(self, conversation_id: Any) -> Optional[Dict[str, Any]]:
        """
        Retrieves a conversation metadata record.
        """
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        return await self.find_one({"_id": conversation_id})

    async def update_summary(self, conversation_id: Any, summary: str) -> None:
        """
        Saves a summary for the conversation thread.
        """
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        await self.update_one(
            {"_id": conversation_id},
            {
                "$set": {
                    "summary": summary,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

    async def update_timestamp(self, conversation_id: Any) -> None:
        """
        Updates the updated_at field.
        """
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        await self.update_one(
            {"_id": conversation_id},
            {"$set": {"updated_at": datetime.now(timezone.utc)}}
        )

    async def delete_conversation(self, conversation_id: Any) -> None:
        """
        Deletes a conversation record.
        """
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        await self.delete_many({"_id": conversation_id})
        
    async def get_last_active_conversation(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Returns the conversation session that was updated most recently.
        """
        res = await self.find_many({"user_id": user_id}, sort=[("updated_at", -1)], limit=1)
        return res[0] if res else None
