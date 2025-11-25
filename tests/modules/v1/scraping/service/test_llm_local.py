import pytest

from app.api.modules.v1.scraping.service.llm_service import (
    build_llm_prompt,
    run_llm_analysis,
)


@pytest.mark.asyncio
async def test_llm_local_integration():
    fake_project_prompt = "Summarize regulatory updates for banking sector."
    fake_jurisdiction_prompt = "Focus on Nigerian financial policies."

    extracted_text = """
    The Central Bank of Nigeria released new guidelines for digital banks.
    Policies include stricter KYC and improved consumer protection.
    """

    # Correct signature → 3 arguments
    llm_input = build_llm_prompt(
        fake_project_prompt,
        fake_jurisdiction_prompt,
        extracted_text
    )

    print("\n=== LLM INPUT ===\n", llm_input)

    result = await run_llm_analysis(llm_input)

    print("\n=== LLM RESULT ===\n", result)

    assert isinstance(result, dict)
    assert "summary" in result
    assert "extracted_data" in result
    assert "confidence_score" in result
