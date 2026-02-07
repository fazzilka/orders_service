import json
import logging
from uuid import UUID

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractExchange

from app.core.config import settings


logger = logging.getLogger(__name__)


async def publish_new_order(exchange: AbstractExchange, order_id: UUID, user_id: UUID) -> None:
    payload = {"event": "new_order", "order_id": str(order_id), "user_id": str(user_id)}
    message = Message(
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
    )
    await exchange.publish(message, routing_key=settings.rabbit_routing_key)
    logger.info("Published new_order event: order_id=%s user_id=%s", order_id, user_id)

