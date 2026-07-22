import asyncio
from app.utils.logger import bot_logger, error_logger
from app.database.repositories.analytics_repository import AnalyticsRepository

class AnalyticsWorker:
    """
    Background worker that runs periodically to report stats and run telemetry tasks.
    """
    def __init__(self, analytics_repo: AnalyticsRepository, interval_seconds: int = 3600):
        self.analytics_repo = analytics_repo
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task = None
        self._running = False

    def start(self) -> None:
        """
        Starts the background async task.
        """
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            bot_logger.info("Analytics background worker task launched.")

    async def stop(self) -> None:
        """
        Stops and cancels the background worker task.
        """
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            bot_logger.info("Analytics background worker task halted.")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                # Periodic logging task
                stats = await self.analytics_repo.get_overall_stats()
                bot_logger.info(
                    f"[SYSTEM METRICS MONITOR] Active stats: Total Requests={stats['total_requests']}, "
                    f"Total Tokens Used={stats['total_tokens']}, Avg Latency={stats['average_latency']:.2f}s"
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                error_logger.error(f"AnalyticsWorker error: {e}")
