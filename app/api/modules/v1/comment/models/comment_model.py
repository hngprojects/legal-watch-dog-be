import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Index, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.users.models.users_model import User


class Comment(SQLModel, table=True):
    """
    Comment model for storing user comments with mention support.

    Attributes:
        comment_id: Unique identifier for the comment
        user_id: User who created the comment
        content: The comment text content
        mentioned_user_ids: List of user IDs mentioned in the comment

        revision_id: Optional link to data revision
        source_id: Optional link to source
        organization_id: Optional link to organization
        project_id: Optional link to project

        created_at: When comment was created
        updated_at: When comment was last updated
        deleted_at: Soft delete timestamp
    """

    __tablename__ = "comments"

    comment_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    content: str = Field(sa_column=sa.Column(Text, nullable=False))

    mentioned_user_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
        description="List of user IDs mentioned in this comment",
    )

    ticket_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="data_revisions.id",
        index=True,
        description="Link to data revision if applicable",
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the comment was last updated",
    )

    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Soft delete timestamp",
    )

    user: Optional["User"] = Relationship()


Index("ix_comments_user_created", Comment.user_id, Comment.created_at.desc())
Index("ix_comments_revision", Comment.ticket_id)
Index("ix_comments_active", Comment.comment_id, postgresql_where=Comment.deleted_at.is_(None))
