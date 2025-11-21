"""
Source model for scraping configuration.

Defines the database schema for sources to be monitored and scraped.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from sqlmodel import JSON, Column, Field, SQLModel


class SourceType(str, Enum):
    """Enumeration of supported source types."""

    WEB = "web"
    PDF = "pdf"
    API = "api"


class Source(SQLModel, table=True):
    """
    Source entity for web scraping configuration.

    Stores URLs, scraping schedules, and encrypted credentials.
    """

    __tablename__ = "sources"
    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    jurisdiction_id: uuid.UUID = Field(index=True)

    name: str
    url: str
    source_type: SourceType = Field(default=SourceType.WEB)

    scrape_frequency: str = Field(default="DAILY")
    next_scrape_time: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False, index=True)

    auth_details_encrypted: Optional[str] = Field(default=None)
    scraping_rules: Dict = Field(default={}, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
