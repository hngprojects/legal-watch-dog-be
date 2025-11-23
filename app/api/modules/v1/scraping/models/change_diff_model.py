import uuid
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ChangeDiff(SQLModel, table=True):
    __tablename__ = "change_diff"

    diff_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    new_revision_id: str
    old_revision_id: str
    diff_patch: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    ai_confidence: Optional[float] = None
