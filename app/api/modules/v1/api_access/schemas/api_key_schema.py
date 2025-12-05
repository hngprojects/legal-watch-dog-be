from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProjectResponse(BaseModel):
    """Response schema for project data."""

    id: UUID
    org_id: UUID
    title: str
    description: Optional[str]


class JurisdictionResponse(BaseModel):
    """Response schema for jurisdiction data."""

    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]


class SourceResponse(BaseModel):
    """Response schema for source data."""

    id: UUID
    jurisdiction_id: UUID
    name: str
    url: str
