import json
from uuid import uuid4

import anyio

from app.core.config import settings
from app.services import events as events_service


class FakeExchange:
    def __init__(self) -> None:
        self.published: list[tuple[object, str]] = []

    async def publish(self, message: object, routing_key: str) -> None:
        self.published.append((message, routing_key))


def test_publish_new_order_builds_message_and_uses_routing_key() -> None:
    exchange = FakeExchange()
    order_id = uuid4()
    user_id = uuid4()

    anyio.run(events_service.publish_new_order, exchange, order_id=order_id, user_id=user_id)

    assert len(exchange.published) == 1
    message, routing_key = exchange.published[0]

    assert routing_key == settings.rabbit_routing_key

    body = getattr(message, "body", b"")
    payload = json.loads(body.decode("utf-8"))
    assert payload == {"event": "new_order", "order_id": str(order_id), "user_id": str(user_id)}
