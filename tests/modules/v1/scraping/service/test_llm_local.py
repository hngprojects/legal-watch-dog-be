from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.modules.v1.scraping.service.llm_service import (
    AIExtractionService,
    AIExtractionServiceError,
)


@pytest.mark.asyncio
async def test_llm_local_integration():
    """Test LLM service integration with mock data and validate response structure."""
    fake_project_prompt = "Summarize regulatory updates for banking sector."
    fake_jurisdiction_prompt = "Focus on Nigerian financial policies."
    extracted_text = """
    The Central Bank of Nigeria released new guidelines for digital banks.
    Policies include stricter KYC and improved consumer protection.
    """

    service = AIExtractionService()
    
    service.model = Mock()
    mock_response = Mock()
    mock_response.text = '''
    {
        "summary": "The Central Bank of Nigeria has introduced new guidelines for digital 
        banks focusing on enhanced KYC requirements and consumer protection measures.",
        "markdown_summary": "## Regulatory Update Summary\\n\\n### Key Changes:\\n- 
        **Stricter KYC requirements** for digital banking\\n- **Enhanced consumer 
        protection** measures\\n- 
        **New guidelines** for digital bank operations\\n\\n### Impact:\\nThese changes 
        aim to strengthen the digital 
        banking sector while ensuring customer security.",
        "extracted_data": {
            "key_value_pairs": [
                {"key": "regulator", "value": "Central Bank of Nigeria"},
                {"key": "sector", "value": "digital banking"},
                {"key": "kyc_requirements", "value": "stricter"},
                {"key": "consumer_protection", "value": "enhanced"}
            ]
        },
        "confidence_score": 0.85
    }
    '''
    
    service.model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await service.run_llm_analysis(
        cleaned_text=extracted_text,
        project_prompt=fake_project_prompt,
        jurisdiction_prompt=fake_jurisdiction_prompt,
        max_retries=0
    )

    print("\n=== LLM RESULT ===\n", result)

    assert isinstance(result, dict)
    assert "summary" in result
    assert "markdown_summary" in result
    assert "extracted_data" in result
    assert "confidence_score" in result
    assert isinstance(result["confidence_score"], float)
    assert 0.0 <= result["confidence_score"] <= 1.0


@pytest.mark.asyncio
async def test_llm_service_error_handling():
    """Test LLM service error handling."""
    service = AIExtractionService()
    service.model = Mock()
    service.model.generate_content_async = AsyncMock(
        side_effect=Exception("API Error")
    )

    with pytest.raises(AIExtractionServiceError):
        await service.run_llm_analysis(
            cleaned_text="Test content",
            project_prompt="Test project",
            jurisdiction_prompt="Test jurisdiction",
            max_retries=1
        )


@pytest.mark.asyncio
async def test_llm_service_json_parsing():
    """Test LLM service JSON parsing and transformation."""
    service = AIExtractionService()
    service.model = Mock()
    mock_response = Mock()
    mock_response.text = '''
    {
        "summary": "Test summary",
        "markdown_summary": "## Test Markdown",
        "extracted_data": {
            "key_value_pairs": [
                {"key": "test_key_1", "value": "value_1"},
                {"key": "test_key_2", "value": "value_2"}
            ]
        },
        "confidence_score": 0.9
    }
    '''
    
    service.model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await service.run_llm_analysis(
        cleaned_text="Test content",
        project_prompt="Test project",
        jurisdiction_prompt="Test jurisdiction"
    )

    assert isinstance(result["extracted_data"]["key_value_pairs"], dict)
    assert "test_key_1" in result["extracted_data"]["key_value_pairs"]
    assert result["extracted_data"]["key_value_pairs"]["test_key_1"] == "value_1"


@pytest.mark.asyncio
async def test_llm_service_initialization():
    """Test LLM service initialization with missing dependencies."""
    with patch('app.api.modules.v1.scraping.service.llm_service._HAS_GENAI', False):
        with pytest.raises(ImportError):
            AIExtractionService()
    
    with patch('app.api.modules.v1.scraping.service.llm_service.settings.GEMINI_API_KEY', None):
        with patch('app.api.modules.v1.scraping.service.llm_service._HAS_GENAI', True):
            with pytest.raises(ValueError):
                AIExtractionService()


@pytest.mark.asyncio
async def test_llm_service_retry_logic():
    """Test LLM service retry logic."""
    service = AIExtractionService()
    service.model = Mock()
    
    service.model.generate_content_async = AsyncMock(
        side_effect=[
            Exception("First failure"),
            Exception("Second failure"),
            Mock(text='''{
                "summary": "Success after retry",
                "markdown_summary": "## Success",
                "extracted_data": {"key_value_pairs": []},
                "confidence_score": 0.8
            }''')
        ]
    )

    result = await service.run_llm_analysis(
        cleaned_text="Test content",
        project_prompt="Test project",
        jurisdiction_prompt="Test jurisdiction",
        max_retries=2
    )

    assert result["summary"] == "Success after retry"
    assert service.model.generate_content_async.call_count == 3
