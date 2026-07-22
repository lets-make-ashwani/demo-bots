from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.middlewares import (
    handle_exceptions, 
    log_request, 
    authenticate_user, 
    rate_limit
)
from app.dependencies import settings_repo
from app.utils.constants import AVAILABLE_MODELS

@handle_exceptions
@log_request
@authenticate_user
@rate_limit
async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the /model command. Displays an inline keyboard to choose the model.
    """
    user_id = update.effective_user.id
    user_settings = await settings_repo.get_by_user_id(user_id)
    current_model = user_settings.get("preferred_model", "llama-3.3-70b-versatile")
    
    keyboard = []
    for model_id, model_name in AVAILABLE_MODELS.items():
        # Display selected indicator on active model
        display_name = f"✅ {model_name}" if model_id == current_model else model_name
        keyboard.append([InlineKeyboardButton(display_name, callback_data=f"set_model:{model_id}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🤖 *Active Model:* `{current_model}`\n\n"
        f"Select a model from the list below to switch:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@handle_exceptions
async def model_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback query handler for setting the preferred model via inline keyboard.
    """
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data or not data.startswith("set_model:"):
        return
        
    model_id = data.split(":", 1)[1]
    if model_id not in AVAILABLE_MODELS:
        await query.edit_message_text("⚠️ Invalid model selection.")
        return
        
    user_id = query.from_user.id
    await settings_repo.update_settings(user_id, preferred_model=model_id)
    
    await query.edit_message_text(
        f"✅ Model updated successfully!\n\n"
        f"🤖 *Active Model:* `{model_id}`",
        parse_mode="Markdown"
    )
