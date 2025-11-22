import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, Text, UniqueConstraint, Column, DateTime, event, func
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

logger = logging.getLogger("app")

if TYPE_CHECKING:
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.source_model import Source
    from app.api.modules.v1.project_audit_log.models.project_audit_log_model import ProjectAuditLog


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

    deleted_at : datetime
        Timestamp indicating when the jurisdiction was soft-deleted.

    is_deleted : bool
        Soft-delete flag. True if the record is considered deleted but retained in DB.

    country : Optional[str]
        Country associated with this jurisdiction.

    state : Optional[str]
        State associated with this jurisdiction.

    city : Optional[str]
        City associated with this jurisdiction.

    is_active : bool
        Indicates if the jurisdiction is active.

    audit_logs : List[ProjectAuditLog]
        Related project audit logs.
    """

    __tablename__ = "jurisdictions"  # type: ignore
    __table_args__ = (
        UniqueConstraint("project_id", "parent_id", "name", name="uix_project_name"),
        CheckConstraint(
            "id IS NULL OR parent_id IS NULL OR id != parent_id", name="chk_parent_not_self"
        ),
    )

    # Core fields
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)

    project_id: UUID = Field(foreign_key="projects.id", ondelete="CASCADE")

    parent_id: Optional[UUID] = Field(
        default=None,
        foreign_key="jurisdictions.id",
        ondelete="SET NULL",
    )

    # RESTORED from second file (max_length, nullable=False, index=True)
    name: str = Field(max_length=255, nullable=False, index=True)

    description: str = Field(sa_column=Text)
    prompt: Optional[str] = Field(default=None, sa_column=Text)
    scrape_output: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Location fields (from second file)
    country: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)

    # RESTORED: nullable=False (from second file)
    is_active: bool = Field(default=True, nullable=False)

    # Soft-delete fields (from first file)
    is_deleted: bool = Field(default=False)

    # Timestamps — preserved *exactly* from first file
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    deleted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    # Relationships
    parent: Optional["Jurisdiction"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Jurisdiction.id"},
    )

    children: Mapped[List["Jurisdiction"]] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"cascade": "save-update, merge, refresh-expire"},
    )

    project: "Project" = Relationship(back_populates="jurisdictions")

    sources: List["Source"] = Relationship(back_populates="jurisdiction")

    # Added from second file
    audit_logs: List["ProjectAuditLog"] = Relationship(back_populates="jurisdiction")

    def __repr__(self):
        return f"<Jurisdiction id={self.id} name={self.name} project_id={self.project_id}>"


# Hierarchy validation logic — unchanged from first file
@event.listens_for(Jurisdiction, "before_update")
@event.listens_for(Jurisdiction, "before_insert")
def validate_hierarchy(mapper, connection, target):
    """
    Validate parent-child hierarchy to prevent self-parenting or circular references.
    """
    logger.debug(
        f"Validating hierarchy for jurisdiction {target.id} "
        f"(parent_id={target.parent_id})"
    )

    table = mapper.local_table

    if target.parent_id is not None and target.parent_id == target.id:
        logger.warning(
            f"Jurisdiction {target.id} attempted to set parent_id to itself."
        )
        raise ValueError("A jurisdiction cannot be its own parent.")

    parent_id = target.parent_id
    MAX_HIERARCHY_DEPTH = 1000
    depth = 0

    while parent_id is not None and depth < MAX_HIERARCHY_DEPTH:
        parent_row = (
            connection.execute(
                table.select().where(table.c.id == parent_id)
            )
            .mappings()
            .fetchone()
        )

        if parent_row is None:
            logger.debug(f"Parent id {parent_id} not found; stopping traversal.")
            break

        logger.debug(
            f"Traversing hierarchy: parent {parent_id} -> {parent_row['parent_id']}"
        )

        if parent_row["id"] == target.id:
            logger.warning(
                f"Circular hierarchy detected: Jurisdiction {target.id} "
                f"is in its own ancestor chain."
            )
            raise ValueError("Circular hierarchy detected.")

        parent_id = parent_row["parent_id"]
        depth += 1
