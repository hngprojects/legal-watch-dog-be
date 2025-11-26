import io
import logging
from typing import Optional

try:
    from minio import Minio
    from minio.error import S3Error

    _HAS_MINIO = True
except Exception as _e:
    Minio = None
    S3Error = Exception
    _HAS_MINIO = False

from app.api.core.config import settings

logger = logging.getLogger(__name__)


minio_client = None
if _HAS_MINIO:
    try:
        minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    except Exception as e:
        logger.critical(f"Failed to initialize MinIO client: {e}")
        minio_client = None
else:
    logger.warning("MinIO SDK not installed.")


def upload_raw_content(file_data: bytes, bucket_name: str, object_name: str) -> str:
    """
    Upload raw byte content to the specified MinIO bucket.

    Args:
        file_data (bytes): The binary content to upload (HTML, PDF, text, etc.).
        bucket_name (str): The destination MinIO bucket name.
        object_name (str): The object key under which the file will be stored.

    Returns:
        str: The object_name (key) upon successful upload.

    Raises:
        Exception: If MinIO is not installed, client initialization failed,
                   or if the upload process encounters an error.
    """
    if not _HAS_MINIO:
        raise Exception(
            "Missing optional dependency: `minio` package is not installed."
            "install minio` to enable storage operations."
        )
    if not minio_client:
        raise Exception("MinIO client is not initialized. Check configuration.")

    try:
        # Ensure bucket exists or create it
        try:
            if not minio_client.bucket_exists(bucket_name=bucket_name):
                logger.info(f"Bucket '{bucket_name}' does not exist. Creating it...")
                minio_client.make_bucket(bucket_name=bucket_name)
        except Exception as e:
            logger.warning(f"Bucket existence check failed (may already exist): {e}")

            try:
                minio_client.make_bucket(bucket_name=bucket_name)
            except Exception as create_err:
                if (
                    "BucketAlreadyExists" not in str(create_err)
                    and "BucketAlreadyOwnedByYou" not in str(create_err)
                ):
                    raise create_err

        # Upload object
        data_stream = io.BytesIO(file_data)
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
    Retrieve raw byte content from a MinIO bucket.

    Args:
        object_name (str): The key identifying the object to retrieve.
        bucket_name (str, optional): The bucket to fetch from. Defaults to "raw-content".

    Returns:
        Optional[bytes]:
            - The raw file contents as bytes if the object is found and read successfully.
            - None if the object does not exist, MinIO is unavailable, or an error occurs.
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
