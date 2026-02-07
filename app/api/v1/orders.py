import logging
from uuid import UUID

from aio_pika.abc import AbstractExchange
from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_rabbit_exchange, get_redis
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.schemas.order import OrderCreate, OrderRead, OrderUpdateStatus
from app.services import cache as cache_service
from app.services import events as events_service
from app.services import orders as orders_service


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/orders/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_orders)
async def create_order(
    request: Request,
    order_in: OrderCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    exchange: AbstractExchange = Depends(get_rabbit_exchange),
) -> OrderRead:
    order = await orders_service.create_order(session, user_id=current_user.id, order_in=order_in)
    order_read = OrderRead.model_validate(order)

    await cache_service.set_order_cache(redis, order_read)

    try:
        await events_service.publish_new_order(exchange, order_id=order.id, user_id=current_user.id)
    except Exception:
        logger.exception("Failed to publish new_order event for order_id=%s", order.id)

    return order_read


@router.get("/orders/{order_id}/", response_model=OrderRead)
@limiter.limit(settings.rate_limit_orders)
async def get_order(
    request: Request,
    order_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> OrderRead:
    cached = await cache_service.get_order_from_cache(redis, order_id)
    if cached is not None:
        if cached.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return cached

    order = await orders_service.get_order_by_id(session, order_id=order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    order_read = OrderRead.model_validate(order)
    await cache_service.set_order_cache(redis, order_read)
    return order_read


@router.patch("/orders/{order_id}/", response_model=OrderRead)
@limiter.limit(settings.rate_limit_orders)
async def update_order_status(
    request: Request,
    order_id: UUID,
    update_in: OrderUpdateStatus,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> OrderRead:
    order = await orders_service.get_order_by_id(session, order_id=order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    order = await orders_service.update_order_status(session, order=order, status=update_in.status)
    order_read = OrderRead.model_validate(order)

    # Update cache (TTL=300)
    await cache_service.set_order_cache(redis, order_read)

    return order_read


@router.get("/orders/user/{user_id}/", response_model=list[OrderRead])
@limiter.limit(settings.rate_limit_orders)
async def list_user_orders(
    request: Request,
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrderRead]:
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    orders = await orders_service.list_orders_by_user(session, user_id=user_id)
    return [OrderRead.model_validate(order) for order in orders]

