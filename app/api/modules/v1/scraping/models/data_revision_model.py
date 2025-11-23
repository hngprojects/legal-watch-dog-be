import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class DataRevision(SQLModel, table=True):
    __tablename__ = "data_revisions"

    revision_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    source_id: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    status: str
    raw_content: Optional[str] = None
    minio_object_key: str = Field(nullable=False)
    extracted_data: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

    ai_summary: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    was_change_detected: Optional[bool] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = None
