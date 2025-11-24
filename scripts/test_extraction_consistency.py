"""
Test extraction consistency: Run same URL twice and compare results.
Tests if the extracted data is deterministic and suitable for diffing.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import hashlib

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api.modules.v1.scraping.service.ai_extraction_service import AIExtractionService
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult
from app.api.utils.text_cleaner import clean_html_content
from app.api.modules.v1.scraping.service.playwright_service import PlaywrightService


async def test_extraction_consistency():
    """
    Test if running extraction twice on the same URL produces consistent results.
    This validates if diff operations will work reliably.
    """
    print("=" * 80)
    print("EXTRACTION CONSISTENCY TEST")
    print("=" * 80)
    print()

    # Configuration
    source_url = "https://www.gov.uk/national-minimum-wage-rates"
    project_prompt = "Extract the current National Minimum Wage and National Living Wage rates per hour. Group the rates by age category (e.g., '21 and over', '18 to 20'). Identify the 'Effective Date' for these rates."
    jurisdiction_prompt = "Context: HM Revenue & Customs (HMRC) official rates for the UK."

    print(f"URL: {source_url}")
    print(f"Project Prompt: {project_prompt[:60]}...")
    print(f"Jurisdiction: {jurisdiction_prompt}")
    print()
    print("-" * 80)
    print()

    # Initialize services
    print("[INFO] Initializing services...")
    extraction_service = AIExtractionService()
    playwright_service = PlaywrightService()
    print("[OK] Services initialized")
    print()

    # Fetch and clean once
    print("[INFO] Fetching content from GOV.UK (shared for both extractions)...")
    try:
        html_bytes = await playwright_service.scrape(source_url, creds={})
        html_content = html_bytes.decode('utf-8') if isinstance(html_bytes, bytes) else html_bytes
        print(f"[OK] Fetched {len(html_content)} characters")

        html_bytes_for_clean = html_content.encode('utf-8') if isinstance(html_content, str) else html_content
        cleaned_text = clean_html_content(html_bytes_for_clean)
        print(f"[OK] Cleaned to {len(cleaned_text)} characters")
        
        # Calculate content hash
        content_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()
        print(f"[OK] Content hash: {content_hash[:16]}...")
    except Exception as e:
        print(f"[FAIL] Fetch/clean failed: {e}")
        return False

    print()
    print("-" * 80)
    print()

    # ===== EXTRACTION 1 =====
    print("[RUN 1] First extraction...")
    try:
        result1 = await extraction_service.generate_structured_data(
            cleaned_text=cleaned_text,
            project_prompt=project_prompt,
            jurisdiction_prompt=jurisdiction_prompt,
            max_retries=3,
        )
        print("[OK] Extraction 1 successful")
        print(f"    Fields: {len(result1['extracted_data'])}")
        print(f"    Confidence: {result1['confidence_score']}")
    except Exception as e:
        print(f"[FAIL] Extraction 1 failed: {e}")
        return False

    print()
    print("-" * 80)
    print()

    # ===== EXTRACTION 2 =====
    print("[RUN 2] Second extraction (same content, fresh LLM call)...")
    try:
        result2 = await extraction_service.generate_structured_data(
            cleaned_text=cleaned_text,
            project_prompt=project_prompt,
            jurisdiction_prompt=jurisdiction_prompt,
            max_retries=3,
        )
        print("[OK] Extraction 2 successful")
        print(f"    Fields: {len(result2['extracted_data'])}")
        print(f"    Confidence: {result2['confidence_score']}")
    except Exception as e:
        print(f"[FAIL] Extraction 2 failed: {e}")
        return False

    print()
    print("-" * 80)
    print()

    # ===== COMPARISON =====
    print("[ANALYSIS] Comparing extractions...")
    print()

    # Extract the data dictionaries
    data1 = result1['extracted_data']
    data2 = result2['extracted_data']

    # 1. Check if keys are identical
    keys1 = set(data1.keys())
    keys2 = set(data2.keys())
    
    print(f"[1] KEY CONSISTENCY:")
    if keys1 == keys2:
        print(f"    [OK] Keys are identical ({len(keys1)} fields)")
    else:
        print(f"    [FAIL] Keys differ!")
        print(f"      Run 1 keys: {sorted(keys1)}")
        print(f"      Run 2 keys: {sorted(keys2)}")
        print(f"      Only in Run 1: {keys1 - keys2}")
        print(f"      Only in Run 2: {keys2 - keys1}")
    
    print()
    print(f"[2] VALUE CONSISTENCY (per key):")
    
    perfect_match = 0
    partial_match = 0
    mismatch = 0
    
    for key in keys1 | keys2:
        val1 = data1.get(key, "MISSING")
        val2 = data2.get(key, "MISSING")
        
        if val1 == val2:
            print(f"    [OK] {key}: {val1}")
            perfect_match += 1
        else:
            # Try numeric comparison (for floating point tolerance)
            try:
                v1_float = float(val1) if isinstance(val1, (int, float, str)) else None
                v2_float = float(val2) if isinstance(val2, (int, float, str)) else None
                if v1_float is not None and v2_float is not None:
                    if abs(v1_float - v2_float) < 0.01:  # 0.01 tolerance
                        print(f"    [~] {key}: {val1} vs {val2} (numeric tolerance)")
                        partial_match += 1
                    else:
                        print(f"    [XX] {key}: {val1} vs {val2} (numeric diff: {abs(v1_float - v2_float)})")
                        mismatch += 1
                else:
                    print(f"    [XX] {key}: '{val1}' vs '{val2}'")
                    mismatch += 1
            except (ValueError, TypeError):
                print(f"    [XX] {key}: '{val1}' vs '{val2}'")
                mismatch += 1
    
    print()
    print(f"[3] MATCH SUMMARY:")
    print(f"    Perfect matches: {perfect_match}/{len(keys1 | keys2)}")
    print(f"    Partial matches: {partial_match}/{len(keys1 | keys2)}")
    print(f"    Mismatches: {mismatch}/{len(keys1 | keys2)}")
    
    consistency_score = (perfect_match + partial_match) / (len(keys1 | keys2)) if (keys1 | keys2) else 0
    print(f"    Consistency Score: {consistency_score:.1%}")
    
    print()
    print(f"[4] CONFIDENCE SCORES:")
    print(f"    Run 1: {result1['confidence_score']}")
    print(f"    Run 2: {result2['confidence_score']}")
    print(f"    Match: {'[OK]' if result1['confidence_score'] == result2['confidence_score'] else '[XX]'}")
    
    print()
    print(f"[5] SUMMARY CONSISTENCY:")
    summary1_hash = hashlib.sha256(result1['summary'].encode()).hexdigest()[:8]
    summary2_hash = hashlib.sha256(result2['summary'].encode()).hexdigest()[:8]
    print(f"    Run 1 summary hash: {summary1_hash}")
    print(f"    Run 2 summary hash: {summary2_hash}")
    print(f"    Match: {'[OK]' if summary1_hash == summary2_hash else '[XX]'}")
    
    print()
    print("-" * 80)
    print()

    # ===== VERDICT =====
    print("[VERDICT]")
    print()
    
    if consistency_score >= 0.95:
        print("[OK] HIGHLY CONSISTENT - Suitable for diffing")
        print("  The extracted data is deterministic enough for reliable change detection.")
    elif consistency_score >= 0.80:
        print("[~] MOSTLY CONSISTENT - Acceptable for diffing with caveats")
        print("  Minor variations exist but would not significantly impact diff operations.")
    else:
        print("[XX] INCONSISTENT - Not reliable for diffing")
        print("  The extracted data varies too much between runs.")
    
    print()
    print(f"Consistency Score: {consistency_score:.1%}")
    print(f"Test completed at: {datetime.now().isoformat()}")
    print()

    return consistency_score >= 0.80


async def main():
    """Run the consistency test."""
    success = await test_extraction_consistency()

    print("=" * 80)
    if success:
        print("[SUCCESS] Extraction is consistent enough for diffing!")
        print("=" * 80)
        return 0
    else:
        print("[FAILURE] Extraction consistency is too low for reliable diffing.")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
