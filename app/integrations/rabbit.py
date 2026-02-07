import asyncio
import logging
from dataclasses import dataclass

import aio_pika
from aio_pika import ExchangeType


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RabbitResources:
    connection: aio_pika.RobustConnection
    channel: aio_pika.RobustChannel
    exchange: aio_pika.Exchange


async def connect_rabbit(url: str, exchange_name: str) -> RabbitResources:
    connection = await _connect_with_retry(url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(exchange_name, ExchangeType.TOPIC, durable=True)
    logger.info("Connected to RabbitMQ (exchange=%s)", exchange_name)

    return RabbitResources(connection=connection, channel=channel, exchange=exchange)


async def close_rabbit(resources: RabbitResources) -> None:
    await resources.connection.close()


async def _connect_with_retry(
    url: str, retries: int = 30, delay_seconds: float = 1.0
) -> aio_pika.RobustConnection:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return await aio_pika.connect_robust(url)
        except Exception as exc:
            last_exc = exc
            logger.warning("RabbitMQ not ready (attempt %s/%s): %s", attempt, retries, exc)
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("RabbitMQ is not ready") from last_exc

