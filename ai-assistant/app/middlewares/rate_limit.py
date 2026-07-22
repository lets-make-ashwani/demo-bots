import functools
import time
from telegram import Update
from telegram.ext import ContextTypes
from app.utils.logger import bot_logger

# In-memory sliding window rate tracker: user_id -> List[timestamp]
_user_history = {}

def rate_limit(func):
    """
    Middleware decorator enforcing sliding-window rate limits per user:
    - 2 requests / second
    - 10 requests / minute
    - 100 requests / hour
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user or not update.message:
            return await func(update, context, *args, **kwargs)

        user_id = update.effective_user.id
        now = time.time()

        if user_id not in _user_history:
            _user_history[user_id] = []

        # Prune timestamps older than 1 hour (3600 seconds)
        _user_history[user_id] = [t for t in _user_history[user_id] if now - t < 3600]
        user_timestamps = _user_history[user_id]

        # 1. 2 requests per second check
        last_sec = [t for t in user_timestamps if now - t < 1.0]
        if len(last_sec) >= 2:
            bot_logger.warning(f"Rate limit triggered: User {user_id} exceeded 2 req/sec.")
            await update.message.reply_text("⚠️ Slow down! Please wait a moment.")
            return

        # 2. 10 requests per minute check
        last_min = [t for t in user_timestamps if now - t < 60.0]
        if len(last_min) >= 10:
            bot_logger.warning(f"Rate limit triggered: User {user_id} exceeded 10 req/min.")
            await update.message.reply_text("⚠️ You are sending messages too quickly. Please wait a minute.")
            return

        # 3. 100 requests per hour check
        if len(user_timestamps) >= 100:
            bot_logger.warning(f"Rate limit triggered: User {user_id} exceeded 100 req/hour.")
            await update.message.reply_text("⚠️ Hourly message limit exceeded. Please try again later.")
            return

        # Record message time
        _user_history[user_id].append(now)

        return await func(update, context, *args, **kwargs)
    return wrapper
