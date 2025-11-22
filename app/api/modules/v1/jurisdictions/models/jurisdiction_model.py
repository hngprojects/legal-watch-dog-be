# app/api/modules/v1/jurisdiction/models/jurisdiction_model.py
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.project_audit_log.models.project_audit_log_model import ProjectAuditLog


class Jurisdiction(SQLModel, table=True):
    __tablename__ = "jurisdictions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)
    name: str = Field(max_length=255, nullable=False, index=True)
    country: str = Field(max_length=100, nullable=True)
    state: str = Field(max_length=100, nullable=True)
    city: str = Field(max_length=100, nullable=True)
    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # Relationship to ProjectAuditLog
    audit_logs: List["ProjectAuditLog"] = Relationship(back_populates="jurisdiction")
