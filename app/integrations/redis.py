import asyncio
import logging
import inspect

from redis.asyncio import Redis


logger = logging.getLogger(__name__)


async def create_redis(url: str) -> Redis:
    client = Redis.from_url(url, decode_responses=True)
    await _ping_with_retry(client)
    return client


async def close_redis(client: Redis) -> None:
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close is not None:
        result = close()
        if inspect.isawaitable(result):
            await result


async def _ping_with_retry(client: Redis, retries: int = 30, delay_seconds: float = 1.0) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            await client.ping()
            logger.info("Connected to Redis")
            return
        except Exception as exc:
            last_exc = exc
            logger.warning("Redis not ready (attempt %s/%s): %s", attempt, retries, exc)
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Redis is not ready") from last_exc
