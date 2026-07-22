from telegram import Update
from telegram.ext import ContextTypes
from app.middlewares import (
    handle_exceptions, 
    log_request, 
    authenticate_user, 
    rate_limit,
    send_typing_action
)
from app.dependencies import orchestrator
from app.utils.markdown import markdown_to_html

@handle_exceptions
@log_request
@authenticate_user
@rate_limit
@send_typing_action
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Standard message handler. Sends typing action and feeds prompt to orchestrator.
    """
    user_id = update.effective_user.id
    prompt_text = update.message.text
    
    # Call orchestration service
    raw_reply = await orchestrator.handle_message(user_id, prompt_text)
    
    # Parse markdown into telegram-compliant HTML
    formatted_reply = markdown_to_html(raw_reply)
    
    # Send formatted response
    await update.message.reply_html(formatted_reply)
