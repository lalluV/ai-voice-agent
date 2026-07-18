from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisState:
    client: Redis | None = None
    enabled: bool = False


redis_state = RedisState()


async def connect_redis(settings: Settings) -> Redis | None:
    redis_state.enabled = settings.redis_enabled
    if not settings.redis_enabled:
        logger.info("redis_disabled")
        return None
    redis_state.client = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    await redis_state.client.ping()
    logger.info("redis_connected")
    return redis_state.client


async def close_redis() -> None:
    if redis_state.client is not None:
        await redis_state.client.aclose()
        redis_state.client = None
        logger.info("redis_closed")


def get_redis() -> Redis | None:
    return redis_state.client
