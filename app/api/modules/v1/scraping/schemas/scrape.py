"""
Pydantic schemas for Source entity.

Defines request and response models for source CRUD operations.
"""

import uuid
from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field, HttpUrl

from app.api.modules.v1.scraping.models.scrape import SourceType


class SourceCreate(BaseModel):
    """
    Schema for creating a new source.

    Attributes:
        jurisdiction_id (uuid.UUID): Parent jurisdiction UUID.
        name (str): Human-readable source name.
        url (HttpUrl): Target URL to scrape.
        source_type (SourceType): Type of source (web, pdf, api).
        scrape_frequency (str): Cron-like frequency string (e.g., "DAILY", "HOURLY").
        auth_details (Optional[Dict]): Authentication credentials (will be encrypted).
        scraping_rules (Optional[Dict]): Custom extraction rules.
    """

    jurisdiction_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    url: HttpUrl
    source_type: SourceType = SourceType.WEB
    scrape_frequency: str = Field(default="DAILY", min_length=1)
    auth_details: Optional[Dict] = None
    scraping_rules: Optional[Dict] = {}


class SourceUpdate(BaseModel):
    """
    Schema for updating an existing source.

    All fields are optional to support partial updates.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[HttpUrl] = None
    source_type: Optional[SourceType] = None
    scrape_frequency: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None
    auth_details: Optional[Dict] = None
    scraping_rules: Optional[Dict] = None


class SourceRead(BaseModel):
    """
    Schema for source responses.

    Ensures auth_details are never exposed (only has_auth flag).

    Attributes:
        id (uuid.UUID): Source unique identifier.
        jurisdiction_id (uuid.UUID): Parent jurisdiction UUID.
        name (str): Source name.
        url (str): Source URL.
        source_type (SourceType): Type of source.
        scrape_frequency (str): Scraping schedule.
        is_active (bool): Whether source is enabled.
        has_auth (bool): Whether source has authentication configured.
        created_at (datetime): Timestamp of creation.
    """

    id: uuid.UUID
    jurisdiction_id: uuid.UUID
    name: str
    url: str
    source_type: SourceType
    scrape_frequency: str
    is_active: bool
    has_auth: bool
    created_at: datetime

    class Config:
        from_attributes = True
