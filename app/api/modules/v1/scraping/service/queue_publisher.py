# scraping/services/queue_publisher.py

import asyncio
import json
import logging
import random
from typing import Any, Dict

import aio_pika

logger = logging.getLogger(__name__)

RABBITMQ_URL = "amqp://guest:guest@localhost/"   
QUEUE_NAME = "ai.summary"


class RabbitMQPublisher:
    """
    Handles publishing AI summary messages to RabbitMQ with reconnection,
    retries and exponential backoff.
    """

    def __init__(self, url: str = RABBITMQ_URL):
        self.url = url
        self.connection = None
        self.channel = None

    async def connect(self):
        """
        Connect to RabbitMQ and create a channel.
        """
        logger.info("Connecting to RabbitMQ...")

        try:
            self.connection = await aio_pika.connect_robust(self.url)
            self.channel = await self.connection.channel()

            
            await self.channel.declare_queue(QUEUE_NAME, durable=True)

            logger.info("Connected to RabbitMQ successfully.")

        except Exception as exc:
            logger.error(f"Failed to connect to RabbitMQ: {exc}", exc_info=True)
            raise

    async def publish(self, message: Dict[str, Any]):
        """
        Publish message to RabbitMQ with retry + exponential backoff.
        """
        payload = json.dumps(message).encode("utf-8")
        backoff = 1 

        for attempt in range(5):  
            try:
                if not self.channel:
                    await self.connect()

                await self.channel.default_exchange.publish(
                    aio_pika.Message(
                        body=payload,
                        content_type="application/json",
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    ),
                    routing_key=QUEUE_NAME,
                )

                logger.info(
                    f"Published AI summary to queue '{QUEUE_NAME}'. Attempt {attempt + 1}"
                )
                return True

            except Exception as exc:
                logger.error(
                    f"Publish failed (attempt {attempt + 1}). Error: {exc}"
                )

               
                sleep_time = backoff + random.uniform(0, 1)
                logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)

                backoff *= 2  

        logger.error("Max retries exceeded. Message not published.")
        return False

    async def close(self):
        """
        Close connection gracefully.
        """
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ connection closed.")
