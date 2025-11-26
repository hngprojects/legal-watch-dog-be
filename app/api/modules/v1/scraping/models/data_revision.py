from datetime import datetime
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class DataRevision(SQLModel, table=True):
    __tablename__ = "data_revisions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(index=True, foreign_key="sources.id")
    minio_object_key: str = Field(nullable=False)
    content_hash: Optional[str] = Field(default=None, nullable=True, index=True)
    extracted_data: Optional[Dict] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=True),
    )
    ai_summary: Optional[str] = Field(default=None)
    ai_markdown_summary: Optional[str] = Field(default=None)
    ai_confidence_score: Optional[float] = Field(default=None)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    was_change_detected: bool = Field(default=False)
