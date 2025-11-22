import difflib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.modules.v1.scraping.models.change_diff_model import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision_model import DataRevision

logger = logging.getLogger(__name__)


class ChangeDetectionService:
    """
    Service responsible for handling creation of data revisions and detecting
    whether meaningful changes occurred between the previous and current revision.

    This includes:
    - Fetching the most recent revision for a source
    - Comparing AI-generated summaries
    - Generating unified diff patches
    - Creating ChangeDiff records when a change is detected
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the ChangeDetectionService.

        Args:
            db (AsyncSession): The async database session used for database operations.
        """
        self.db = db

    async def get_previous_revision(self, source_id: str) -> Optional[DataRevision]:
        """
        Retrieve the most recent (non-deleted) revision for a specific source_id.

        Args:
            source_id (str): Identifier of the data source.

        Returns:
            Optional[DataRevision]: The latest revision or None if none exists.

        Raises:
            SQLAlchemyError: If the database query fails.
        """
        result = await self.db.execute(
            select(DataRevision)
            .where(DataRevision.source_id == source_id)
            .where(DataRevision.deleted_at.is_(None))
            .order_by(DataRevision.created_at.desc())
        )
        return result.scalars().first()

    def compare_summaries(self, old_summary: str, new_summary: str) -> bool:
        """
        Compare two AI summaries to determine if they differ.

        Args:
            old_summary (str): Summary from the previous revision.
            new_summary (str): Newly generated summary.

        Returns:
            bool: True if they are different, False otherwise.
        """
        if old_summary is None and new_summary is None:
            return False
        if old_summary is None or new_summary is None:
            return True

        return old_summary.strip() != new_summary.strip()

    def generate_diff_patch(self, old_summary: str, new_summary: str) -> Dict[str, Any]:
        """
        Generate a detailed unified diff patch between two summaries.

        Args:
            old_summary (str): Previous summary text.
            new_summary (str): Current summary text.

        Returns:
            Dict[str, Any]: Structured diff data including additions, deletions,
                            previews and unified diff.
        """
        old_summary = old_summary or ""
        new_summary = new_summary or ""

        old_lines = old_summary.splitlines(keepends=True)
        new_lines = new_summary.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="old_summary",
                tofile="new_summary",
                lineterm="",
            )
        )

        diff_patch = {
            "diff_type": "text_comparison",
            "old_length": len(old_summary),
            "new_length": len(new_summary),
            "unified_diff": diff,
            "change_summary": {
                "additions": sum(
                    1
                    for line in diff
                    if line.startswith("+") and not line.startswith("+++")
                ),
                "deletions": sum(
                    1
                    for line in diff
                    if line.startswith("-") and not line.startswith("---")
                ),
            },
            "old_preview": (
                old_summary[:200] + "..." if len(old_summary) > 200 else old_summary
            ),
            "new_preview": (
                new_summary[:200] + "..." if len(new_summary) > 200 else new_summary
            ),
        }

        return diff_patch

    async def create_revision_with_detection(
        self,
        source_id: str,
        scraped_at: datetime,
        status: str,
        raw_content: str,
        extracted_data: Dict[str, Any],
        ai_summary: str,
    ) -> Tuple[DataRevision, Optional[ChangeDiff]]:
        """
        Create a new revision for a source and detect whether changes occurred
        compared to the previous revision.

        Args:
            source_id (str): Unique identifier for the scraped source.
            scraped_at (datetime): Timestamp of the scraping operation.
            status (str): Current status of the scraped data.
            raw_content (str): Raw scraped text/content.
            extracted_data (Dict[str, Any]): Parsed structured data.
            ai_summary (str): AI-generated summary used for change comparison.

        Returns:
            Tuple[DataRevision, Optional[ChangeDiff]]:
                - Newly created revision
                - A ChangeDiff record if changes were detected, otherwise None

        Raises:
            SQLAlchemyError: If database operations fail.
        """

        # Retrieve previous revision
        previous_revision = await self.get_previous_revision(source_id)

        # Determine whether a change occurred
        was_change_detected = False
        if previous_revision is not None:
            was_change_detected = self.compare_summaries(
                previous_revision.ai_summary, ai_summary
            )

        # Create new revision record
        new_revision = DataRevision(
            revision_id=str(uuid.uuid4()),
            source_id=source_id,
            scraped_at=scraped_at,
            status=status,
            raw_content=raw_content,
            extracted_data=extracted_data,
            ai_summary=ai_summary,
            was_change_detected=was_change_detected,
            created_at=datetime.utcnow(),
            deleted_at=None,
        )

        self.db.add(new_revision)
        await self.db.flush()

        # Create ChangeDiff only if a change was detected
        change_diff = None
        if was_change_detected and previous_revision is not None:
            logger.info("Change detected, creating ChangeDiff record.")
            diff_patch = self.generate_diff_patch(
                previous_revision.ai_summary, ai_summary
            )
            change_diff = ChangeDiff(
                diff_id=str(uuid.uuid4()),
                new_revision_id=new_revision.revision_id,
                old_revision_id=previous_revision.revision_id,
                diff_patch=diff_patch,
                ai_confidence=None,
            )
            self.db.add(change_diff)
            logger.info(f"Created change_diff: {change_diff}")

        # Commit and refresh
        await self.db.commit()
        await self.db.refresh(new_revision)
        if change_diff:
            await self.db.refresh(change_diff)

        return new_revision, change_diff
