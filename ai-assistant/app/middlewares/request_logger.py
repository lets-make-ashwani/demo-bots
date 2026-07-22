import functools
from telegram import Update
from telegram.ext import ContextTypes
from app.utils.logger import bot_logger

def log_request(func):
    """
    Middleware decorator that logs incoming updates (commands and text messages) 
    with user metadata in bot.log.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return await func(update, context, *args, **kwargs)
            
        user_id = update.effective_user.id
        username = update.effective_user.username or "None"
        
        if update.message and update.message.text:
            text_preview = update.message.text[:100]
            bot_logger.info(f"User {user_id} (@{username}) sent: {text_preview}")
        elif update.callback_query:
            bot_logger.info(f"User {user_id} (@{username}) triggered callback query: {update.callback_query.data}")
            
        return await func(update, context, *args, **kwargs)
    return wrapper
