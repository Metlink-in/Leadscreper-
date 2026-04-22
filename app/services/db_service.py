import logging
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

logger = logging.getLogger(__name__)

class DatabaseService:
    client: AsyncIOMotorClient = None
    db = None
    
    @classmethod
    async def connect(cls):
        if settings.mongodb_uri:
            try:
                cls.client = AsyncIOMotorClient(settings.mongodb_uri)
                # Ensure connection is established
                await cls.client.admin.command('ping')
                cls.db = cls.client.get_database("leadscraper")
                logger.info("[DB] Successfully connected to MongoDB!")
            except Exception as e:
                logger.error("[DB] Could not connect to MongoDB: %s", e)
        else:
            logger.warning("[DB] No MONGODB_URI provided in settings.")

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()
            logger.info("[DB] MongoDB connection closed.")

    @classmethod
    async def save_search(cls, search_id: str, search_data: Dict[str, Any]):
        if cls.db is not None:
            try:
                search_data["_id"] = search_id
                await cls.db.searches.insert_one(search_data)
                logger.info("[DB] Saved search %s to database.", search_id)
            except Exception as e:
                logger.error("[DB] Error saving search: %s", e)
        else:
            logger.warning("[DB] Database not connected. Search not saved.")
            
    @classmethod
    async def get_search(cls, search_id: str) -> Optional[Dict[str, Any]]:
        if cls.db is not None:
            try:
                search = await cls.db.searches.find_one({"_id": search_id})
                if search:
                    # Remove _id before returning to avoid JSON serialization issues if used directly
                    search.pop("_id", None)
                return search
            except Exception as e:
                logger.error("[DB] Error retrieving search: %s", e)
        return None

    @classmethod
    async def get_search_history(cls, limit: int = 50) -> List[Dict[str, Any]]:
        if cls.db is not None:
            try:
                cursor = cls.db.searches.find({}, {"leads": 0}).sort("created_at", -1).limit(limit)
                history = await cursor.to_list(length=limit)
                for h in history:
                    h["search_id"] = h.pop("_id")
                return history
            except Exception as e:
                logger.error("[DB] Error retrieving history: %s", e)
        return []

    @classmethod
    async def delete_search(cls, search_id: str) -> bool:
        if cls.db is not None:
            try:
                result = await cls.db.searches.delete_one({"_id": search_id})
                return result.deleted_count > 0
            except Exception as e:
                logger.error("[DB] Error deleting search: %s", e)
        return False

    @classmethod
    async def clear_all_searches(cls) -> int:
        if cls.db is not None:
            try:
                result = await cls.db.searches.delete_many({})
                return result.deleted_count
            except Exception as e:
                logger.error("[DB] Error clearing history: %s", e)
        return 0

db_service = DatabaseService()
