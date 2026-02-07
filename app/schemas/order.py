from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.order import OrderStatus


class OrderCreate(BaseModel):
    items: list[dict[str, Any]]
    total_price: float = Field(ge=0)


class OrderUpdateStatus(BaseModel):
    status: OrderStatus


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    items: list[dict[str, Any]]
    total_price: float
    status: OrderStatus
    created_at: datetime

