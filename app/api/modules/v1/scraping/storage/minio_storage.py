import io
import logging
from typing import Optional

try:
    from minio import Minio
    from minio.error import S3Error

    _HAS_MINIO = True
except Exception as _e:  # ImportError in case package missing
    Minio = None
    S3Error = Exception
    _HAS_MINIO = False

from app.api.core.config import settings

logger = logging.getLogger(__name__)

# Initialize MinIO Client (if the SDK is available)
minio_client = None
if _HAS_MINIO:
    # We wrap this in a try-except to ensure the app doesn't crash on startup if
    # MinIO is down, but requests needing it will fail gracefully later.
    try:
        minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,  # e.g., "localhost:9000" or "minio:9000"
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,  # True for HTTPS, False for HTTP
        )
    except Exception as e:
        logger.critical(f"Failed to initialize MinIO client: {e}")
        minio_client = None
else:
    logger.warning(
        "MinIO SDK not installed. Install `minio` package to enable storage operations:"
        "`pip install minio`"
    )


def upload_raw_content(file_data: bytes, bucket_name: str, object_name: str) -> str:
    """
    Uploads raw byte data (HTML/PDF) to the specified MinIO bucket.

    Args:
        file_data (bytes): The raw content to upload.
        bucket_name (str): The target bucket (e.g., 'raw-content').
        object_name (str): The unique key (e.g., 'project_id/source_id/timestamp.html').

    Returns:
        str: The object_name (key) if successful.

    Raises:
        Exception: If upload fails, triggering the Retry/DLQ logic in the caller.
    """
    if not _HAS_MINIO:
        raise Exception(
            "Missing optional dependency: `minio` package is not installed. Run `pip install minio`"
            "to enable storage operations."
        )
    if not minio_client:
        raise Exception("MinIO client is not initialized. Check configuration.")

    try:
        # 1. Ensure Bucket Exists (Idempotent check)
        try:
            if not minio_client.bucket_exists(bucket_name=bucket_name):
                logger.info(f"Bucket '{bucket_name}' does not exist. Creating it...")
                minio_client.make_bucket(bucket_name=bucket_name)
        except Exception as e:
            logger.warning(f"Bucket existence check failed (may already exist): {e}")
            # Attempt creation anyway; if bucket exists, MinIO will handle gracefully
            try:
                minio_client.make_bucket(bucket_name=bucket_name)
            except Exception as create_err:
                if "BucketAlreadyExists" not in str(
                    create_err
                ) and "BucketAlreadyOwnedByYou" not in str(create_err):
                    raise create_err

        # 2. Prepare Stream
        # MinIO's put_object requires a stream, not raw bytes
        data_stream = io.BytesIO(file_data)

        # 3. Upload
        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=data_stream,
            length=len(file_data),
            content_type="application/octet-stream",
        )

        logger.info(f"Successfully uploaded to MinIO: {bucket_name}/{object_name}")
        return object_name

    except S3Error as e:
        logger.error(f"MinIO S3 Error during upload: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error uploading to MinIO: {e}")
        raise e


def fetch_raw_content_from_minio(
    object_name: str, bucket_name: str = "raw-content"
) -> Optional[bytes]:
    """
    Retrieves raw content from MinIO. Used for debugging or 'View Source' features.
    """
    if not minio_client:
        return None

    try:
        response = minio_client.get_object(bucket_name=bucket_name, object_name=object_name)
        content = response.read()
        response.close()
        return content

    except Exception as e:
        logger.error(f"Failed to fetch object {object_name} from MinIO: {e}")
        return None
