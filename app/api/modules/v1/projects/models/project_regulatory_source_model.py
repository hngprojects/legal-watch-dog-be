import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.projects.models.project_model import Project


class ProjectRegulatorySource(SQLModel, table=True):
    """
    Regulatory sources attached to a Project.
    Examples: website URLs, document links, PDF sources, etc.
    """

    __tablename__ = "project_regulatory_sources"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    project_id: uuid.UUID = Field(
        foreign_key="projects.id",
        index=True,
        description="Project that this regulatory source belongs to",
    )

    value: str = Field(
        max_length=500,
        description="The URL or link to the regulatory source"
    )

    description: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="A human-readable description of the source"
    )

    source_type: Optional[str] = Field(
        default="website",
        description="Type of source: website, document, pdf, etc."
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    project: Optional["Project"] = Relationship(back_populates="regulatory_sources")
