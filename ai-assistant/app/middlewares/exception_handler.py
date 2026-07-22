import functools
import traceback
from telegram import Update
from telegram.ext import ContextTypes
from app.utils.logger import error_logger

def handle_exceptions(func):
    """
    Middleware decorator that catches any exceptions raised within handlers,
    logs the stack trace in error.log, and returns a graceful message to the user.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            stack_trace = traceback.format_exc()
            user_id = update.effective_user.id if update.effective_user else "Unknown"
            
            error_logger.error(
                f"Exception in handler '{func.__name__}' for user {user_id}: {e}\n"
                f"Stack Trace:\n{stack_trace}"
            )
            
            # Send standard error message to Telegram
            if update.message:
                await update.message.reply_text(
                    "⚠️ Sorry, an internal server error occurred. Our developers have been notified."
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "⚠️ An internal error occurred. Please try again.", 
                    show_alert=True
                )
    return wrapper
