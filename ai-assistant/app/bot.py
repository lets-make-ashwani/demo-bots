import os
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
)
from app.config import settings
from app.database import db_instance, create_indexes
from app.dependencies import analytics_repo
from app.workers.analytics_worker import AnalyticsWorker
from app.utils.logger import bot_logger, error_logger
from app.handlers import (
    start_handler,
    help_handler,
    clear_handler,
    model_handler,
    model_callback_handler,
    settings_handler,
    settings_callback_handler,
    stats_handler,
    ping_handler,
    chat_handler
)

# Background stats reporting worker
analytics_worker = AnalyticsWorker(analytics_repo, interval_seconds=3600)

async def post_init(application) -> None:
    """
    Executed on bot startup: connects to DB, sets up indexes, and starts workers.
    """
    bot_logger.info("Executing startup init lifecycle hooks...")
    
    # Connect to database
    db_instance.connect()
    
    # Ensure all index constraints
    await create_indexes()
    
    # Start the periodic analytics background daemon
    analytics_worker.start()
    
    bot_logger.info("Bot initialization finished successfully.")

async def post_shutdown(application) -> None:
    """
    Executed on bot shutdown: halts worker and closes connections.
    """
    bot_logger.info("Executing shutdown lifecycle hooks...")
    
    # Halt background worker
    await analytics_worker.stop()
    
    # Terminate database connections
    db_instance.close()
    
    bot_logger.info("Bot shutdown completed.")

def run_telegram_bot() -> None:
    """
    Constructs and executes the python-telegram-bot application.
    """
    if not settings.bot_token:
        error_logger.critical("BOT_TOKEN environment variable not set. Startup aborted.")
        raise ValueError("BOT_TOKEN is required to start the Telegram bot.")

    app = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Command Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("ping", ping_handler))

    # Inline Keyboards Callbacks
    app.add_handler(CallbackQueryHandler(model_callback_handler, pattern=r"^set_model:"))
    app.add_handler(CallbackQueryHandler(settings_callback_handler, pattern=r"^(menu_|set_prompt:|set_temp:|back_to_main)"))

    # Text Chat Messages Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    bot_logger.info("Long polling started.")
    print("Telegram AI Assistant is running. Press Ctrl+C to terminate.")
    
    app.run_polling()
