from datetime import datetime
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Field, SQLModel


class DataRevision(SQLModel, table=True):
    __tablename__ = "data_revisions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(index=True, foreign_key="sources.id")
    minio_object_key: str = Field(nullable=False)
    extracted_data: Optional[Dict] = Field(default={}, sa_column=Field(sa_type=JSON))
    ai_summary: Optional[str] = Field(default=None)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    was_change_detected: bool = Field(default=False)
