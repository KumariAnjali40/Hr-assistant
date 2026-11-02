import time

from fastapi import Depends, HTTPException

from app.auth import User, current_user
from app.config import settings
from app.services.redis import get_redis


async def rate_limit(user: User = Depends(current_user)) -> User:
    """Fixed-window per-user limiter in Redis (shared by every API replica)."""
    r = get_redis()
    key = f"rl:{user.id}:{int(time.time() // 60)}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 61)
    if count > settings.rate_limit_per_min:
        raise HTTPException(429, "Too many requests, slow down.", headers={"Retry-After": "30"})
    return user
