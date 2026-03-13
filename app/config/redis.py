import redis.asyncio as aioredis
from app.config.settings import get_settings

settings = get_settings()
_redis_client: aioredis.Redis | None = None


async def init_redis():
    global _redis_client
    _redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Verify connection
    await _redis_client.ping()


async def get_redis() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() at startup.")
    return _redis_client


async def close_redis():
    if _redis_client:
        await _redis_client.aclose()
