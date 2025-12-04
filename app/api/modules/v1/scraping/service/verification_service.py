"""
Verification Service.

Handles change verification, suppression rule management, and false positive metrics.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.change_verification import ChangeVerification
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.suppression_rule import (
    SuppressionRule,
    SuppressionRuleType,
)
from app.api.modules.v1.scraping.schemas.verification_schema import (
    ChangeVerificationRequest,
    ChangeVerificationUpdate,
    FalsePositiveMetrics,
    SuppressionRuleCreate,
    SuppressionRuleUpdate,
)

logger = logging.getLogger("app")


class VerificationService:
    """Service for managing change verifications and suppression rules."""

    # ==================== Change Verification ====================

    async def verify_change(
        self,
        db: AsyncSession,
        diff_id: uuid.UUID,
        request: ChangeVerificationRequest,
        user_id: uuid.UUID,
    ) -> ChangeVerification:
        """
        Verify a detected change as true or false positive.

        Args:
            db: Database session
            diff_id: The change diff ID to verify
            request: Verification request with is_false_positive and optional feedback
            user_id: ID of the user performing verification

        Returns:
            The created ChangeVerification record

        Raises:
            HTTPException: 404 if diff not found, 409 if already verified
        """
        # Check if diff exists
        diff_query = select(ChangeDiff).where(ChangeDiff.diff_id == diff_id)
        diff_result = await db.execute(diff_query)
        diff = diff_result.scalars().first()

        if not diff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Change diff {diff_id} not found",
            )

        # Check if already verified
        existing_query = select(ChangeVerification).where(
            ChangeVerification.change_diff_id == diff_id
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This change has already been verified",
            )

        # Create suppression rule if requested
        suppression_rule_id = None
        if request.create_suppression_rule and request.suppression_rule:
            # Get source_id from the diff's revision
            revision_query = select(DataRevision).where(
                DataRevision.id == diff.new_revision_id
            )
            revision_result = await db.execute(revision_query)
            revision = revision_result.scalars().first()

            if revision:
                rule = await self.create_suppression_rule(
                    db=db,
                    source_id=revision.source_id,
                    rule_data=request.suppression_rule,
                    user_id=user_id,
                )
                suppression_rule_id = rule.id

        # Create verification
        verification = ChangeVerification(
            change_diff_id=diff_id,
            verified_by=user_id,
            is_false_positive=request.is_false_positive,
            feedback_reason=request.feedback_reason,
            suppression_rule_id=suppression_rule_id,
        )

        db.add(verification)
        await db.commit()
        await db.refresh(verification)

        logger.info(
            f"Change {diff_id} verified as "
            f"{'false positive' if request.is_false_positive else 'true positive'} "
            f"by user {user_id}"
        )

        return verification

    async def update_verification(
        self,
        db: AsyncSession,
        verification_id: uuid.UUID,
        update: ChangeVerificationUpdate,
        user_id: uuid.UUID,
    ) -> ChangeVerification:
        """
        Update an existing change verification.

        Args:
            db: Database session
            verification_id: The verification ID to update
            update: Update data
            user_id: ID of the user performing the update

        Returns:
            The updated ChangeVerification record

        Raises:
            HTTPException: 404 if verification not found, 403 if not the verifier
        """
        query = select(ChangeVerification).where(
            ChangeVerification.id == verification_id
        )
        result = await db.execute(query)
        verification = result.scalars().first()

        if not verification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Verification {verification_id} not found",
            )

        if verification.verified_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the original verifier can update this verification",
            )

        # Apply updates
        if update.is_false_positive is not None:
            verification.is_false_positive = update.is_false_positive
        if update.feedback_reason is not None:
            verification.feedback_reason = update.feedback_reason

        verification.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()
        await db.refresh(verification)

        logger.info(f"Verification {verification_id} updated by user {user_id}")

        return verification

    async def get_verification_by_diff(
        self,
        db: AsyncSession,
        diff_id: uuid.UUID,
    ) -> Optional[ChangeVerification]:
        """Get verification for a specific diff."""
        query = select(ChangeVerification).where(
            ChangeVerification.change_diff_id == diff_id
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_verified_changes(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ChangeVerification], int]:
        """
        Get verified changes for a source with pagination.

        Args:
            db: Database session
            source_id: Source ID to filter by
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            Tuple of (verifications list, total count)
        """
        # Join with ChangeDiff and DataRevision to filter by source
        base_query = (
            select(ChangeVerification)
            .join(ChangeDiff, ChangeVerification.change_diff_id == ChangeDiff.diff_id)
            .join(DataRevision, ChangeDiff.new_revision_id == DataRevision.id)
            .where(DataRevision.source_id == source_id)
            .order_by(ChangeVerification.created_at.desc())
        )

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = base_query.offset(skip).limit(limit)
        result = await db.execute(query)
        verifications = result.scalars().all()

        return list(verifications), total

    # ==================== Suppression Rules ====================

    async def create_suppression_rule(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        rule_data: SuppressionRuleCreate,
        user_id: uuid.UUID,
    ) -> SuppressionRule:
        """
        Create a new suppression rule for a source.

        Args:
            db: Database session
            source_id: Source to apply the rule to
            rule_data: Rule configuration
            user_id: ID of the user creating the rule

        Returns:
            The created SuppressionRule
        """
        # Validate regex pattern if applicable
        if rule_data.rule_type == SuppressionRuleType.REGEX:
            try:
                re.compile(rule_data.rule_pattern)
            except re.error as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid regex pattern: {str(e)}",
                )

        rule = SuppressionRule(
            source_id=source_id,
            rule_type=rule_data.rule_type,
            rule_pattern=rule_data.rule_pattern,
            rule_description=rule_data.rule_description,
            created_by=user_id,
        )

        db.add(rule)
        await db.commit()
        await db.refresh(rule)

        logger.info(
            f"Suppression rule created for source {source_id} "
            f"by user {user_id}: {rule_data.rule_type.value}"
        )

        return rule

    async def update_suppression_rule(
        self,
        db: AsyncSession,
        rule_id: uuid.UUID,
        update: SuppressionRuleUpdate,
        user_id: uuid.UUID,
    ) -> SuppressionRule:
        """
        Update a suppression rule.

        Args:
            db: Database session
            rule_id: Rule ID to update
            update: Update data
            user_id: ID of the user performing the update

        Returns:
            The updated SuppressionRule

        Raises:
            HTTPException: 404 if rule not found
        """
        query = select(SuppressionRule).where(SuppressionRule.id == rule_id)
        result = await db.execute(query)
        rule = result.scalars().first()

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suppression rule {rule_id} not found",
            )

        # Validate regex pattern if applicable
        if (
            update.rule_pattern
            and rule.rule_type == SuppressionRuleType.REGEX
        ):
            try:
                re.compile(update.rule_pattern)
            except re.error as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid regex pattern: {str(e)}",
                )

        # Apply updates
        if update.rule_pattern is not None:
            rule.rule_pattern = update.rule_pattern
        if update.rule_description is not None:
            rule.rule_description = update.rule_description
        if update.is_active is not None:
            rule.is_active = update.is_active

        rule.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()
        await db.refresh(rule)

        logger.info(f"Suppression rule {rule_id} updated by user {user_id}")

        return rule

    async def delete_suppression_rule(
        self,
        db: AsyncSession,
        rule_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Delete a suppression rule.

        Args:
            db: Database session
            rule_id: Rule ID to delete
            user_id: ID of the user performing the deletion

        Returns:
            True if deleted successfully

        Raises:
            HTTPException: 404 if rule not found
        """
        query = select(SuppressionRule).where(SuppressionRule.id == rule_id)
        result = await db.execute(query)
        rule = result.scalars().first()

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suppression rule {rule_id} not found",
            )

        await db.delete(rule)
        await db.commit()

        logger.info(f"Suppression rule {rule_id} deleted by user {user_id}")

        return True

    async def get_suppression_rules(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[SuppressionRule]:
        """
        Get suppression rules for a source.

        Args:
            db: Database session
            source_id: Source ID to filter by
            active_only: If True, only return active rules

        Returns:
            List of SuppressionRule objects
        """
        query = select(SuppressionRule).where(SuppressionRule.source_id == source_id)

        if active_only:
            query = query.where(SuppressionRule.is_active == True)  # noqa: E712

        query = query.order_by(SuppressionRule.created_at.desc())

        result = await db.execute(query)
        return list(result.scalars().all())

    # ==================== Suppression Rule Application ====================

    def apply_suppression_rules(
        self,
        rules: list[SuppressionRule],
        diff_data: dict,
    ) -> dict:
        """
        Apply suppression rules to filter out non-meaningful changes.

        Args:
            rules: List of active suppression rules
            diff_data: The diff data to filter

        Returns:
            Filtered diff data with suppressed changes removed
        """
        if not rules or not diff_data:
            return diff_data

        filtered_diff = diff_data.copy()
        changes = filtered_diff.get("changes", [])
        filtered_changes = []

        for change in changes:
            should_suppress = False

            for rule in rules:
                if self._matches_rule(rule, change):
                    should_suppress = True
                    logger.debug(
                        f"Change suppressed by rule {rule.id}: "
                        f"{rule.rule_description}"
                    )
                    break

            if not should_suppress:
                filtered_changes.append(change)

        filtered_diff["changes"] = filtered_changes
        filtered_diff["suppressed_count"] = len(changes) - len(filtered_changes)

        return filtered_diff

    def _matches_rule(self, rule: SuppressionRule, change: dict) -> bool:
        """Check if a change matches a suppression rule."""
        try:
            if rule.rule_type == SuppressionRuleType.FIELD_NAME:
                # Check if the changed field matches
                field_name = change.get("field", "")
                return field_name == rule.rule_pattern

            elif rule.rule_type == SuppressionRuleType.REGEX:
                # Check if any content matches the regex
                pattern = re.compile(rule.rule_pattern)
                old_value = str(change.get("old_value", ""))
                new_value = str(change.get("new_value", ""))
                return bool(pattern.search(old_value) or pattern.search(new_value))

            elif rule.rule_type == SuppressionRuleType.JSON_PATH:
                # Check if the JSON path matches
                path = change.get("path", "")
                return path.startswith(rule.rule_pattern)

            return False

        except Exception as e:
            logger.warning(f"Error applying suppression rule {rule.id}: {str(e)}")
            return False

    # ==================== Metrics ====================

    async def get_false_positive_metrics(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        period_days: int = 30,
    ) -> FalsePositiveMetrics:
        """
        Calculate false positive metrics for a source.

        Args:
            db: Database session
            source_id: Source ID to calculate metrics for
            period_days: Number of days to include in the calculation

        Returns:
            FalsePositiveMetrics with rates and counts
        """
        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None)
        from datetime import timedelta
        cutoff_date = cutoff_date - timedelta(days=period_days)

        # Get total changes for the source in the period
        total_changes_query = (
            select(func.count())
            .select_from(ChangeDiff)
            .join(DataRevision, ChangeDiff.new_revision_id == DataRevision.id)
            .where(DataRevision.source_id == source_id)
        )
        total_result = await db.execute(total_changes_query)
        total_changes = total_result.scalar() or 0

        # Get verified changes in the period
        verified_query = (
            select(func.count())
            .select_from(ChangeVerification)
            .join(ChangeDiff, ChangeVerification.change_diff_id == ChangeDiff.diff_id)
            .join(DataRevision, ChangeDiff.new_revision_id == DataRevision.id)
            .where(DataRevision.source_id == source_id)
            .where(ChangeVerification.created_at >= cutoff_date)
        )
        verified_result = await db.execute(verified_query)
        verified_changes = verified_result.scalar() or 0

        # Get false positives
        false_positives_query = (
            select(func.count())
            .select_from(ChangeVerification)
            .join(ChangeDiff, ChangeVerification.change_diff_id == ChangeDiff.diff_id)
            .join(DataRevision, ChangeDiff.new_revision_id == DataRevision.id)
            .where(DataRevision.source_id == source_id)
            .where(ChangeVerification.created_at >= cutoff_date)
            .where(ChangeVerification.is_false_positive == True)  # noqa: E712
        )
        fp_result = await db.execute(false_positives_query)
        false_positives = fp_result.scalar() or 0

        # Calculate rate
        false_positive_rate = 0.0
        if verified_changes > 0:
            false_positive_rate = (false_positives / verified_changes) * 100

        return FalsePositiveMetrics(
            source_id=source_id,
            total_changes=total_changes,
            verified_changes=verified_changes,
            false_positives=false_positives,
            false_positive_rate=round(false_positive_rate, 2),
            period_days=period_days,
        )
