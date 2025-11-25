import json
from unittest.mock import AsyncMock, patch

import pytest

from app.api.modules.v1.scraping.service.diff_service import DiffAIService


class MockGeminiResponse:
    """Mock object to simulate the response returned by generate_content_async."""

    def __init__(self, data: dict):
        self.text = json.dumps(data)


@pytest.fixture
def diff_service():
    """Provides a fresh DiffAIService instance for each test."""
    with patch("app.api.modules.v1.scraping.service.diff_service.genai.GenerativeModel"):
        service = DiffAIService()
        yield service


@pytest.fixture
def test_context():
    """Fixture for a common context string."""
    return "Monitor product pricing and stock status."


def create_mock_llm_result(detected: bool, summary: str, score: float, change_type: str) -> dict:
    """Helper to create the dictionary that the service expects from the LLM."""
    return {
        "detected": detected,
        "change_summary": summary,
        "confidence_score": score,
        "change_type": change_type,
    }


@pytest.mark.asyncio
async def test_exact_match_no_api_call(diff_service, test_context):
    """Test 1: Identical data should fast-fail without calling the LLM."""
    data = {"product": "A", "price": 10}

    with patch.object(diff_service.model, "generate_content_async") as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(data, data, test_context)

        assert was_changed is False
        assert patch_data["change_summary"] == "No changes (Exact Match)"
        mock_llm_call.assert_not_called()


@pytest.mark.asyncio
async def test_cold_start_new_record(diff_service, test_context):
    """Test 2: Cold start path (old_data is empty) should bypass the LLM."""
    old_data = {}
    new_data = {"product": "B", "price": 50}

    with patch.object(diff_service.model, "generate_content_async") as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(old_data, new_data, test_context)

        assert was_changed is True
        assert "Initial data extraction (New Record)" == patch_data["change_summary"]
        assert patch_data["change_type"] == "New Record"
        mock_llm_call.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_price_change(diff_service, test_context):
    """Test 3: Relevant change detected by mocking a positive LLM response."""
    old_data = {"id": 1, "price": 100.00, "description": "old desc"}
    new_data = {"id": 1, "price": 110.00, "description": "old desc"}

    mock_result = create_mock_llm_result(
        detected=True,
        summary="Price increased from 100.00 to 110.00.",
        score=0.95,
        change_type="Price Update",
    )
    mock_response = MockGeminiResponse(mock_result)

    with patch.object(
        diff_service.model,
        "generate_content_async",
        new=AsyncMock(return_value=mock_response),
    ) as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(old_data, new_data, test_context)

        assert was_changed is True
        assert patch_data["change_type"] == "Price Update"
        assert "100.00 to 110.00" in patch_data["change_summary"]
        mock_llm_call.assert_called_once()


@pytest.mark.asyncio
async def test_noise_ignored_timestamp(diff_service, test_context):
    """Test 4: Irrelevant change should be ignored."""
    old_data = {"id": 2, "stock": 50, "last_updated": "2025-11-23T00:00:00"}
    new_data = {"id": 2, "stock": 50, "last_updated": "2025-11-24T12:00:00"}

    mock_result = create_mock_llm_result(
        detected=False,
        summary="Only metadata (timestamp) changed, which is not relevant.",
        score=1.0,
        change_type="Cosmetic",
    )
    mock_response = MockGeminiResponse(mock_result)

    with patch.object(
        diff_service.model,
        "generate_content_async",
        new=AsyncMock(return_value=mock_response),
    ) as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(old_data, new_data, test_context)

        assert was_changed is False
        assert patch_data["change_type"] == "Cosmetic"
        assert "not relevant" in patch_data["change_summary"]
        mock_llm_call.assert_called_once()
