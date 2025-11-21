"""
Service layer for Project Regulatory Sources.
Contains all business logic related to regulatory sources.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.projects.models.project_regulatory_source_model import (
    ProjectRegulatorySource,
)

logger = logging.getLogger(__name__)


# -----------------------------
# CREATE REGULATORY SOURCE
# -----------------------------
async def create_regulatory_source(
    db: AsyncSession,
    project_id: UUID,
    value: str,
    source_type: Optional[str] = "website",
    description: Optional[str] = None,
) -> ProjectRegulatorySource:
    """
    Create a new regulatory source for a project.

    Args:
        db: Async database session
        project_id: UUID of the project
        value: URL or content of the source
        source_type: Type of source (default "website")
        description: Optional description of the source

    Returns:
        Newly created ProjectRegulatorySource object
    """
    logger.info(f"Creating regulatory source for project_id={project_id}")

    source = ProjectRegulatorySource(
        project_id=project_id,
        value=value,
        source_type=source_type,
        description=description,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    logger.info(f"Regulatory source created with id={source.id}")

    return source


# -----------------------------
# LIST ALL REGULATORY SOURCES
# -----------------------------
async def list_regulatory_sources(
    db: AsyncSession, project_id: UUID
) -> List[ProjectRegulatorySource]:
    """
    List all regulatory sources for a given project.

    Args:
        db: Async database session
        project_id: UUID of the project

    Returns:
        List of ProjectRegulatorySource objects
    """
    logger.info(f"Fetching all regulatory sources for project_id={project_id}")

    statement = select(ProjectRegulatorySource).where(
        ProjectRegulatorySource.project_id == project_id
    )
    result = await db.exec(statement)
    sources = result.all()

    logger.info(f"Found {len(sources)} sources for project_id={project_id}")

    return sources


# -----------------------------
# GET REGULATORY SOURCE BY ID
# -----------------------------
async def get_regulatory_source_by_id(
    db: AsyncSession, source_id: UUID
) -> Optional[ProjectRegulatorySource]:
    """
    Get a single regulatory source by its ID.

    Args:
        db: Async database session
        source_id: UUID of the regulatory source

    Returns:
        ProjectRegulatorySource object or None if not found
    """
    logger.info(f"Fetching regulatory source by id={source_id}")

    statement = select(ProjectRegulatorySource).where(
        ProjectRegulatorySource.id == source_id
    )
    result = await db.exec(statement)
    source = result.one_or_none()

    if source:
        logger.info(f"Regulatory source found: id={source.id}")
    else:
        logger.warning(f"Regulatory source not found: id={source_id}")

    return source


# -----------------------------
# UPDATE REGULATORY SOURCE
# -----------------------------
async def update_regulatory_source(
    db: AsyncSession,
    source_id: UUID,
    value: Optional[str] = None,
    source_type: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[ProjectRegulatorySource]:
    """
    Update a regulatory source.

    Args:
        db: Async database session
        source_id: UUID of the source
        value: New URL or content
        source_type: New type
        description: New description

    Returns:
        Updated ProjectRegulatorySource object or None if not found
    """
    logger.info(f"Updating regulatory source id={source_id}")

    source = await get_regulatory_source_by_id(db, source_id)
    if not source:
        logger.warning(f"Cannot update. Source not found: id={source_id}")
        return None

    if value is not None:
        source.value = value
    if source_type is not None:
        source.source_type = source_type
    if description is not None:
        source.description = description

    source.updated_at = datetime.now(timezone.utc)

    db.add(source)
    await db.commit()
    await db.refresh(source)

    logger.info(f"Regulatory source updated successfully: id={source.id}")

    return source


# -----------------------------
# DELETE REGULATORY SOURCE
# -----------------------------
async def delete_regulatory_source(
    db: AsyncSession, source_id: UUID
) -> bool:
    """
    Delete a regulatory source by ID.

    Args:
        db: Async database session
        source_id: UUID of the source

    Returns:
        True if deleted, False if not found
    """
    logger.info(f"Deleting regulatory source id={source_id}")

    source = await get_regulatory_source_by_id(db, source_id)
    if not source:
        logger.warning(f"Cannot delete. Source not found: id={source_id}")
        return False

    await db.delete(source)
    await db.commit()

    logger.info(f"Regulatory source deleted successfully: id={source_id}")
    return True
