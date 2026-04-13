import logging
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.schemas.order import OrderRead

logger = logging.getLogger(__name__)


def order_cache_key(order_id: UUID) -> str:
    return f"order:{order_id}"


async def get_order_from_cache(redis: Redis, order_id: UUID) -> OrderRead | None:
    key = order_cache_key(order_id)
    try:
        payload = await redis.get(key)
    except RedisError:
        logger.exception("Redis GET failed for key=%s", key)
        return None

    if not payload:
        return None

    try:
        return OrderRead.model_validate_json(payload)
    except ValueError:
        logger.warning("Invalid cached order payload for key=%s; invalidating", key)
        await invalidate_order_cache(redis, order_id)
        return None


async def set_order_cache(redis: Redis, order: OrderRead) -> None:
    key = order_cache_key(order.id)
    try:
        await redis.set(key, order.model_dump_json(), ex=settings.cache_ttl_seconds)
    except RedisError:
        logger.exception("Redis SET failed for key=%s", key)


async def invalidate_order_cache(redis: Redis, order_id: UUID) -> None:
    key = order_cache_key(order_id)
    try:
        await redis.delete(key)
    except RedisError:
        logger.exception("Redis DEL failed for key=%s", key)
