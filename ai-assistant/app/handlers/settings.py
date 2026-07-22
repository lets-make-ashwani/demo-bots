from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.middlewares import (
    handle_exceptions, 
    log_request, 
    authenticate_user, 
    rate_limit
)
from app.dependencies import settings_repo

@handle_exceptions
@log_request
@authenticate_user
@rate_limit
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the /settings command. Shows settings controls.
    """
    user_id = update.effective_user.id
    user_settings = await settings_repo.get_by_user_id(user_id)
    
    prompt = user_settings.get("system_prompt", "assistant")
    temp = user_settings.get("temperature", 0.7)
    
    keyboard = [
        [InlineKeyboardButton(f"🎭 Prompt Profile: {prompt}", callback_data="menu_prompts")],
        [InlineKeyboardButton(f"🌡️ Temperature: {temp}", callback_data="menu_temp")],
        [InlineKeyboardButton("🔄 Reset to Default Settings", callback_data="menu_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ *System Configuration*\n\n"
        f"🎭 *System Prompt Profile:* `{prompt}`\n"
        f"🌡️ *Temperature:* `{temp}`\n\n"
        "Configure parameters below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@handle_exceptions
async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback query handler for settings inline updates.
    """
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "menu_prompts":
        keyboard = [
            [InlineKeyboardButton("Friendly Assistant", callback_data="set_prompt:assistant")],
            [InlineKeyboardButton("Expert Coder", callback_data="set_prompt:coding")],
            [InlineKeyboardButton("Patient Teacher", callback_data="set_prompt:teacher")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_to_main")]
        ]
        await query.edit_message_text(
            "🎭 *Select System Prompt Profile*\n\n"
            "Choose a personality configuration for the bot:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data == "menu_temp":
        keyboard = [
            [
                InlineKeyboardButton("0.2 (Precise)", callback_data="set_temp:0.2"),
                InlineKeyboardButton("0.5 (Balanced)", callback_data="set_temp:0.5")
            ],
            [
                InlineKeyboardButton("0.7 (Default)", callback_data="set_temp:0.7"),
                InlineKeyboardButton("1.0 (Creative)", callback_data="set_temp:1.0")
            ],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_to_main")]
        ]
        await query.edit_message_text(
            "🌡️ *Select Temperature*\n\n"
            "Configure how creative/diverse the response text should be:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data.startswith("set_prompt:"):
        prompt_name = data.split(":", 1)[1]
        await settings_repo.update_settings(user_id, system_prompt=prompt_name)
        await _refresh_main_settings_message(query, user_id)
    elif data.startswith("set_temp:"):
        temp_val = float(data.split(":", 1)[1])
        await settings_repo.update_settings(user_id, temperature=temp_val)
        await _refresh_main_settings_message(query, user_id)
    elif data == "menu_reset":
        await settings_repo.reset_settings(user_id)
        await _refresh_main_settings_message(query, user_id)
    elif data == "back_to_main":
        await _refresh_main_settings_message(query, user_id)

async def _refresh_main_settings_message(query, user_id: int) -> None:
    user_settings = await settings_repo.get_by_user_id(user_id)
    prompt = user_settings.get("system_prompt", "assistant")
    temp = user_settings.get("temperature", 0.7)
    
    keyboard = [
        [InlineKeyboardButton(f"🎭 Prompt Profile: {prompt}", callback_data="menu_prompts")],
        [InlineKeyboardButton(f"🌡️ Temperature: {temp}", callback_data="menu_temp")],
        [InlineKeyboardButton("🔄 Reset to Default Settings", callback_data="menu_reset")]
    ]
    await query.edit_message_text(
        "⚙️ *System Configuration*\n\n"
        f"🎭 *System Prompt Profile:* `{prompt}`\n"
        f"🌡️ *Temperature:* `{temp}`\n\n"
        "Configure parameters below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
