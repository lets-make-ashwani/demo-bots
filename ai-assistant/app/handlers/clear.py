from telegram import Update
from telegram.ext import ContextTypes
from app.middlewares import (
    handle_exceptions, 
    log_request, 
    authenticate_user, 
    rate_limit
)
from app.dependencies import conv_repo, msg_repo, settings_repo

@handle_exceptions
@log_request
@authenticate_user
@rate_limit
async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the /clear command. Resets conversation history.
    """
    user_id = update.effective_user.id
    
    # Retrieve user's last active conversation
    conversation = await conv_repo.get_last_active_conversation(user_id)
    if conversation:
        conv_id = conversation["_id"]
        # Delete messages in active conversation
        await msg_repo.delete_conversation_messages(conv_id)
        # Delete the conversation document
        await conv_repo.delete_conversation(conv_id)
        
    # Get user preferred model to initialize new conversation
    user_settings = await settings_repo.get_by_user_id(user_id)
    preferred_model = user_settings.get("preferred_model", "llama-3.3-70b-versatile")
    
    # Spin up a brand new conversation thread
    await conv_repo.create_conversation(user_id, preferred_model)
    
    await update.message.reply_text("🧹 History erased. A fresh conversation session has been initialized.")
