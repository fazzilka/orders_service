from datetime import UTC, datetime
from uuid import UUID, uuid4

import anyio
import pytest

from app.core.security import create_access_token, create_refresh_token
from app.db.models.order import OrderStatus
from app.schemas.order import OrderRead
from app.services import cache as cache_service


@pytest.fixture()
def _override_orders_deps(app, fake_redis, monkeypatch, fake_user):  # type: ignore[no-untyped-def]
    import app.api.deps as deps_module
    import app.api.v1.orders as orders_module

    async def override_get_db():  # type: ignore[no-untyped-def]
        yield object()

    def override_get_redis():  # type: ignore[no-untyped-def]
        return fake_redis

    def override_get_exchange():  # type: ignore[no-untyped-def]
        return object()

    async def fake_get_user_by_id(session, user_id: UUID):  # type: ignore[no-untyped-def]
        return fake_user

    monkeypatch.setattr(deps_module, "get_user_by_id", fake_get_user_by_id)

    app.dependency_overrides[orders_module.get_db] = override_get_db
    app.dependency_overrides[orders_module.get_redis] = override_get_redis
    app.dependency_overrides[orders_module.get_rabbit_exchange] = override_get_exchange

    yield
    app.dependency_overrides.clear()


def _auth_header(user_id: UUID, email: str) -> dict[str, str]:
    token = create_access_token(subject=str(user_id), email=email)
    return {"Authorization": f"Bearer {token}"}


def test_create_order_caches_and_publishes_event(
    client, app, fake_user, fake_redis, monkeypatch, recorder, _override_orders_deps
):  # type: ignore[no-untyped-def]
    import app.api.v1.orders as orders_module

    order_id = uuid4()

    class FakeOrder:
        id = order_id
        user_id = fake_user.id
        items = [{"sku": "A1", "qty": 1}]
        total_price = 10.0
        status = OrderStatus.PENDING
        created_at = datetime.now(UTC)

    async def fake_create_order(session, user_id: UUID, order_in):  # type: ignore[no-untyped-def]
        return FakeOrder()

    async def fake_publish_new_order(exchange, order_id: UUID, user_id: UUID):  # type: ignore[no-untyped-def]
        recorder.record(exchange=exchange, order_id=order_id, user_id=user_id)

    monkeypatch.setattr(orders_module.orders_service, "create_order", fake_create_order)
    monkeypatch.setattr(orders_module.events_service, "publish_new_order", fake_publish_new_order)

    response = client.post(
        "/orders/",
        json={"items": [{"sku": "A1", "qty": 1}], "total_price": 10.0},
        headers=_auth_header(fake_user.id, fake_user.email),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == str(order_id)
    assert payload["user_id"] == str(fake_user.id)
    assert payload["status"] == "PENDING"

    cached = anyio.run(cache_service.get_order_from_cache, fake_redis, order_id)
    assert cached is not None
    assert cached.id == order_id

    assert len(recorder.calls) == 1
    _args, kwargs = recorder.calls[0]
    assert kwargs["order_id"] == order_id
    assert kwargs["user_id"] == fake_user.id


def test_get_order_returns_from_cache(
    client, fake_user, fake_redis, monkeypatch, _override_orders_deps
):  # type: ignore[no-untyped-def]
    import app.api.v1.orders as orders_module

    order_id = uuid4()
    order = OrderRead(
        id=order_id,
        user_id=fake_user.id,
        items=[{"sku": "A1", "qty": 2}],
        total_price=99.9,
        status=OrderStatus.PAID,
        created_at=datetime.now(UTC),
    )
    anyio.run(cache_service.set_order_cache, fake_redis, order)

    async def should_not_hit_db(session, order_id: UUID):  # type: ignore[no-untyped-def]
        raise AssertionError("DB should not be used when cache is present")

    monkeypatch.setattr(orders_module.orders_service, "get_order_by_id", should_not_hit_db)

    response = client.get(
        f"/orders/{order_id}/",
        headers=_auth_header(fake_user.id, fake_user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(order_id)
    assert payload["status"] == "PAID"


def test_get_order_forbidden_when_cached_order_belongs_to_other_user(
    client, fake_user, fake_redis, _override_orders_deps
):  # type: ignore[no-untyped-def]
    order_id = uuid4()
    order = OrderRead(
        id=order_id,
        user_id=uuid4(),
        items=[{"sku": "A1", "qty": 1}],
        total_price=10.0,
        status=OrderStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    anyio.run(cache_service.set_order_cache, fake_redis, order)

    response = client.get(
        f"/orders/{order_id}/",
        headers=_auth_header(fake_user.id, fake_user.email),
    )

    assert response.status_code == 403


def test_get_order_404_when_missing_in_db(
    client, fake_user, monkeypatch, _override_orders_deps
):  # type: ignore[no-untyped-def]
    import app.api.v1.orders as orders_module

    async def fake_get_order_by_id(session, order_id: UUID):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(orders_module.orders_service, "get_order_by_id", fake_get_order_by_id)

    order_id = uuid4()
    response = client.get(
        f"/orders/{order_id}/",
        headers=_auth_header(fake_user.id, fake_user.email),
    )

    assert response.status_code == 404


def test_update_order_status_updates_cache(
    client, fake_user, fake_redis, monkeypatch, _override_orders_deps
):  # type: ignore[no-untyped-def]
    import app.api.v1.orders as orders_module

    order_id = uuid4()

    class FakeOrder:
        id = order_id
        user_id = fake_user.id
        items = [{"sku": "A1", "qty": 1}]
        total_price = 10.0
        status = OrderStatus.PENDING
        created_at = datetime.now(UTC)

    async def fake_get_order_by_id(session, order_id: UUID):  # type: ignore[no-untyped-def]
        return FakeOrder()

    async def fake_update_order_status(session, order, status):  # type: ignore[no-untyped-def]
        order.status = status
        return order

    monkeypatch.setattr(orders_module.orders_service, "get_order_by_id", fake_get_order_by_id)
    monkeypatch.setattr(orders_module.orders_service, "update_order_status", fake_update_order_status)

    response = client.patch(
        f"/orders/{order_id}/",
        json={"status": "PAID"},
        headers=_auth_header(fake_user.id, fake_user.email),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PAID"

    cached = anyio.run(cache_service.get_order_from_cache, fake_redis, order_id)
    assert cached is not None
    assert cached.status == OrderStatus.PAID


def test_update_order_status_rejects_refresh_token(
    client, fake_user, monkeypatch, _override_orders_deps
):  # type: ignore[no-untyped-def]
    import app.api.v1.orders as orders_module

    async def fake_get_order_by_id(session, order_id: UUID):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(orders_module.orders_service, "get_order_by_id", fake_get_order_by_id)

    refresh = create_refresh_token(subject=str(fake_user.id), email=fake_user.email)
    response = client.get(
        f"/orders/{uuid4()}/",
        headers={"Authorization": f"Bearer {refresh}"},
    )

    assert response.status_code == 401


def test_list_user_orders_forbidden_when_not_self(
    client, fake_user, _override_orders_deps
):  # type: ignore[no-untyped-def]
    other_user_id = uuid4()
    response = client.get(
        f"/orders/user/{other_user_id}/",
        headers=_auth_header(fake_user.id, fake_user.email),
    )

    assert response.status_code == 403


def test_list_user_orders_success(
    client, fake_user, monkeypatch, _override_orders_deps
):  # type: ignore[no-untyped-def]
    import app.api.v1.orders as orders_module

    class FakeOrder:
        def __init__(self, order_id: UUID, status: OrderStatus) -> None:
            self.id = order_id
            self.user_id = fake_user.id
            self.items = [{"sku": "A1", "qty": 1}]
            self.total_price = 10.0
            self.status = status
            self.created_at = datetime.now(UTC)

    async def fake_list_orders_by_user(session, user_id: UUID):  # type: ignore[no-untyped-def]
        return [FakeOrder(uuid4(), OrderStatus.PENDING), FakeOrder(uuid4(), OrderStatus.SHIPPED)]

    monkeypatch.setattr(orders_module.orders_service, "list_orders_by_user", fake_list_orders_by_user)

    response = client.get(
        f"/orders/user/{fake_user.id}/",
        headers=_auth_header(fake_user.id, fake_user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 2

