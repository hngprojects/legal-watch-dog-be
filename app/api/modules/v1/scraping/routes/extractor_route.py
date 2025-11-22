import json

import aio_pika
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette import status

from app.api.modules.v1.scraping.service.extractor_service import TextExtractorService
from app.api.core.config import settings  # Make sure your settings has RabbitMQ credentials


# ----------------- RESPONSE MODEL -----------------
class ExtractResponse(BaseModel):
    status: str
    html_object: str
    text_object: str
    preview: str


# ----------------- ROUTER -----------------
router = APIRouter(prefix="/scraping/extract", tags=["Scraping - Extraction"])

extractor = TextExtractorService()


# ----------------- HELPER FUNCTION -----------------
async def publish_to_rabbitmq(queue_name: str, message: dict):
    """
    Publish a message to RabbitMQ asynchronously.
    """
    connection = await aio_pika.connect_robust(
        host=settings.RABBIT_HOST,
        port=settings.RABBIT_PORT,
        login=settings.RABBIT_USER,
        password=settings.RABBIT_PASS,
    )
    async with connection:
        channel = await connection.channel()
        await channel.declare_queue(queue_name, durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()), routing_key=queue_name
        )


# ----------------- ENDPOINT -----------------
@router.post("/{object_name}", response_model=ExtractResponse)
async def extract_text(object_name: str):
    """
    Extract text from stored HTML inside MinIO, save it as a .txt file,
    and publish the result to RabbitMQ.
    """

    # --- Input validation ---
    if not object_name.lower().endswith(".html"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="object_name must end with .html"
        )

    output_name = object_name[:-5] + ".txt"  # safer than replace

    try:
        # --- Extract text ---
        text = await extractor.extract_and_save(
            src_bucket="scraped-pages",
            html_object=object_name,
            dest_bucket="extracted-text",
            output_name=output_name,
        )

        # --- Prepare payload for RabbitMQ ---
        payload = {
            "status": "success",
            "html_object": object_name,
            "text_object": output_name,
            "preview": text if text else "",
        }

        # --- Publish to RabbitMQ ---
        await publish_to_rabbitmq("extracted_data_queue", payload)

    # --- Domain-level errors ---
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HTML file '{object_name}' not found in 'scraped-pages' bucket.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # --- Unexpected errors ---
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during extraction: {e}",
        )

    # --- Response ---
    return ExtractResponse(**payload)
