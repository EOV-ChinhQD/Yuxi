import asyncio
from yuxi.storage.redis import get_async_redis_client
import time


class GpuThrottle:
    """
    Distributed semaphore using Redis to limit concurrent GPU tasks (like embedding) globally.
    """

    def __init__(self, key: str = "gpu_semaphore", max_concurrent: int = 5, timeout_sec: int = 60):
        self.key = key
        self.max_concurrent = max_concurrent
        self.timeout_sec = timeout_sec
        self.identifier = f"{time.time()}_{id(self)}"

    async def __aenter__(self):
        try:
            redis = await get_async_redis_client()
            self._redis = redis
            # Clean up expired identifiers
            await redis.zremrangebyscore(self.key, "-inf", time.time() - self.timeout_sec)

            # Simple loop for acquiring lock
            while True:
                count = await redis.zcard(self.key)
                if count < self.max_concurrent:
                    # Try to add our identifier
                    await redis.zadd(self.key, {self.identifier: time.time()})
                    # Recheck if we got it (race condition handling)
                    rank = await redis.zrank(self.key, self.identifier)
                    if rank is not None and rank < self.max_concurrent:
                        return self
                    else:
                        await redis.zrem(self.key, self.identifier)
                await asyncio.sleep(0.5)
        except Exception:
            self._redis = None
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if getattr(self, "_redis", None):
            try:
                await self._redis.zrem(self.key, self.identifier)
            except Exception:
                pass
