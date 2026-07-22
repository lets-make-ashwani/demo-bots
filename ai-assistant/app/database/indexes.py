import pymongo
from app.database.mongodb import db_instance
from app.utils.logger import bot_logger, error_logger

async def create_indexes() -> None:
    """
    Creates required indexes for all collections.
    """
    if db_instance.db is None:
        error_logger.error("Cannot create indexes: MongoDB connection not established.")
        return

    try:
        bot_logger.info("Verifying and creating MongoDB indexes...")
        db = db_instance.db

        # users collection indexes
        await db.users.create_index([("telegram_id", pymongo.ASCENDING)], unique=True)
        await db.users.create_index([("username", pymongo.ASCENDING)])
        await db.users.create_index([("last_seen", pymongo.DESCENDING)])

        # conversations collection indexes
        await db.conversations.create_index([("user_id", pymongo.ASCENDING)])
        await db.conversations.create_index([("updated_at", pymongo.DESCENDING)])

        # messages collection indexes
        await db.messages.create_index([
            ("conversation_id", pymongo.ASCENDING),
            ("created_at", pymongo.ASCENDING)
        ])
        await db.messages.create_index([("user_id", pymongo.ASCENDING)])
        await db.messages.create_index([("role", pymongo.ASCENDING)])
        await db.messages.create_index([("model", pymongo.ASCENDING)])

        # settings collection indexes
        await db.settings.create_index([("user_id", pymongo.ASCENDING)], unique=True)

        # analytics collection indexes
        await db.analytics.create_index([("date", pymongo.ASCENDING)], unique=True)

        bot_logger.info("MongoDB indexes initialized successfully.")
    except Exception as e:
        error_logger.error(f"Error occurred while creating indexes: {e}")
        raise e
