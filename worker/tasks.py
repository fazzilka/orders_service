import logging
import time

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.process_order")
def process_order(order_id: str) -> None:
    time.sleep(2)
    logger.info("Order %s processed", order_id)
