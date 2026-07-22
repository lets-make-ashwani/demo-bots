from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bson import ObjectId
from app.database.repositories.base import BaseRepository

class MessageRepository(BaseRepository):
    def __init__(self):
        super().__init__("messages")

    async def add_message(
        self,
        conversation_id: Any,
        user_id: int,
        role: str,
        content: str,
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        response_time: float = 0.0
    ) -> ObjectId:
        """
        Inserts a new message log into a conversation thread.
        """
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        
        doc = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "response_time": response_time,
            "created_at": datetime.now(timezone.utc)
        }
        return await self.insert_one(doc)

    async def get_conversation_messages(self, conversation_id: Any, limit: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieves all messages for a specific conversation session, ordered chronologically.
        """
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        return await self.find_many(
            {"conversation_id": conversation_id},
            sort=[("created_at", 1)],
            limit=limit
        )

    async def delete_conversation_messages(self, conversation_id: Any) -> int:
        """
        Deletes all messages linked to a specific conversation session.
        """
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        return await self.delete_many({"conversation_id": conversation_id})
