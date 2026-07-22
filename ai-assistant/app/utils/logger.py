import os
import logging
from logging.handlers import RotatingFileHandler

def setup_loggers():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # General Bot Logger
    bot_logger = logging.getLogger("bot")
    bot_logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup is called multiple times
    if not bot_logger.handlers:
        bot_handler = RotatingFileHandler(
            os.path.join(log_dir, "bot.log"), maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
        )
        bot_handler.setFormatter(formatter)
        bot_logger.addHandler(bot_handler)

    # API Logger
    api_logger = logging.getLogger("api")
    api_logger.setLevel(logging.INFO)
    if not api_logger.handlers:
        api_handler = RotatingFileHandler(
            os.path.join(log_dir, "api.log"), maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
        )
        api_handler.setFormatter(formatter)
        api_logger.addHandler(api_handler)

    # Error Logger
    error_logger = logging.getLogger("error")
    error_logger.setLevel(logging.ERROR)
    if not error_logger.handlers:
        error_handler = RotatingFileHandler(
            os.path.join(log_dir, "error.log"), maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
        )
        error_handler.setFormatter(formatter)
        error_logger.addHandler(error_handler)

    # Add console logging to all
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    if len(bot_logger.handlers) == 1:
        bot_logger.addHandler(console_handler)
    if len(api_logger.handlers) == 1:
        api_logger.addHandler(console_handler)
    if len(error_logger.handlers) == 1:
        error_logger.addHandler(console_handler)

    return bot_logger, api_logger, error_logger

bot_logger, api_logger, error_logger = setup_loggers()
