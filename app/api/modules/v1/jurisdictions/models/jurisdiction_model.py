from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Text
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.projects.models.project_model import Project


class Jurisdiction(SQLModel, table=True):
    """
    Represents a legal or regulatory jurisdiction within a project.

    A Jurisdiction defines the scope of regulations, rules, or compliance requirements
    that are independent of geography. Jurisdictions can have hierarchical relationships
    (parent-child) to model nested or dependent legal scopes.

    Fields:
    -------
    jurisdiction_id : UUID
        Primary key. Unique identifier for the jurisdiction.

    project_id : str
        Foreign key or reference to the parent project.

    parent_id : Optional[UUID]
        References another jurisdiction as the parent (for hierarchy). Null if top-level.

    name : str
        Human-readable name of the jurisdiction.
        Should be unique per project.

    description : str
        Detailed description or documentation of the jurisdiction.
        Stored as TEXT in the database.

    prompt : Optional[str]
        Optional AI prompt guiding extraction, summarization, or classification
        tasks for this jurisdiction. Stored as TEXT.

    scrape_output : Optional[Dict[str, Any]]
        Optional JSONB field storing processed AI results, scraping output,
        or other structured data associated with this jurisdiction.

    created_at : datetime
        Timestamp when the jurisdiction was created. Defaults to current UTC time.

    updated_at : datetime
        Timestamp of last update. Automatically set on modification.

    deleted_at : Optional[datetime]
        Timestamp indicating when the jurisdiction was soft-deleted.

    is_deleted : bool
        Soft-delete flag. True if the record is considered deleted but retained in DB.
    """

    __tablename__ = "jurisdictions"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    project_id: UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    parent_id: Optional[UUID] = Field(
        default=None, foreign_key="jurisdictions.id", ondelete="CASCADE"
    )
    name: str
    description: str = Field(sa_column=Text)
    prompt: Optional[str] = Field(default=None, sa_column=Text)
    scrape_output: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    deleted_at: Optional[datetime] = None
    is_deleted: bool = Field(default=False)

    project: "Project" = Relationship(back_populates="jurisdictions")
