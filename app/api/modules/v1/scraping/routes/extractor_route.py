import json
import logging

import aio_pika
from fastapi import APIRouter

from app.api.core.config import settings
from app.api.modules.v1.scraping.service.extractor_service import TextExtractorService
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)

# Create router for this module
router = APIRouter(prefix="/scraping/extract", tags=["Scraping - Extraction"])

# Instantiate the extraction pipeline service
extractor = TextExtractorService()


async def publish_to_rabbitmq(queue_name: str, message: dict):
    """
    Asynchronously publish a JSON message to a RabbitMQ queue.
    Uses aio-pika for non-blocking I/O.
    """
    try:
        # Establish robust (reconnecting) RabbitMQ connection
        connection = await aio_pika.connect_robust(
            host=settings.RABBIT_HOST,
            port=settings.RABBIT_PORT,
            login=settings.RABBIT_USER,
            password=settings.RABBIT_PASS,
        )

        async with connection:
            # Open a channel
            channel = await connection.channel()

            # Declare the queue to ensure it exists
            await channel.declare_queue(queue_name, durable=True)

            # Publish message to default exchange
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(message).encode()), routing_key=queue_name
            )

    except Exception as e:
        # Log failure but do not break main workflow
        logger.error(f"Failed to publish to RabbitMQ: {e}")


@router.post("/{object_name}")
async def extract_text(object_name: str):
    if not object_name.lower().endswith(".html"):
        return error_response(status_code=400, message="object_name must end with .html")

    output_name = object_name[:-5] + ".txt"

    try:
        # Extract and save
        result = await extractor.extract_and_save(
            src_bucket="scraped-pages",
            html_object=object_name,
            dest_bucket="extracted-text",
            output_name=output_name,
        )

        # If extraction failed
        if result.get("success") is False:
            return error_response(
                status_code=result.get("status_code", 500),
                message=result.get("message", "Extraction failed"),
            )

        # Prepare payload for RabbitMQ
        payload = {
            "status": "success",
            "html_object": object_name,
            "text_object": output_name,
            "preview": result["data"].get("text_preview", ""),
        }

        await publish_to_rabbitmq("extracted_data_queue", payload)

        return success_response(status_code=200, message="Extraction completed", data=payload)

    except FileNotFoundError:
        return error_response(
            status_code=404,
            message=f"HTML file '{object_name}' not found in 'scraped-pages' bucket.",
        )
    except Exception as e:
        return error_response(status_code=500, message=f"Unexpected error during extraction: {e}")
