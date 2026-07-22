from app.database.mongodb import db_instance
from app.database.indexes import create_indexes

__all__ = ["db_instance", "create_indexes"]
