from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.modules.v1.scraping.models.data_revision_model import DataRevision
from app.api.modules.v1.scraping.service.change_detection_service import ChangeDetectionService


@pytest.mark.asyncio
async def test_create_revision_first_time():
    db = AsyncMock()

    # Properly mock execute -> scalars().first()
    fake_result = MagicMock()
    fake_result.scalars.return_value.first.return_value = None
    db.execute.return_value = fake_result

    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = ChangeDetectionService(db)

    ai_summary = {
        "summary": "A new update happened.",
        "changes_detected": "Initial scrape.",
        "risk_level": "Low",
        "key_points": ["Point A", "Point B"],
    }

    extracted_data = {"title": "Sample"}

    new_rev, diff = await service.create_revision_with_detection(
        source_id="SRC1",
        scraped_at=datetime.utcnow(),
        status="success",
        raw_content="Raw text here",
        minio_object_key="file.txt",
        extracted_data=extracted_data,
        ai_summary=ai_summary,
    )

    assert new_rev is not None
    assert new_rev.was_change_detected is True
    assert diff is None


@pytest.mark.asyncio
async def test_revision_with_change_detected():
    db = AsyncMock()

    previous_revision = DataRevision(
        revision_id="OLD1",
        source_id="SRC1",
        scraped_at=datetime.utcnow(),
        status="success",
        raw_content="Old raw content",
        extracted_data={"title": "Old"},
        minio_object_key="old.txt",
        ai_summary={
            "summary": "Old summary",
            "changes_detected": "None",
            "risk_level": "Low",
            "key_points": ["A"],
        },
        was_change_detected=False,
        created_at=datetime.utcnow(),
        deleted_at=None,
    )

    fake_result = MagicMock()
    fake_result.scalars.return_value.first.return_value = previous_revision
    db.execute.return_value = fake_result

    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = ChangeDetectionService(db)

    new_ai = {
        "summary": "Fees increased by 90% this week.",
        "changes_detected": "Fee changed from $100 to $190",
        "risk_level": "High",
        "key_points": ["Nigeria to Ghana", "$190 current", "$100 old"],
    }

    new_rev, diff = await service.create_revision_with_detection(
        source_id="SRC1",
        scraped_at=datetime.utcnow(),
        status="success",
        raw_content="Updated raw content",
        minio_object_key="new.txt",
        extracted_data={"title": "New"},
        ai_summary=new_ai,
    )

    assert new_rev.was_change_detected is True
    assert diff is not None
    assert diff.diff_patch["change_summary"]["total_changes"] >= 1


@pytest.mark.asyncio
async def test_revision_with_no_change():
    db = AsyncMock()

    previous_revision = DataRevision(
        revision_id="OLD1",
        source_id="SRC1",
        scraped_at=datetime.utcnow(),
        status="success",
        raw_content="Old raw content",
        extracted_data={"title": "Old"},
        minio_object_key="old.txt",
        ai_summary={
            "summary": "Same text",
            "changes_detected": "None",
            "risk_level": "Low",
            "key_points": ["A", "B"],
        },
        was_change_detected=False,
        created_at=datetime.utcnow(),
        deleted_at=None,
    )

    fake_result = MagicMock()
    fake_result.scalars.return_value.first.return_value = previous_revision
    db.execute.return_value = fake_result

    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = ChangeDetectionService(db)

    new_ai = {
        "summary": "Same text",
        "changes_detected": "None",
        "risk_level": "Low",
        "key_points": ["A", "B"],
    }

    new_rev, diff = await service.create_revision_with_detection(
        source_id="SRC1",
        scraped_at=datetime.utcnow(),
        status="success",
        raw_content="Old raw content",
        minio_object_key="same.txt",
        extracted_data={"title": "Old"},
        ai_summary=new_ai,
    )

    assert new_rev.was_change_detected is False
    assert diff is None
