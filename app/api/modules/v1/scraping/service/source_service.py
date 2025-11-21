"""
Service layer for Source CRUD operations.

Handles all business logic for source management including:
- CRUD operations for sources
- Encryption/decryption of auth details
- Validation and error handling
- Database transactions
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.security import encrypt_auth_details
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.schemas.source_service import (
    SourceCreate,
    SourceRead,
    SourceUpdate,
)

logger = logging.getLogger("app")


class SourceService:
    """
    Business logic for Source entity operations.

    Provides centralized handling of:
    - Source creation with encrypted auth details
    - Source retrieval (single and list)
    - Source updates
    - Source deletion
    - Secure credential management
    """

    async def create_source(
        self,
        db: AsyncSession,
        source_data: SourceCreate,
    ) -> SourceRead:
        """
        Create a new source with encrypted auth details.

        Args:
            db (AsyncSession): Database session.
            source_data (SourceCreate): Source creation data.

        Returns:
            SourceRead: The created source with sanitized fields.

        Raises:
            HTTPException: 400 if source URL already exists, 500 if creation fails.

        Examples:
            >>> service = SourceService()
            >>> source = await service.create_source(db, source_data)
            >>> print(source.name)
            'Ministry of Justice Website'
        """
        try:
            # Check if source URL already exists
            existing_source = await db.scalar(
                select(Source).where(Source.url == str(source_data.url))
            )
            if existing_source:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Source with this URL already exists",
                )

            # Handle encryption of auth details
            encrypted_auth = None
            if source_data.auth_details:
                encrypted_auth = encrypt_auth_details(source_data.auth_details)
                logger.info(f"Encrypted auth details for source: {source_data.name}")

            # Create database object
            db_source = Source(
                jurisdiction_id=source_data.jurisdiction_id,
                name=source_data.name,
                url=str(source_data.url),
                source_type=source_data.source_type,
                scrape_frequency=source_data.scrape_frequency,
                scraping_rules=source_data.scraping_rules or {},
                auth_details_encrypted=encrypted_auth,
            )

            db.add(db_source)
            await db.commit()
            await db.refresh(db_source)

            logger.info(f"Successfully created source: {db_source.id} - {db_source.name}")

            # Return sanitized response
            return self._to_read_schema(db_source)

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create source: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create source",
            )

    async def get_source(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        include_deleted: bool = True,
    ) -> SourceRead:
        """
        Retrieve a single source by ID.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID.
            include_deleted (bool): If True, include soft-deleted sources.
                Default is True (for recovery).

        Returns:
            SourceRead: The source with sanitized fields.

        Raises:
            HTTPException: If source not found (404).

        Examples:
            >>> source = await service.get_source(db, source_id)
            >>> print(source.has_auth)
            True
        """
        source = await db.get(Source, source_id)

        if not source:
            logger.warning(f"Source not found: {source_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found",
            )

        # Allow access to soft-deleted sources for recovery purposes
        if source.is_deleted and not include_deleted:
            logger.warning(f"Source is deleted and cannot be accessed: {source_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found",
            )

        logger.info(f"Retrieved source: {source_id}")
        return self._to_read_schema(source)

    async def get_sources(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        jurisdiction_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None,
        include_deleted: bool = False,
    ) -> List[SourceRead]:
        """
        Retrieve a list of sources with optional filtering.

        Args:
            db (AsyncSession): Database session.
            skip (int): Number of records to skip (pagination).
            limit (int): Maximum number of records to return.
            jurisdiction_id (Optional[uuid.UUID]): Filter by jurisdiction.
            is_active (Optional[bool]): Filter by active status.
            include_deleted (bool): If True, include soft-deleted sources. Default is False.

        Returns:
            List[SourceRead]: List of sources with sanitized fields.

        Examples:
            >>> sources = await service.get_sources(db, jurisdiction_id=juris_id)
            >>> len(sources)
            5
        """
        query = select(Source)

        # Apply filters
        if jurisdiction_id:
            query = query.where(Source.jurisdiction_id == jurisdiction_id)
        if is_active is not None:
            query = query.where(Source.is_active == is_active)

        # Exclude soft-deleted sources by default
        if not include_deleted:
            query = query.where(~Source.is_deleted)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        sources = result.scalars().all()

        logger.info(f"Retrieved {len(sources)} sources")
        return [self._to_read_schema(source) for source in sources]

    async def update_source(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        source_data: SourceUpdate,
    ) -> SourceRead:
        """
        Update an existing source.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID to update.
            source_data (SourceUpdate): Updated source data (partial allowed).

        Returns:
            SourceRead: The updated source with sanitized fields.

        Raises:
            HTTPException: If source not found (404) or update fails.

        Examples:
            >>> updated = await service.update_source(db, source_id, update_data)
            >>> print(updated.scrape_frequency)
        """
        source = await db.get(Source, source_id)

        if not source:
            logger.warning(f"Cannot update - source not found: {source_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found",
            )

        # Allow updating soft-deleted sources (for undo delete)
        logger.debug(f"Updating source {source_id}, is_deleted={source.is_deleted}")

        try:
            # Update fields (excluding unset values)
            update_data = source_data.model_dump(exclude_unset=True)

            # Handle auth_details encryption if provided
            if "auth_details" in update_data:
                auth_details = update_data.pop("auth_details")
                if auth_details:
                    source.auth_details_encrypted = encrypt_auth_details(auth_details)
                    logger.info(f"Updated encrypted auth for source: {source_id}")
                else:
                    source.auth_details_encrypted = None

            # Update other fields
            for field, value in update_data.items():
                if field == "url" and value:
                    value = str(value)
                setattr(source, field, value)

            await db.commit()
            await db.refresh(source)

            logger.info(f"Successfully updated source: {source_id}")
            return self._to_read_schema(source)

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update source {source_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update source",
            )

    async def delete_source(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        permanent: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete a source by ID (soft delete by default, hard delete if permanent=True).

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID to delete.
            permanent (bool): If True, perform hard delete; otherwise soft delete.

        Returns:
            Dict[str, Any]: Confirmation message.

        Raises:
            HTTPException: If source not found (404) or deletion fails.

        Examples:
            >>> result = await service.delete_source(db, source_id)
            >>> print(result["message"])
            'Source successfully deleted'
            >>> result = await service.delete_source(db, source_id, permanent=True)
            >>> print(result["message"])
            'Source permanently deleted'
        """
        source = await db.get(Source, source_id)

        if not source:
            logger.warning(f"Cannot delete - source not found: {source_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found",
            )

        try:
            if permanent:
                # Hard delete: remove from database
                await db.delete(source)
                await db.commit()
                logger.info(f"Permanently deleted source: {source_id}")
                return {
                    "message": "Source permanently deleted",
                    "source_id": str(source_id),
                }
            else:
                # Soft delete: mark as deleted
                source.is_deleted = True
                await db.commit()
                await db.refresh(source)
                logger.info(f"Soft deleted source: {source_id}")
                return {
                    "message": "Source successfully deleted",
                    "source_id": str(source_id),
                }

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete source {source_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete source",
            )

    def _to_read_schema(self, source: Source) -> SourceRead:
        """
        Convert a Source model to SourceRead schema.

        Ensures auth details are never exposed in responses.

        Args:
            source (Source): Source database model.

        Returns:
            SourceRead: Sanitized source response schema.
        """
        return SourceRead(
            id=source.id,
            jurisdiction_id=source.jurisdiction_id,
            name=source.name,
            url=source.url,
            source_type=source.source_type,
            scrape_frequency=source.scrape_frequency,
            is_active=source.is_active,
            is_deleted=source.is_deleted,
            has_auth=bool(source.auth_details_encrypted),
            created_at=source.created_at,
        )
