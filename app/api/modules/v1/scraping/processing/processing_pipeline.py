import json
import logging
import os
from typing import Any, Dict

import aio_pika
from scraping.service.llm_service import build_gemini_prompt, run_gemini_analysis
from scraping.service.prompt_service import build_final_prompt
from scraping.service.queue_publisher import RabbitMQPublisher

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
EXTRACTOR_QUEUE = "extractor.data"
SUMMARY_QUEUE = "ai.summary"


async def process_single_message(message: aio_pika.IncomingMessage):
    """
    Handles one message from extractor:
    - Parse fields
    - Build final prompt
    - Run Gemini
    - Publish AI summary with comparison-ready fields
    """
    async with message.process():
        try:
            payload: Dict[str, Any] = json.loads(message.body.decode())
            logger.info(f"Received extractor payload: {payload}")

            project_id = payload.get("project_id")
            jurisdiction_id = payload.get("jurisdiction_id")
            html_object = payload.get("html_object")
            text_object = payload.get("text_object")
            cleaned_text = payload.get("preview")
            meta = payload.get("meta", {})

            final_prompt = await build_final_prompt(
                db=None, project_id=project_id, jurisdiction_id=jurisdiction_id
            )
            logger.info(f"ProcessingPipeline: Final prompt →\n{final_prompt}")


            gemini_input = build_gemini_prompt(final_prompt, cleaned_text)

            gemini_result = await run_gemini_analysis(gemini_input)
            logger.info(f"Gemini Result: {gemini_result}")

            publisher = RabbitMQPublisher(RABBITMQ_URL)
            await publisher.publish(
                {
                    "project_id": project_id,
                    "jurisdiction_id": jurisdiction_id,
                    "html_object": html_object,
                    "text_object": text_object,
                    "preview": cleaned_text,
                    "meta": meta,
                    "summary": gemini_result.get("summary"),
                    "changes_detected": gemini_result.get("changes_detected"),
                    "risk_level": gemini_result.get("risk_level"),
                    "recommendation": gemini_result.get("recommendation"),
                }
            )
            await publisher.close()

        except Exception as exc:
            logger.error(f"Error processing message: {exc}", exc_info=True)


async def start_processing_pipeline():
    """
    Startup listener for the extractor queue.
    """
    logger.info("Starting extraction → Gemini→ summary pipeline...")

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    queue = await channel.declare_queue(EXTRACTOR_QUEUE, durable=True)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            await process_single_message(message)
