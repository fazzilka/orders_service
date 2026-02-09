from datetime import UTC, datetime
from uuid import uuid4

import anyio

from app.db.models.order import OrderStatus
from app.schemas.order import OrderRead
from app.services import cache as cache_service

from .conftest import FakeRedis


def test_order_cache_roundtrip(fake_redis: FakeRedis) -> None:
    order = OrderRead(
        id=uuid4(),
        user_id=uuid4(),
        items=[{"sku": "A1", "qty": 2}],
        total_price=123.45,
        status=OrderStatus.PENDING,
        created_at=datetime.now(UTC),
    )

    anyio.run(cache_service.set_order_cache, fake_redis, order)
    cached = anyio.run(cache_service.get_order_from_cache, fake_redis, order.id)

    assert cached is not None
    assert cached.model_dump() == order.model_dump()


def test_order_cache_invalidate(fake_redis: FakeRedis) -> None:
    order = OrderRead(
        id=uuid4(),
        user_id=uuid4(),
        items=[{"sku": "A1", "qty": 1}],
        total_price=10.0,
        status=OrderStatus.PAID,
        created_at=datetime.now(UTC),
    )

    anyio.run(cache_service.set_order_cache, fake_redis, order)
    anyio.run(cache_service.invalidate_order_cache, fake_redis, order.id)

    cached = anyio.run(cache_service.get_order_from_cache, fake_redis, order.id)
    assert cached is None


def test_order_cache_invalid_payload_is_invalidated(fake_redis: FakeRedis) -> None:
    order_id = uuid4()
    key = cache_service.order_cache_key(order_id)

    anyio.run(fake_redis.set, key, "{not-json")
    cached = anyio.run(cache_service.get_order_from_cache, fake_redis, order_id)

    assert cached is None
    assert anyio.run(fake_redis.get, key) is None

