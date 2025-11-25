"""
Source model for scraping configuration.
Updated to use Timezone-Aware datetimes (TIMESTAMP WITH TIME ZONE).
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, TYPE_CHECKING

from sqlmodel import JSON, Column, Field, Relationship, SQLModel
# Import necessary SQLAlchemy types
from sqlalchemy import DateTime 

if TYPE_CHECKING:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction


class SourceType(str, Enum):
    """Enumeration of supported source types."""

    WEB = "web"
    PDF = "pdf"
    API = "api"


class ScrapeFrequency(str, Enum):
    """Enumeration of supported scrape frequencies."""

    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


# Define a lambda for timezone-aware UTC now
def now_utc_aware():
    return datetime.now(timezone.utc)


class Source(SQLModel, table=True):
    """
    Source entity for web scraping configuration.
    All datetime fields are now timezone-aware.
    """

    __tablename__ = "sources"
    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    jurisdiction_id: uuid.UUID = Field(foreign_key="jurisdictions.id", index=True)

    name: str
    url: str
    source_type: SourceType = Field(default=SourceType.WEB)

    scrape_frequency: ScrapeFrequency = Field(default=ScrapeFrequency.DAILY)
    
    # --- TIMEZONE AWARE FIELDS ---
    next_scrape_time: Optional[datetime] = Field(
        default=None,
        # Explicitly use TIMESTAMP WITH TIME ZONE
        sa_column=Column(DateTime(timezone=True))
    )
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False, index=True)

    auth_details_encrypted: Optional[str] = Field(default=None)
    scraping_rules: Dict = Field(default={}, sa_column=Column(JSON))

    created_at: datetime = Field(
        # Use timezone-aware default factory
        default_factory=now_utc_aware, 
        # Explicitly use TIMESTAMP WITH TIME ZONE
        sa_column=Column(DateTime(timezone=True))
    )

    jurisdiction: Optional["Jurisdiction"] = Relationship(back_populates="sources")