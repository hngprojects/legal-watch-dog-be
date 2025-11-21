# app/api/modules/v1/scraping/models/scrape_job.py
import uuid
from datetime import datetime
from typing import Dict, Optional  # Import Optional and Dict

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from sqlmodel import Field  # Import Field from sqlmodel

from app.api.db.database import Base


class ScrapeJob(Base):
    """Represents a single web scraping job in the database.

    Attributes:
        scrape_id (uuid.UUID): A unique identifier for each scrape job.
        jurisdiction_id (uuid.UUID): The ID of the jurisdiction this scrape job belongs to.
        project_id (uuid.UUID): The ID of the project this scrape job is associated with.
        created_at (datetime): The timestamp when the scrape job was initiated.
        sources (dict): A JSONB field storing various information about the data sources.
    """
    __tablename__ = "scrape_jobs"

    scrape_id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    jurisdiction_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("jurisdictions.id"), nullable=False)
    )
    project_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime, default=func.now(), nullable=False)
    )
    sources: Dict = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False, default={})
    )

    def __repr__(self):
        return (
            f"<ScrapeJob("
            f"scrape_id='{self.scrape_id}', "
            f"project_id='{self.project_id}', "
            f"jurisdiction_id='{self.jurisdiction_id}')>"
        )