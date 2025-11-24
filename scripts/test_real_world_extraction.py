"""
Real-world integration test: UK Minimum Wage Compliance Monitoring
Tests extraction from actual GOV.UK website with exact prompts provided.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api.modules.v1.scraping.service.ai_extraction_service import AIExtractionService
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult
from pydantic import ValidationError


async def test_real_world_extraction():
    """
    Test extraction from real GOV.UK minimum wage rates page.
    Uses exact prompts as provided by user.
    """
    print("=" * 80)
    print("REAL-WORLD INTEGRATION TEST: UK MINIMUM WAGE COMPLIANCE")
    print("=" * 80)
    print()

    # Exact configuration as provided
    source_url = "https://www.gov.uk/national-minimum-wage-rates"
    project_prompt = "Extract the current National Minimum Wage and National Living Wage rates per hour. Group the rates by age category (e.g., '21 and over', '18 to 20'). Identify the 'Effective Date' for these rates."
    jurisdiction_prompt = "Context: HM Revenue & Customs (HMRC) official rates for the UK."

    print(f"URL: {source_url}")
    print(f"Project Prompt: {project_prompt}")
    print(f"Jurisdiction: {jurisdiction_prompt}")
    print()
    print("-" * 80)
    print()

    try:
        # Initialize services
        print("[INFO] Initializing services...")
        extraction_service = AIExtractionService()
        print("[OK] Services initialized")
        print()

        # Step 1: Fetch content
        print("[INFO] Step 1: Fetching content from GOV.UK...")
        try:
            from app.api.modules.v1.scraping.service.playwright_service import PlaywrightService
            playwright_service = PlaywrightService()
            html_content = await playwright_service.fetch_page_content(source_url)
            print(f"[OK] Fetched content ({len(html_content)} characters)")
        except Exception as e:
            print(f"[WARNING] Playwright failed: {e}")
            print("[INFO] Attempting with requests library...")
            try:
                import requests
                response = requests.get(source_url, timeout=10)
                html_content = response.text
                print(f"[OK] Fetched content with requests ({len(html_content)} characters)")
            except Exception as e2:
                print(f"[FAIL] Both methods failed: {e2}")
                return False

        # Step 2: Clean HTML to text
        print()
        print("[INFO] Step 2: Cleaning HTML to plain text...")
        try:
            from app.api.utils.text_cleaner import clean_html_content
            cleaned_text = clean_html_content(html_content)
            
            print(f"[OK] Cleaned text ({len(cleaned_text)} characters)")
            print()
            print("Sample of cleaned text (first 500 chars):")
            print("-" * 40)
            print(cleaned_text[:500])
            print("-" * 40)
        except Exception as e:
            print(f"[FAIL] Text cleaning failed: {e}")
            return False

        # Step 3: Extract structured data
        print()
        print("[INFO] Step 3: Extracting structured data with AI...")
        try:
            result = await extraction_service.generate_structured_data(
                cleaned_text=cleaned_text,
                project_prompt=project_prompt,
                jurisdiction_prompt=jurisdiction_prompt,
                max_retries=3,
            )
            print("[OK] Extraction successful!")
        except Exception as e:
            print(f"[FAIL] Extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Step 4: Validate result
        print()
        print("[INFO] Step 4: Validating extraction result...")
        print()

        # Check fields
        required_fields = ["summary", "confidence_score", "extracted_data", "markdown_summary"]
        for field in required_fields:
            if field in result:
                print(f"[OK] {field}: present")
            else:
                print(f"[FAIL] {field}: missing")
                return False

        # Validate confidence
        if 0.0 <= result["confidence_score"] <= 1.0:
            print(f"[OK] confidence_score: {result['confidence_score']}")
        else:
            print(f"[FAIL] confidence_score out of range: {result['confidence_score']}")
            return False

        # Validate extracted_data
        if isinstance(result["extracted_data"], dict):
            print(f"[OK] extracted_data: dict with {len(result['extracted_data'])} fields")
            for key, value in result["extracted_data"].items():
                print(f"    - {key}: {value}")
        else:
            print(f"[FAIL] extracted_data: not a dict")
            return False

        # Validate schema
        print()
        print("[INFO] Step 5: Validating against ExtractionResult schema...")
        try:
            validated = ExtractionResult(**result)
            print("[OK] Schema validation passed")
        except ValidationError as ve:
            print(f"[FAIL] Schema validation failed:")
            for error in ve.errors():
                print(f"    - {error}")
            return False

        # Display results
        print()
        print("-" * 80)
        print("EXTRACTION RESULTS")
        print("-" * 80)
        print()
        print("SUMMARY:")
        print(result["summary"])
        print()
        print("MARKDOWN SUMMARY:")
        print(result["markdown_summary"])
        print()
        print("EXTRACTED DATA (JSON):")
        print(json.dumps(result["extracted_data"], indent=2))
        print()

        # Timestamp
        print(f"Test completed at: {datetime.now().isoformat()}")
        print()

        return True

    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run the real-world test."""
    success = await test_real_world_extraction()

    print("=" * 80)
    if success:
        print("[SUCCESS] Real-world extraction test passed!")
        print("=" * 80)
        return 0
    else:
        print("[FAILURE] Real-world extraction test failed.")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
