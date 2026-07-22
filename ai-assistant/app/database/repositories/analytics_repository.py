from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.database.repositories.base import BaseRepository

class AnalyticsRepository(BaseRepository):
    def __init__(self):
        super().__init__("analytics")

    async def track_request(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        latency: float,
        is_new_user: bool = False
    ) -> None:
        """
        Increments performance metrics for the current date (YYYY-MM-DD).
        """
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        total_tokens = prompt_tokens + completion_tokens
        
        await self.collection.update_one(
            {"date": date_str},
            {
                "$inc": {
                    "requests": 1,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "users": 1 if is_new_user else 0,
                    "total_latency": latency
                },
                "$setOnInsert": {
                    "date": date_str
                }
            },
            upsert=True
        )

    async def get_analytics_for_date(self, date_str: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves statistics for a specific date.
        """
        return await self.find_one({"date": date_str})

    async def get_overall_stats(self) -> Dict[str, Any]:
        """
        Aggregates stats across all logged metrics.
        """
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_requests": {"$sum": "$requests"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_latency": {"$sum": "$total_latency"},
                    "total_days": {"$sum": 1}
                }
            }
        ]
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        if results:
            res = results[0]
            avg_latency = res["total_latency"] / res["total_requests"] if res["total_requests"] > 0 else 0.0
            return {
                "total_requests": res["total_requests"],
                "total_tokens": res["total_tokens"],
                "average_latency": avg_latency,
                "total_days": res["total_days"]
            }
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "average_latency": 0.0,
            "total_days": 0
        }
