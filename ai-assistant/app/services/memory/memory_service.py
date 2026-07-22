from typing import List, Dict, Any
from bson import ObjectId
from app.database.repositories.message_repository import MessageRepository
from app.utils.tokenizer import count_tokens
from app.utils.constants import ROLE_SYSTEM

class MemoryService:
    """
    Manages loading, formatting, and pruning conversation memory based on token count limits.
    """
    def __init__(self, message_repo: MessageRepository):
        self.message_repo = message_repo

    async def get_messages_for_llm(
        self,
        conversation_id: Any,
        system_prompt: str,
        max_history_tokens: int = 12000
    ) -> List[Dict[str, str]]:
        """
        Retrieves history for the given conversation, counting tokens backwards, 
        and pruning when limits are hit. Prepends the system prompt at index 0.
        """
        raw_messages = await self.message_repo.get_conversation_messages(conversation_id)
        
        # Calculate base tokens for system prompt
        system_tokens = count_tokens(system_prompt)
        current_tokens = system_tokens
        
        history_to_keep: List[Dict[str, str]] = []
        
        # Scan from newest message back to oldest
        for msg in reversed(raw_messages):
            role = msg["role"]
            content = msg["content"]
            
            # Use cached token count if available, otherwise count it on-the-fly
            msg_tokens = msg.get("total_tokens", 0)
            if not msg_tokens:
                msg_tokens = count_tokens(content)
                
            if current_tokens + msg_tokens > max_history_tokens:
                # Limit reached, stop including older messages
                break
                
            history_to_keep.append({"role": role, "content": content})
            current_tokens += msg_tokens
            
        # Restore chronological order
        history_to_keep.reverse()
        
        # Insert system prompt at the beginning
        history_to_keep.insert(0, {"role": ROLE_SYSTEM, "content": system_prompt})
        
        return history_to_keep

    async def add_message(
        self,
        conversation_id: Any,
        user_id: int,
        role: str,
        content: str,
        model: str = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        response_time: float = 0.0
    ) -> None:
        """
        Persists a message in the conversation logs database.
        """
        if not total_tokens:
            total_tokens = count_tokens(content)
            
        await self.message_repo.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_time=response_time
        )
