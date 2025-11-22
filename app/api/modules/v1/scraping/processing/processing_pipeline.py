import json
import logging
from typing import Any, Dict

import aio_pika
from scraping.services.llm_service import build_llm_prompt, run_llm_analysis
from scraping.services.prompt_service import build_final_prompt
from scraping.services.queue_publisher import RabbitMQPublisher

logger = logging.getLogger(__name__)

EXTRACTOR_QUEUE = "extractor.data"      # team extracting will push here
SUMMARY_QUEUE = "ai.summary"            # your ai summary output


async def process_single_message(message: aio_pika.IncomingMessage):
    """
    Handles ONE message from extractor:
    1. Parse data
    2. Build final prompt
    3. Run LLM
    4. Publish ai.summary
    """

    async with message.process():
        try:
            payload: Dict[str, Any] = json.loads(message.body.decode())
            logger.info(f"Received extractor payload: {payload}")

            # -------------------------
            # STEP 1 — extract fields
            # -------------------------
            project_prompt = payload.get("project_prompt", "")
            jurisdiction_prompt = payload.get("jurisdiction_prompt", "")
            extracted_text = payload.get("extracted_text", "")
            metadata = payload.get("meta", {})

            # -------------------------
            # STEP 2 — build full prompt
            # -------------------------
            final_prompt = build_final_prompt(project_prompt, jurisdiction_prompt)
            llm_input = build_llm_prompt(final_prompt, extracted_text)

            # -------------------------
            # STEP 3 — call LLM
            # -------------------------
            llm_result = await run_llm_analysis(llm_input)

            logger.info(f"LLM Result: {llm_result}")

            # -------------------------
            # STEP 4 — publish AI summary
            # -------------------------
            publisher = RabbitMQPublisher()
            await publisher.publish({
                "meta": metadata,
                "summary": llm_result.get("summary"),
                "changes_detected": llm_result.get("changes_detected"),
                "risk_level": llm_result.get("risk_level"),
                "recommendation": llm_result.get("recommendation"),
            })
            await publisher.close()

        except Exception as exc:
            logger.error(f"Error processing message: {exc}", exc_info=True)


async def start_processing_pipeline():
    """
    Runs on FastAPI startup event.
    Keeps listening forever to extractor queue.
    """

    logger.info("Starting extraction → LLM → summary pipeline...")

    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()

    # Ensure queue exists
    queue = await channel.declare_queue(EXTRACTOR_QUEUE, durable=True)

    # Background listening
    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            await process_single_message(message)

