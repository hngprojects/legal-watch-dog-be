import io
import logging

from minio import Minio
from minio.error import S3Error

from app.api.core.config import settings

logger = logging.getLogger(__name__)


class MinioReadError(Exception):
    """Raised when reading from MinIO fails."""

    pass


class MinioWriteError(Exception):
    """Raised when writing to MinIO fails."""

    pass


def get_minio_client() -> Minio:
    """
    Initialize and return a MinIO client using environment/config settings.
    """
    try:
        return Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    except Exception as e:
        logger.error(f"Failed to initialize MinIO client: {e}")
        raise


def read_object(bucket: str, object_name: str) -> str:
    """
    Read raw object content from MinIO and return it as UTF-8 text.
    Adds full error handling and logs issues clearly.
    """

    client = get_minio_client()

    try:
        logger.info(f"Reading object '{object_name}' from bucket '{bucket}'...")
        response = client.get_object(bucket, object_name)
    except S3Error as e:
        logger.error(f"MinIO S3 error while fetching object: {e.code} {e.message}")
        raise MinioReadError(f"Failed to get object '{object_name}' from bucket '{bucket}'") from e
    except Exception as e:
        logger.error(f"Unexpected error while getting object: {e}")
        raise MinioReadError("Unexpected error while reading object from MinIO") from e

    try:
        raw_content = response.read()
    except Exception as e:
        logger.error(f"Error reading response stream for '{object_name}': {e}")
        raise MinioReadError("Error reading object content from MinIO") from e
    finally:
        response.close()
        response.release_conn()

    try:
        return raw_content.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Decoding error for '{object_name}': {e}")
        raise MinioReadError("Failed to decode object content as UTF-8") from e


def write_object(bucket: str, object_name: str, extracted_data: str):
    """
    Write extracted text back to MinIO with safety checks and error handling.
    """

    client = get_minio_client()

    try:
        encoded_data = extracted_data.encode("utf-8")
    except Exception as e:
        logger.error(f"Encoding failed for '{object_name}': {e}")
        raise MinioWriteError("Failed to encode extracted data to UTF-8") from e

    try:
        logger.info(f"Uploading extracted text to '{bucket}/{object_name}'...")
        client.put_object(
            bucket=bucket,
            object_name=object_name,
            data=io.BytesIO(encoded_data),
            length=len(encoded_data),
        )
    except S3Error as e:
        logger.error(f"MinIO S3 error during upload: {e.code} {e.message}")
        raise MinioWriteError(f"Failed to write object '{object_name}' to bucket '{bucket}'") from e
    except Exception as e:
        logger.error(f"Unexpected error writing object to MinIO: {e}")
        raise MinioWriteError("Unexpected error while writing object to MinIO") from e
