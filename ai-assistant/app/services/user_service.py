from typing import Optional, Dict, Any
from app.database.repositories.user_repository import UserRepository

class UserService:
    """
    Service layer for managing user profiles and operational metadata.
    """
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        return await self.user_repo.create_or_update_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language=language
        )

    async def update_last_seen(self, telegram_id: int) -> None:
        await self.user_repo.update_last_seen(telegram_id)

    async def increment_user_stats(self, telegram_id: int, tokens: int) -> None:
        await self.user_repo.increment_stats(telegram_id, tokens)
