from telegram import Update
from telegram.ext import ContextTypes
from app.middlewares import (
    handle_exceptions, 
    log_request, 
    authenticate_user, 
    rate_limit
)

@handle_exceptions
@log_request
@authenticate_user
@rate_limit
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the /start command.
    """
    user = context.user_data.get("user", {})
    name = user.get("first_name", "there")
    
    greeting = (
        f"👋 Hello {name}!\n\n"
        f"I am your production-ready AI Assistant. I feature persistent memory, "
        f"dynamic system prompt switching, and rate limiting.\n\n"
        f"💡 Type /help to see all available commands."
    )
    
    await update.message.reply_text(greeting)
