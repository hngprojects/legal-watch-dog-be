from datetime import datetime
from io import BytesIO

from minio import Minio

from app.api.core.config import settings

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.USE_SSL,
)


def upload_raw_content(content: bytes | str, extension: str = "html") -> str:
    """
    Upload raw content (HTML or PDF) to MinIO and return the object key.
    """
    # Convert string to bytes if necessary
    if isinstance(content, str):
        content = content.encode("utf-8")
    
    object_key = f"raw/{datetime.utcnow().isoformat()}Z.{extension}"
    
    # Wrap bytes in a BytesIO object to provide a .read() method
    data_stream = BytesIO(content)
    
    minio_client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_key,
        data=data_stream,
        length=len(content),
        content_type="text/html" if extension == "html" else "application/pdf",
    )
    return object_key


def fetch_raw_content_from_minio(object_key: str) -> bytes:
    """
    Fetch raw content from MinIO.
    """
    response = minio_client.get_object(settings.MINIO_BUCKET, object_key)
    data = response.read()
    response.close()
    response.release_conn()
    return data
