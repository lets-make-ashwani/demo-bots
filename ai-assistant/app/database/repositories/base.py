from typing import Dict, Any, List, Optional
from app.database.mongodb import db_instance

class BaseRepository:
    """
    Abstract Base Repository for wrapping common Motor driver operations.
    """
    def __init__(self, collection_name: str):
        self._collection_name = collection_name

    @property
    def collection(self):
        if db_instance.db is None:
            raise RuntimeError("MongoDB connection not initialized.")
        return db_instance.db[self._collection_name]

    async def find_one(self, filter_query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one(filter_query)

    async def find_many(
        self, 
        filter_query: Dict[str, Any], 
        sort: Optional[List[tuple]] = None, 
        limit: int = 0
    ) -> List[Dict[str, Any]]:
        cursor = self.collection.find(filter_query)
        if sort:
            cursor = cursor.sort(sort)
        if limit > 0:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=None)

    async def insert_one(self, document: Dict[str, Any]) -> Any:
        result = await self.collection.insert_one(document)
        return result.inserted_id

    async def update_one(
        self, 
        filter_query: Dict[str, Any], 
        update_data: Dict[str, Any], 
        upsert: bool = False
    ) -> int:
        result = await self.collection.update_one(filter_query, update_data, upsert=upsert)
        return result.modified_count

    async def delete_many(self, filter_query: Dict[str, Any]) -> int:
        result = await self.collection.delete_many(filter_query)
        return result.deleted_count
