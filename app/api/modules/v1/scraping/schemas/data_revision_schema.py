from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DataRevisionResponse(BaseModel):
    """
    Schema for DataRevision response.
    """

    id: UUID
    source_id: UUID
    minio_object_key: str
    extracted_data: Optional[Dict] = None
    ai_summary: Optional[str] = None
    scraped_at: datetime
    was_change_detected: bool

    model_config = ConfigDict(from_attributes=True)
