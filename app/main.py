from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.orders import router as orders_router
from app.core.config import settings
from app.core.cors import setup_cors
from app.core.logging import configure_logging
from app.core.rate_limit import setup_rate_limiting
from app.integrations.rabbit import RabbitResources, close_rabbit, connect_rabbit
from app.integrations.redis import close_redis, create_redis


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = await create_redis(settings.redis_url)
    app.state.redis = redis

    rabbit: RabbitResources = await connect_rabbit(
        url=settings.rabbitmq_url,
        exchange_name=settings.rabbit_exchange,
    )
    app.state.rabbit = rabbit
    app.state.rabbit_exchange = rabbit.exchange

    yield

    await close_redis(redis)
    await close_rabbit(rabbit)


app = FastAPI(title=settings.api_title, version=settings.api_version, lifespan=lifespan)

setup_cors(app)
setup_rate_limiting(app)

app.include_router(auth_router, tags=["auth"])
app.include_router(orders_router, tags=["orders"])


@app.get("/health/", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

