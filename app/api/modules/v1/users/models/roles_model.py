from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field, Relationship, JSON
from sqlalchemy.dialects.postgresql import JSONB
import uuid


class Role(SQLModel, table=True):
    __tablename__ = "roles"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    name: str = Field(max_length=50, nullable=False, unique=True, index=True)

    description: Optional[str] = Field(default=None, max_length=500)

    permissions: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
