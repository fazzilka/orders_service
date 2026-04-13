import asyncio
import contextlib
import json
import logging
import signal
from typing import Any

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue

from app.core.config import settings
from worker.celery_app import celery_app

logger = logging.getLogger("consumer")


async def handle_message(message: AbstractIncomingMessage) -> None:
    async with message.process():
        payload: dict[str, Any] = json.loads(message.body)

        if payload.get("event") != "new_order":
            logger.info("Skipping unknown event: %s", payload)
            return

        order_id = payload.get("order_id")
        user_id = payload.get("user_id")
        if not order_id or not user_id:
            logger.warning("Invalid new_order payload: %s", payload)
            return

        logger.info("new_order received: order_id=%s user_id=%s", order_id, user_id)

        await asyncio.to_thread(
            celery_app.send_task,
            "worker.tasks.process_order",
            args=[order_id],
        )
        logger.info("Celery task queued: process_order(order_id=%s)", order_id)


async def consume(queue: AbstractQueue, stop_event: asyncio.Event) -> None:
    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            if stop_event.is_set():
                break
            await handle_message(message)


async def main() -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        settings.rabbit_exchange, ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.rabbit_queue, durable=True)
    await queue.bind(exchange, routing_key=settings.rabbit_routing_key)

    logger.info(
        "Consumer started (exchange=%s queue=%s routing_key=%s)",
        settings.rabbit_exchange,
        settings.rabbit_queue,
        settings.rabbit_routing_key,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    consumer_task = asyncio.create_task(consume(queue, stop_event))
    await stop_event.wait()

    consumer_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await consumer_task

    await connection.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
