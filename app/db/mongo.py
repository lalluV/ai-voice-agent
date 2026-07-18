from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Mongo:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongo = Mongo()


async def connect_mongo(settings: Settings) -> AsyncIOMotorDatabase:
    mongo.client = AsyncIOMotorClient(
        settings.mongodb_uri,
        maxPoolSize=50,
        minPoolSize=5,
        serverSelectionTimeoutMS=5000,
    )
    mongo.db = mongo.client[settings.mongodb_database]
    await mongo.client.admin.command("ping")
    await _ensure_indexes(mongo.db)
    logger.info("mongo_connected", database=settings.mongodb_database)
    return mongo.db


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.tenants.create_index("tenant_id", unique=True)
    await db.tenants.create_index("plivo_numbers")
    await db.call_logs.create_index("session_id", unique=True)
    await db.call_logs.create_index([("tenant_id", 1), ("started_at", -1)])
    await db.call_logs.create_index("call_id")


async def close_mongo() -> None:
    if mongo.client is not None:
        mongo.client.close()
        mongo.client = None
        mongo.db = None
        logger.info("mongo_closed")


def get_db() -> AsyncIOMotorDatabase:
    if mongo.db is None:
        raise RuntimeError("MongoDB is not connected")
    return mongo.db
