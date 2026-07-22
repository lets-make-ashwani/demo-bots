import functools
from telegram import Update
from telegram.ext import ContextTypes
from app.database.repositories.user_repository import UserRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.utils.logger import bot_logger

user_repo = UserRepository()
settings_repo = SettingsRepository()

def authenticate_user(func):
    """
    Middleware decorator to register/update user profile in MongoDB 
    and store details in context.user_data.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return
            
        tg_user = update.effective_user
        telegram_id = tg_user.id
        username = tg_user.username
        first_name = tg_user.first_name
        last_name = tg_user.last_name
        language = tg_user.language_code or "en"
        
        # Upsert user record
        user = await user_repo.create_or_update_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language=language
        )
        
        # Initialize default settings if not exists
        await settings_repo.get_by_user_id(telegram_id)
        
        # Store in session context
        context.user_data["user"] = user
        
        return await func(update, context, *args, **kwargs)
    return wrapper
