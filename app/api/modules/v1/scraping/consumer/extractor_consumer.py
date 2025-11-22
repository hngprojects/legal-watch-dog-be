import asyncio
import json
import logging

import aio_pika
from aio_pika import IncomingMessage
from app.db.database import async_session
from scraping.services.llm_service import run_llm_analysis
from scraping.services.prompt_service import build_final_prompt
from scraping.services.queue_publisher import publish_ai_summary

logger = logging.getLogger(__name__)


RABBITMQ_URL = "amqp://guest:guest@localhost/"
EXTRACTOR_QUEUE = "extractor.raw_data"  


async def process_extracted_message(message: IncomingMessage):
    """
    Main handler that processes extracted data from the extractor.
    """
    async with message.process():
        try:
            payload = json.loads(message.body.decode())

            project_id = payload.get("project_id")
            jurisdiction_id = payload.get("jurisdiction_id")
            extracted_text = payload.get("extracted_text")  

            logger.info(
    f"Received extracted text for project={project_id}, "
    f"jurisdiction={jurisdiction_id}"
)

            
            async with async_session() as db:
                final_prompt = await build_final_prompt(
                    db=db,
                    project_id=project_id,
                    jurisdiction_id=jurisdiction_id,
                )

           
            llm_input = (
                final_prompt
                + "\n\n--- EXTRACTED TEXT BELOW ---\n\n"
                + extracted_text
            )

            
            llm_summary = await run_llm_analysis(llm_input)

           
            await publish_ai_summary(llm_summary)

            logger.info("Successfully processed and published AI summary.")

        except Exception as exc:
            logger.error(f"Error processing message: {exc}", exc_info=True)
          


async def start_consumer():
    """
    Starts the RabbitMQ consumer that listens to extracted data.
    """
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    queue = await channel.declare_queue(EXTRACTOR_QUEUE, durable=True)

    logger.info(f"Listening on queue '{EXTRACTOR_QUEUE}'...")

    await queue.consume(process_extracted_message)

    return connection


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_consumer())
    loop.run_forever()


