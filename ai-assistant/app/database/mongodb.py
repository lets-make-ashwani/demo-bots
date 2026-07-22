from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.utils.logger import bot_logger, error_logger

class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.db = None

    def connect(self) -> None:
        """
        Initializes the async MongoDB client.
        """
        try:
            bot_logger.info(f"Connecting to MongoDB at {settings.mongodb_uri}...")
            self.client = AsyncIOMotorClient(settings.mongodb_uri)
            self.db = self.client[settings.database_name]
            bot_logger.info(f"Connected to database: {settings.database_name}")
        except Exception as e:
            error_logger.critical(f"Failed to connect to MongoDB: {e}")
            raise e

    def close(self) -> None:
        """
        Closes the MongoDB connection client.
        """
        if self.client:
            bot_logger.info("Closing MongoDB connection client.")
            self.client.close()
            self.client = None
            self.db = None

# Singleton DB instance
db_instance = MongoDB()
