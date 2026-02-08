import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test environment bootstrap
#
# `app.core.config.settings` is instantiated at import time, and it requires
# several env vars. We set safe defaults here so any import of `app.*` works
# in tests without having a real Postgres/Redis/RabbitMQ running.
# ---------------------------------------------------------------------------

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/2")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

# Keep rate limiting in-memory for tests (no Redis required).
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")
os.environ.setdefault("RATE_LIMIT_TOKEN", "1000/minute")
os.environ.setdefault("RATE_LIMIT_ORDERS", "1000/minute")


# ---------------------------------------------------------------------------
# Small test doubles
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FakeUser:
    id: UUID
    email: str
    created_at: datetime


@dataclass(slots=True)
class FakeOrder:
    id: UUID
    user_id: UUID
    items: list[dict[str, Any]]
    total_price: float
    status: Any
    created_at: datetime


class FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:  # noqa: ARG002
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


class CallRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def record(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append((args, kwargs))


# ---------------------------------------------------------------------------
# FastAPI app/client fixtures (no lifespan/external connections)
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> FastAPI:
    from app.api.v1.auth import router as auth_router
    from app.api.v1.orders import router as orders_router
    from app.core.rate_limit import setup_rate_limiting

    fastapi_app = FastAPI()
    setup_rate_limiting(fastapi_app)

    fastapi_app.include_router(auth_router, tags=["auth"])
    fastapi_app.include_router(orders_router, tags=["orders"])

    return fastapi_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def fake_user() -> FakeUser:
    return FakeUser(id=uuid4(), email="user@example.com", created_at=datetime.now(UTC))


@pytest.fixture()
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture()
def recorder() -> CallRecorder:
    return CallRecorder()

