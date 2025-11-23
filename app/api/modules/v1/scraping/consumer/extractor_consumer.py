import asyncio
import json
import logging
import os

import aio_pika
import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL")
EXTRACTOR_QUEUE = "extractor.result"


class ExtractorConsumer:
    """
    Consumes extraction results from RabbitMQ, prepares payload for the LLM Service,
    and forwards the cleaned content with project & jurisdiction IDs.
    """

    def __init__(self, rabbitmq_url: str = RABBITMQ_URL):
        self.rabbitmq_url = rabbitmq_url

    async def connect(self):
        """
        Connect to RabbitMQ and declare extractor queue.
        """
        logger.info("ExtractorConsumer: Connecting to RabbitMQ...")

        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        await self.channel.declare_queue(EXTRACTOR_QUEUE, durable=True)

        logger.info("ExtractorConsumer: Connected successfully.")

    async def process_message(self, message: aio_pika.IncomingMessage):
        """
        Process incoming extraction results and forward them to the LLM API.
        """
        async with message.process():
            try:
                payload = json.loads(message.body.decode("utf-8"))
                logger.info(f"ExtractorConsumer: Received payload: {payload}")

                cleaned_text = payload.get("preview")

                project_id = payload.get("project_id")
                jurisdiction_id = payload.get("jurisdiction_id")

                if not project_id or not jurisdiction_id:
                    logger.error("ExtractorConsumer: Missing project_id or jurisdiction_id")
                    return

                llm_payload = {
                    "content": cleaned_text,
                    "project_id": project_id,
                    "jurisdiction_id": jurisdiction_id,
                }

                logger.info(f"ExtractorConsumer: Sending LLM Payload → {llm_payload}")

                async with httpx.AsyncClient(timeout=60.0) as client:
                    llm_response = await client.post(LLM_SERVICE_URL, json=llm_payload)

                if llm_response.status_code != 200:
                    logger.error(
                        f"ExtractorConsumer: LLM Service Error {llm_response.status_code} — "
                        f"{llm_response.text}"
                    )
                    return

                llm_data = llm_response.json()
                logger.info(f"ExtractorConsumer: LLM Response: {llm_data}")

            except Exception as exc:
                logger.error(f"ExtractorConsumer: Error processing message — {exc}", exc_info=True)

    async def start(self):
        """
        Start listening to the extractor queue.
        """
        await self.connect()

        queue = await self.channel.declare_queue(EXTRACTOR_QUEUE, durable=True)
        logger.info(f"ExtractorConsumer: Listening to queue '{EXTRACTOR_QUEUE}'...")

        await queue.consume(self.process_message)

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("ExtractorConsumer: Shutting down...")
            await self.connection.close()


if __name__ == "__main__":
    consumer = ExtractorConsumer()

    try:
        asyncio.run(consumer.start())
    except KeyboardInterrupt:
        logger.info("ExtractorConsumer: Service stopped manually.")
