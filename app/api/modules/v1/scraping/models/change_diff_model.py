from sqlalchemy import Column, String, Text, Boolean, DateTime, Float, func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional
import uuid



class ChangeDiff(SQLModel, table=True):
    __tablename__ = "change_diff"
    
    diff_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    new_revision_id: str
    old_revision_id: str
    diff_patch: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    ai_confidence: Optional[float] = None