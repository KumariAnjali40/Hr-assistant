import redis.asyncio as aioredis

from app.config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def corpus_version() -> str:
    """Bumped whenever documents change; part of every retrieval-cache key."""
    return await get_redis().get("corpus_version") or "0"


async def bump_corpus_version() -> None:
    await get_redis().incr("corpus_version")
