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
from sqlmodel import func, select

from app.api.core.security import encrypt_auth_details
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.schemas.baseline_schema import BaselineAcceptanceRequest
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
            HTTPException: 400 if required prompts are missing or the URL already exists.
            HTTPException: 500 if creation fails.

        Examples:
            >>> service = SourceService()
            >>> source = await service.create_source(db, source_data)
            >>> print(source.name)
            'Ministry of Justice Website'
        """
        try:
            await self._ensure_prompt_requirements(db, source_data.jurisdiction_id)
            existing_source = await db.scalar(
                select(Source).where(
                    Source.url == str(source_data.url),
                    Source.jurisdiction_id == source_data.jurisdiction_id,
                    ~Source.is_deleted,
                )
            )
            if existing_source:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Source with this URL already exists in the jurisdiction",
                )

            encrypted_auth = None
            if source_data.auth_details:
                encrypted_auth = encrypt_auth_details(source_data.auth_details)
                logger.info(f"Encrypted auth details for source: {source_data.name}")

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

    async def bulk_create_sources(
        self,
        db: AsyncSession,
        sources_data: List["SourceCreate"],
    ) -> List[SourceRead]:
        """
        Create multiple sources in a single transaction.

        Args:
            db (AsyncSession): Database session.
            sources_data (List[SourceCreate]): List of source creation data.

        Returns:
            List[SourceRead]: List of created sources with sanitized fields.

        Raises:
            HTTPException: 400 if required prompts are missing or URLs already exist.
            HTTPException: 500 if creation fails.

        Examples:
            >>> sources = await service.bulk_create_sources(db, sources_data)
            >>> print(f"Created {len(sources)} sources")
            Created 3 sources
        """
        if not sources_data:
            return []

        try:
            unique_jurisdiction_ids = {source.jurisdiction_id for source in sources_data}
            for jurisdiction_id in unique_jurisdiction_ids:
                await self._ensure_prompt_requirements(db, jurisdiction_id)
            created_sources = []
            urls_to_check = [str(source.url) for source in sources_data]

            existing_sources = await db.execute(
                select(Source.url).where(Source.url.in_(urls_to_check))
            )
            existing_urls = set(existing_sources.scalars().all())

            duplicates = [url for url in urls_to_check if url in existing_urls]
            if duplicates:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Source URLs already exist: {', '.join(duplicates)}",
                )

            for source_data in sources_data:
                encrypted_auth = None
                if source_data.auth_details:
                    encrypted_auth = encrypt_auth_details(source_data.auth_details)
                    logger.info(f"Encrypted auth details for source: {source_data.name}")

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
                created_sources.append(db_source)

            await db.commit()

            for source in created_sources:
                await db.refresh(source)

            logger.info(f"Successfully created {len(created_sources)} sources in bulk")

            return [self._to_read_schema(source) for source in created_sources]

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to bulk create sources: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create sources",
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

        if jurisdiction_id:
            query = query.where(Source.jurisdiction_id == jurisdiction_id)
        if is_active is not None:
            query = query.where(Source.is_active == is_active)

        if not include_deleted:
            query = query.where(~Source.is_deleted)

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

        logger.debug(f"Updating source {source_id}, is_deleted={source.is_deleted}")

        try:
            update_data = source_data.model_dump(exclude_unset=True)

            if "auth_details" in update_data:
                auth_details = update_data.pop("auth_details")
                if auth_details:
                    source.auth_details_encrypted = encrypt_auth_details(auth_details)
                    logger.info(f"Updated encrypted auth for source: {source_id}")
                else:
                    source.auth_details_encrypted = None

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
                await db.delete(source)
                await db.commit()
                logger.info(f"Permanently deleted source: {source_id}")
                return {
                    "message": "Source permanently deleted",
                    "source_id": str(source_id),
                }
            else:
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

    async def get_source_revisions(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[DataRevision], int]:
        """
        Retrieve revision history for a specific source.

        Fetches all data revisions associated with a source, ordered by most recent first.
        Supports pagination for large revision histories.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID to get revisions for.
            skip (int): Number of records to skip (pagination). Default: 0.
            limit (int): Maximum number of records to return. Default: 50.

        Returns:
            tuple: (List[DataRevision], int) - List of revisions and total count.

        Raises:
            HTTPException: 404 if source not found.

        Examples:
            >>> revisions, total = await service.get_source_revisions(db, source_id)
            >>> print(f"Found {total} revisions, showing {len(revisions)}")
            Found 150 revisions, showing 50
        """

        source = await db.get(Source, source_id)
        if not source:
            logger.warning(f"Cannot fetch revisions - source not found: {source_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found",
            )

        query = (
            select(DataRevision)
            .where(DataRevision.source_id == source_id)
            .order_by(DataRevision.scraped_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)
        revisions = result.scalars().all()

        count_query = select(func.count()).where(DataRevision.source_id == source_id)
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        logger.info(f"Retrieved {len(revisions)} revisions for source {source_id} (total: {total})")
        return revisions, total

    async def accept_revision_as_baseline(
        self,
        db: AsyncSession,
        revision_id: uuid.UUID,
        acceptance_data: BaselineAcceptanceRequest,
        user_id: uuid.UUID,
    ) -> DataRevision:
        """
        Mark a revision as the accepted baseline for its source.

        This operation is atomic:
        1. Verifies the revision exists
        2. Unsets 'is_baseline' for any existing baseline for this source
        3. Sets 'is_baseline' to True for the target revision
        4. Records acceptance metadata (user, time, notes)

        Args:
            db (AsyncSession): Database session.
            revision_id (uuid.UUID): ID of the revision to accept.
            acceptance_data (BaselineAcceptanceRequest): Acceptance details (notes).
            user_id (uuid.UUID): ID of the user accepting the baseline.

        Returns:
            DataRevision: The updated revision.

        Raises:
            HTTPException: 404 if revision not found.
        """
        revision = await db.get(DataRevision, revision_id)
        if not revision:
            logger.warning(f"Cannot accept baseline - revision not found: {revision_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Revision not found",
            )

        try:
            # Unset existing baseline for this source
            # We do this in the same transaction to ensure only one baseline exists
            statement = (
                select(DataRevision)
                .where(DataRevision.source_id == revision.source_id)
                .where(DataRevision.is_baseline == True)  # noqa: E712
            )
            existing_baselines = await db.execute(statement)
            for old_baseline in existing_baselines.scalars().all():
                old_baseline.is_baseline = False
                db.add(old_baseline)

            # Set new baseline
            revision.is_baseline = True
            revision.baseline_accepted_at = func.now()
            revision.baseline_accepted_by = user_id
            revision.baseline_notes = acceptance_data.notes

            db.add(revision)
            await db.commit()
            await db.refresh(revision)

            logger.info(
                f"Revision {revision_id} accepted as baseline "
                f"for source {revision.source_id} by user {user_id}"
            )

            return revision

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to accept baseline for revision {revision_id}: {str(e)}", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to accept baseline",
            )

    async def get_current_baseline(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
    ) -> Optional[DataRevision]:
        """
        Retrieve the currently accepted baseline for a source.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID.

        Returns:
            Optional[DataRevision]: The current baseline revision, or None if none exists.
        """
        statement = (
            select(DataRevision)
            .where(DataRevision.source_id == source_id)
            .where(DataRevision.is_baseline == True)  # noqa: E712
        )
        result = await db.execute(statement)
        baseline = result.scalar_one_or_none()

        if baseline:
            logger.debug(f"Found active baseline {baseline.id} for source {source_id}")
        else:
            logger.debug(f"No active baseline found for source {source_id}")

        return baseline

    async def get_baseline_history(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[DataRevision], int]:
        """
        Retrieve history of accepted baselines for a source.

        Returns all revisions that have acceptance metadata (baseline_accepted_at is not None),
        ordered by acceptance time (most recent first). This includes both the current
        baseline and historical baselines.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID.
            skip (int): Pagination skip.
            limit (int): Pagination limit.

        Returns:
            tuple: (List[DataRevision], total_count)
        """
        # Verify source exists first
        source = await db.get(Source, source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found",
            )

        query = (
            select(DataRevision)
            .where(DataRevision.source_id == source_id)
            .where(DataRevision.baseline_accepted_at.is_not(None))
            .order_by(DataRevision.baseline_accepted_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)
        history = result.scalars().all()

        count_query = (
            select(func.count())
            .where(DataRevision.source_id == source_id)
            .where(DataRevision.baseline_accepted_at.is_not(None))
        )
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        logger.info(f"Retrieved {len(history)} historical baselines for source {source_id}")
        return history, total

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

    async def _ensure_prompt_requirements(
        self,
        db: AsyncSession,
        jurisdiction_id: uuid.UUID,
    ) -> None:
        """Validate that project and jurisdiction prompts exist before source creation.

        Args:
            db (AsyncSession): Async database session used for lookups.
            jurisdiction_id (uuid.UUID): Jurisdiction identifier associated with the source.

        Returns:
            None

        Raises:
            HTTPException: 404 if jurisdiction or project cannot be located.
            HTTPException: 400 if project instructions, jurisdiction prompt, or both are missing.

        Examples:
            >>> service = SourceService()
            >>> await service._ensure_prompt_requirements(db, jurisdiction_id)
            >>> # Continues without raising when prompts are available
        """

        jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
        if not jurisdiction or jurisdiction.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jurisdiction not found",
            )

        project = await db.get(Project, jurisdiction.project_id)
        if not project or project.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found for jurisdiction",
            )

        project_prompt = (project.master_prompt or "").strip()
        jurisdiction_prompt = (jurisdiction.prompt or "").strip()

        has_project_prompt = bool(project_prompt)
        has_jurisdiction_prompt = bool(jurisdiction_prompt)

        if has_project_prompt and has_jurisdiction_prompt:
            return

        if not has_project_prompt and not has_jurisdiction_prompt:
            message = (
                "Add the project instruction (master prompt) and jurisdiction prompt before adding "
                "sources. These instructions guide the AI scraping pipeline."
            )
        elif not has_project_prompt:
            message = (
                "Add the project instruction (master prompt) before adding sources. "
                "These instructions guide the AI scraping pipeline."
            )
        else:
            message = (
                "Add jurisdiction prompt before adding sources. "
                "These instructions guide the AI scraping pipeline."
            )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
