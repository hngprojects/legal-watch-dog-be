import json
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

    Now handles JSON AI summaries with semantic comparison.
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

    def compare_json_summaries(
        self, old_summary: Dict[str, Any], new_summary: Dict[str, Any]
    ) -> bool:
        """
        Compare two JSON AI summaries to determine if meaningful changes occurred.

        Args:
            old_summary (Dict): JSON summary from the previous revision.
            new_summary (Dict): Newly generated JSON summary.

        Returns:
            bool: True if meaningful changes detected, False otherwise.
        """
        if not old_summary and not new_summary:
            return False
        if not old_summary or not new_summary:
            return True

        # Compare critical fields that indicate meaningful changes
        critical_fields = ["summary", "changes_detected", "risk_level", "key_points"]

        for field in critical_fields:
            old_val = old_summary.get(field)
            new_val = new_summary.get(field)

            if self._field_changed_meaningfully(old_val, new_val):
                logger.info(f"Meaningful change detected in field: {field}")
                return True

        return False

    def _field_changed_meaningfully(self, old_val: Any, new_val: Any) -> bool:
        """
        Determine if a field changed meaningfully.
        """
        # Handle None cases
        if old_val is None and new_val is None:
            return False
        if old_val is None or new_val is None:
            return True

        # Handle different types
        if type(old_val) is not type(new_val):

            return True

        # Handle strings with semantic comparison
        if isinstance(old_val, str) and isinstance(new_val, str):
            return self._compare_text_semantic(old_val.strip(), new_val.strip())

        # Handle lists (like key_points)
        if isinstance(old_val, list) and isinstance(new_val, list):
            return self._compare_lists_meaningfully(old_val, new_val)

        # Handle other types with simple comparison
        return old_val != new_val

    def _compare_text_semantic(
        self, text1: str, text2: str, threshold: float = 0.85
    ) -> bool:
        """
        Compare text using semantic similarity.
        Returns True if texts are meaningfully different.
        """
        if text1 == text2:
            return False

        if not text1 or not text2:
            return True

        try:
            # Simple word-based similarity as lightweight semantic check
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())

            if not words1 and not words2:
                return False

            intersection = words1.intersection(words2)
            union = words1.union(words2)

            similarity = len(intersection) / len(union) if union else 0
            logger.debug(f"Text similarity: {similarity:.2f}")

            return similarity < threshold

        except Exception as e:
            logger.warning(f"Semantic comparison failed, using fallback: {e}")
            return text1 != text2

    def _compare_lists_meaningfully(self, old_list: list, new_list: list) -> bool:
        """
        Compare lists for meaningful differences.
        """
        if old_list == new_list:
            return False

        # Convert lists to text for semantic comparison
        old_text = " ".join(str(item) for item in old_list)
        new_text = " ".join(str(item) for item in new_list)

        return self._compare_text_semantic(old_text, new_text, threshold=0.8)

    def generate_json_diff_patch(
        self, old_summary: Dict[str, Any], new_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a detailed diff patch between two JSON summaries.

        Args:
            old_summary (Dict): Previous JSON summary.
            new_summary (Dict): Current JSON summary.

        Returns:
            Dict[str, Any]: Structured diff data including field-level changes.
        """
        old_summary = old_summary or {}
        new_summary = new_summary or {}

        # Track changes at field level
        field_changes = {}
        critical_fields = ["summary", "changes_detected", "risk_level", "key_points"]

        for field in critical_fields:
            old_val = old_summary.get(field)
            new_val = new_summary.get(field)

            if self._field_changed_meaningfully(old_val, new_val):
                field_changes[field] = {
                    "old_value": old_val,
                    "new_value": new_val,
                    "change_type": "modified",
                }

        diff_patch = {
            "diff_type": "json_comparison",
            "field_changes": field_changes,
            "change_summary": {
                "fields_changed": list(field_changes.keys()),
                "total_changes": len(field_changes),
            },
            "old_preview": {
                "summary": str(old_summary.get("summary", ""))[:200],
                "risk_level": old_summary.get("risk_level"),
                "key_points_count": len(old_summary.get("key_points", [])),
            },
            "new_preview": {
                "summary": str(new_summary.get("summary", ""))[:200],
                "risk_level": new_summary.get("risk_level"),
                "key_points_count": len(new_summary.get("key_points", [])),
            },
        }

        return diff_patch

    async def create_revision_with_detection(
        self,
        source_id: str,
        scraped_at: datetime,
        status: str,
        raw_content: str,
        minio_object_key: str,
        extracted_data: Dict[str, Any],
        ai_summary: Dict[str, Any],
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
            ai_summary (Dict[str, Any]): AI-generated JSON summary used for change comparison.

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
        previous_ai_summary = None

        if previous_revision is not None:
            # Parse previous AI summary from JSON string stored in database
            try:
                if previous_revision.ai_summary:
                    previous_ai_summary = previous_revision.ai_summary
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse previous AI summary as JSON, treating as no previous data"
                )
                previous_ai_summary = None

        # Compare summaries
        if previous_ai_summary is not None:
            was_change_detected = self.compare_json_summaries(
                previous_ai_summary, ai_summary
            )
        else:
            # First revision or no previous valid summary
            was_change_detected = True

        # Create new revision record - store AI summary as JSON string
        new_revision = DataRevision(
            revision_id=str(uuid.uuid4()),
            source_id=source_id,
            scraped_at=scraped_at,
            status=status,
            raw_content=raw_content,
            extracted_data=extracted_data,
            minio_object_key=minio_object_key,
            ai_summary=ai_summary,
            was_change_detected=was_change_detected,
            created_at=datetime.utcnow(),
            deleted_at=None,
        )

        self.db.add(new_revision)
        await self.db.flush()

        # Create ChangeDiff only if a change was detected
        change_diff = None
        if was_change_detected and previous_ai_summary is not None:
            logger.info("Meaningful change detected, creating ChangeDiff record.")
            diff_patch = self.generate_json_diff_patch(previous_ai_summary, ai_summary)
            change_diff = ChangeDiff(
                diff_id=str(uuid.uuid4()),
                new_revision_id=new_revision.revision_id,
                old_revision_id=previous_revision.revision_id,
                diff_patch=diff_patch,
                ai_confidence=None,
            )
            self.db.add(change_diff)
            logger.info(
                f"Created change_diff with {len(diff_patch['field_changes'])} field changes"
            )

        # Commit and refresh
        await self.db.commit()
        await self.db.refresh(new_revision)
        if change_diff:
            await self.db.refresh(change_diff)

        return new_revision, change_diff
