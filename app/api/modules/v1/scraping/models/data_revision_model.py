from sqlalchemy import Column, String, Text, Boolean, DateTime, Float, func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional
import uuid


class DataRevision(SQLModel, table=True):
    __tablename__ = "data_revision"
    
    revision_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    source_id: str
    scraped_at: datetime
    status: str
    raw_content: Optional[str] = None
    extracted_data: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    ai_summary: Optional[str] = None
    was_change_detected: Optional[bool] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None
