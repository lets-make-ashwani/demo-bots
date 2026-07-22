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
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the /stats command. Shows user metrics.
    """
    user = context.user_data.get("user", {})
    
    total_messages = user.get("total_messages", 0)
    total_tokens = user.get("total_tokens", 0)
    joined_date = user.get("created_at")
    joined_str = joined_date.strftime("%Y-%m-%d") if joined_date else "N/A"
    
    stats_msg = (
        "📊 *Usage Report*\n\n"
        f"✉️ *Total Prompts Sent:* `{total_messages}`\n"
        f"🪙 *Total Tokens Consumed:* `{total_tokens}`\n"
        f"📅 *Registration Date:* `{joined_str}`"
    )
    
    await update.message.reply_text(stats_msg, parse_mode="Markdown")
