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
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the /help command.
    """
    help_text = (
        "🤖 **AI Assistant Command Guide**\n\n"
        "Here are the commands you can use:\n"
        "• /start \\- Initialize the bot and register\n"
        "• /help \\- View this help guide\n"
        "• /ping \\- Verify bot latency and connectivity\n"
        "• /clear \\- Erase all history for your active conversation thread\n"
        "• /model \\- Switch or inspect the active LLM model\n"
        "• /settings \\- Change custom parameters (system prompt, temperature)\n"
        "• /stats \\- Inspect personal message and token stats"
    )
    # Using MarkdownV2
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")
