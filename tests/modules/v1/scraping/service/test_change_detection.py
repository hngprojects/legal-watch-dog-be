import json
from unittest.mock import AsyncMock, patch

import pytest

# Note: The service and model imports are based on your provided file paths.
from app.api.modules.v1.scraping.service.diff_service import DiffAIService

# --- MOCK RESPONSE HELPER CLASS ---


class MockGeminiResponse:
    """Mock object to simulate the response returned by generate_content_async.
    It must have a .text attribute containing the JSON string."""

    def __init__(self, data: dict):
        # The service expects a 'response.text' attribute containing the JSON string
        self.text = json.dumps(data)


# --- FIXTURES (Setup and Mocks) ---


@pytest.fixture
def diff_service():
    """Provides a fresh DiffAIService instance for each test.
    We patch the GenerativeModel class instantiation to avoid hitting the
    real API key or configuration during setup."""
    # Patch the GenerativeModel constructor to prevent actual initialization
    # and allow us to mock its methods on the instance later.
    with patch(
        "app.api.modules.v1.scraping"
        ".service.diff_service."
          "genai.GenerativeModel"
    ):
        service = DiffAIService()
        yield service


@pytest.fixture
def test_context():
    """Fixture for a common context string."""
    return "Monitor product pricing and stock status."


# --- HELPER FOR MOCK DATA ---


def create_mock_llm_result(
    detected: bool, summary: str, score: float, change_type: str
) -> dict:
    """Helper to create the dictionary that the service expects from the LLM."""
    return {
        "detected": detected,
        "change_summary": summary,
        "confidence_score": score,
        "change_type": change_type,
    }


# --- TESTS ---


@pytest.mark.asyncio
async def test_exact_match_no_api_call(diff_service, test_context):
    """Test 1: Identical data should fast-fail without calling the LLM."""
    data = {"product": "A", "price": 10}

    # We patch the *actual* method called by the service (model.generate_content_async)
    # and confirm it is NOT called.
    with patch.object(diff_service.model, "generate_content_async") as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(
            data, data, test_context
        )

        assert was_changed is False
        assert patch_data["change_summary"] == "No changes (Exact Match)"
        mock_llm_call.assert_not_called()


@pytest.mark.asyncio
async def test_cold_start_new_record(diff_service, test_context):
    """Test 2: Cold start path (old_data is empty) should bypass the LLM and set correct output."""
    old_data = {}
    new_data = {"product": "B", "price": 50}

    # We patch the *actual* method called by the service (model.generate_content_async)
    # and confirm it is NOT called.
    with patch.object(diff_service.model, "generate_content_async") as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(
            old_data, new_data, test_context
        )

        assert was_changed is True
        # Assertions now match the logic found in DiffAIService's compute_diff method
        assert "Initial data extraction (New Record)" == patch_data["change_summary"]
        assert patch_data["change_type"] == "New Record"
        mock_llm_call.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_price_change(diff_service, test_context):
    """Test 3: Relevant change detected by mocking a positive LLM response."""
    old_data = {"id": 1, "price": 100.00, "description": "old desc"}
    new_data = {"id": 1, "price": 110.00, "description": "old desc"}

    # Mock the AI's structured result
    mock_result = create_mock_llm_result(
        detected=True,
        summary="Price increased from 100.00 to 110.00.",
        score=0.95,
        change_type="Price Update",
    )
    mock_response = MockGeminiResponse(mock_result)

    # Patch the *actual* method called by the service: diff_service.model.generate_content_async
    with patch.object(
        diff_service.model,
        "generate_content_async",
        new=AsyncMock(return_value=mock_response),
    ) as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(
            old_data, new_data, test_context
        )

        assert was_changed is True
        assert patch_data["change_type"] == "Price Update"
        assert "100.00 to 110.00" in patch_data["change_summary"]
        mock_llm_call.assert_called_once()


@pytest.mark.asyncio
async def test_noise_ignored_timestamp(diff_service, test_context):
    """Test 4: Irrelevant change (like timestamp)
    should be ignored by mocking a negative LLM response."""
    old_data = {"id": 2, "stock": 50, "last_updated": "2025-11-23T00:00:00"}
    new_data = {"id": 2, "stock": 50, "last_updated": "2025-11-24T12:00:00"}

    # Mock the AI's structured result
    mock_result = create_mock_llm_result(
        detected=False,
        summary="Only metadata (timestamp) changed, which is not relevant.",
        score=1.0,
        change_type="Cosmetic",
    )
    mock_response = MockGeminiResponse(mock_result)

    # Patch the *actual* method called by the service: diff_service.model.generate_content_async
    with patch.object(
        diff_service.model,
        "generate_content_async",
        new=AsyncMock(return_value=mock_response),
    ) as mock_llm_call:
        was_changed, patch_data = await diff_service.compute_diff(
            old_data, new_data, test_context
        )

        assert was_changed is False
        assert patch_data["change_type"] == "Cosmetic"
        assert "not relevant" in patch_data["change_summary"]
        mock_llm_call.assert_called_once()
