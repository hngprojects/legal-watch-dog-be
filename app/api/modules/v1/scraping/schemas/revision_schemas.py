from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DataRevisionResponse(BaseModel):
    """
    Response schema for DataRevision records.
    """
    id: UUID
    source_id: UUID
    minio_object_key: str
    content_hash: Optional[str]
    extracted_data: Optional[Dict[str, Any]]
    ai_summary: Optional[str]
    ai_markdown_summary: Optional[str]
    ai_confidence_score: Optional[float]
    scraped_at: datetime
    was_change_detected: bool

    class Config:
        from_attributes = True


class ChangeDiffResponse(BaseModel):
    """
    Response schema for ChangeDiff records.
    """
    diff_id: UUID
    new_revision_id: UUID
    old_revision_id: UUID
    diff_patch: Optional[Dict[str, Any]]
    ai_confidence: Optional[float]

    class Config:
        from_attributes = True


class RevisionListResponse(BaseModel):
    """
    Response schema for list of revisions with pagination info.
    """
    revisions: List[DataRevisionResponse]
    total: int
    page: int
    limit: int
    total_pages: Optional[int] = None


class ChangeListResponse(BaseModel):
    """
    Response schema for list of changes with pagination info.
    """
    changes: List[ChangeDiffResponse]
    total: int
    page: int
    limit: int
    total_pages: Optional[int] = None