from typing import Dict, Any
from app.database.repositories.analytics_repository import AnalyticsRepository

class AnalyticsService:
    """
    Coordinates capturing and retrieving operational bot metrics.
    """
    def __init__(self, analytics_repo: AnalyticsRepository):
        self.analytics_repo = analytics_repo

    async def track_api_call(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        latency: float,
        is_new_user: bool = False
    ) -> None:
        """
        Records an API invocation and logs performance data.
        """
        await self.analytics_repo.track_request(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency=latency,
            is_new_user=is_new_user
        )

    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Retrieves consolidated usage statistics across the bot lifetime.
        """
        return await self.analytics_repo.get_overall_stats()
