from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate


async def create_order(session: AsyncSession, user_id: UUID, order_in: OrderCreate) -> Order:
    order = Order(
        user_id=user_id,
        items=order_in.items,
        total_price=order_in.total_price,
        status=OrderStatus.PENDING,
    )
    session.add(order)
    await session.commit()
    return order


async def get_order_by_id(session: AsyncSession, order_id: UUID) -> Order | None:
    return await session.get(Order, order_id)


async def update_order_status(session: AsyncSession, order: Order, status: OrderStatus) -> Order:
    order.status = status
    session.add(order)
    await session.commit()
    return order


async def list_orders_by_user(session: AsyncSession, user_id: UUID) -> list[Order]:
    result = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())
