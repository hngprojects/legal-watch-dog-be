import io
import logging

from minio import Minio
from minio.error import S3Error

from app.api.core.config import settings

logger = logging.getLogger(__name__)


class MinioReadError(Exception):
    """Raised when reading from MinIO fails."""


class MinioWriteError(Exception):
    """Raised when writing to MinIO fails."""


def get_minio_client() -> Minio:
    """
    Initialize and return a MinIO client using configuration settings.
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


# Helper func


def ensure_bucket(bucket: str):
    client = get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def read_object(bucket: str, object_name: str) -> str:
    """
    Read an object from MinIO and return its UTF-8 decoded content.
    """
    client = get_minio_client()

    try:
        response = client.get_object(bucket, object_name)
    except S3Error as e:
        if e.code == "NoSuchKey":
            raise FileNotFoundError(f"Object '{object_name}' not found in bucket '{bucket}'") from e
        raise MinioReadError(f"S3Error while reading object {object_name}: {e}") from e
    except Exception as e:
        raise MinioReadError(f"Unexpected error reading object {object_name}") from e

    try:
        raw = response.read()
    finally:
        response.close()
        response.release_conn()

    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        raise MinioReadError(f"Failed to decode object '{object_name}' as UTF-8")


def write_object(bucket: str, object_name: str, extracted_data: str):
    """
    Write UTF-8 text back to MinIO as a .txt file.
    """
    client = get_minio_client()

    ensure_bucket(bucket)

    try:
        encoded = extracted_data.encode("utf-8")
    except Exception as e:
        logger.error(f"Encoding failed for '{object_name}': {e}")
        raise MinioWriteError("Failed to encode extracted data to UTF-8") from e

    # Must provide a BytesIO stream for MinIO
    data_stream = io.BytesIO(encoded)
    length = len(encoded)

    logger.info(f"Uploading extracted text to '{bucket}/{object_name}'...")

    try:
        client.put_object(
            bucket,  # bucket_name (positional)
            object_name,  # object_name (positional)
            data_stream,  # data stream
            length,  # exact length required
            content_type="text/plain",
        )

    except S3Error as e:
        logger.error(f"MinIO S3 error during upload: {e.code} {e.message}")
        raise MinioWriteError(f"Failed to write object '{object_name}' to bucket '{bucket}'") from e

    except Exception as e:
        logger.error(f"Unexpected error writing object to MinIO: {e}")
        raise MinioWriteError("Unexpected error while writing object to MinIO") from e
