import asyncio
import json
import logging
import os
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")


def build_llm_prompt(project_prompt: str, jurisdiction_prompt: str, extracted_text: str) -> str:
    """
    Combines project and jurisdiction prompts with extracted text
    """
    combined_prompt = f"{project_prompt}\n{jurisdiction_prompt}".strip()

    return f"""
You are an AI data extraction specialist that analyzes content and extracts structured information.

### CONTEXT & INSTRUCTIONS
{combined_prompt}

### TEXT TO ANALYZE
{extracted_text}

### OUTPUT REQUIREMENTS
You MUST return valid JSON with the following structure:

{{
  "summary": "Brief overall summary (2-3 sentences)",
  "markdown_summary": "Detailed markdown formatted analysis with headers, "
                      "bullet points, and emphasis for frontend display",
  "extracted_data": {{
    "key_value_pairs": {{
      "specific_field_1": "value_1",
      "specific_field_2": "value_2",
      "specific_field_3": "value_3"
    }}
  }},
  "confidence_score": 0.85
}}

### EXAMPLES OF KEY-VALUE PAIRS:

**For Price Monitoring:**
- "current_price": "650 NGN"
- "previous_price": "600 NGN" 
- "price_change_percentage": "8.3%"
- "effective_date": "2024-01-15"

**For Policy Updates:**
- "policy_name": "Environmental Compliance Act"
- "compliance_deadline": "2024-06-30"
- "penalty_amount": "5000000 NGN"
- "affected_industries": "Manufacturing, Energy"

**For Product Updates:**
- "product_version": "2.1.0"
- "release_date": "2024-01-20"
- "new_features": "Dashboard analytics, Export functionality"
- "system_requirements": "Python 3.8+"

**For Regulatory Changes:**
- "regulation_name": "Data Protection Act"
- "implementation_date": "2024-03-01"
- "required_actions": "Data audit, Privacy policy update"
- "applicable_to": "All businesses processing user data"

### CRITICAL RULES:
1. **extracted_data.key_value_pairs** MUST contain precise key-value pairs from the text
   - Keys should be specific, descriptive field names
   - Values should be exact figures, dates, or specific terms found in the text
   - Extract only information actually present in the text

2. **markdown_summary** must be properly formatted for frontend display:
   - Use ## Headers for sections
   - Use bullet points with - or *
   - Use **bold** for important terms
   - Use tables if relevant data comparisons exist

3. **confidence_score** must reflect how confident you are in the extraction (0.0-1.0)

4. Return ONLY valid JSON, no other text or explanations.
""".strip()


async def run_llm_analysis(llm_input: str) -> Dict[str, Any]:
    """
    Sends prompt to LLM and ensures JSON output matching orchestrator format.
    """
    await asyncio.sleep(0.5)

    headers = {
        "Content-Type": "application/json",
    }

    # Add API key to headers or payload based on provider
    if LLM_PROVIDER == "gemini":
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
        payload = {
            "model": LLM_MODEL,
            "prompt": llm_input,
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
        }
    else:
        # For other providers like OpenAI, Anthropic, etc.
        payload = {
            "model": LLM_MODEL,
            "prompt": llm_input,
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "1000")),
        }

    logger.info("Sending request to LLM...")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(LLM_API_URL, json=payload, headers=headers)

        response.raise_for_status()
        data = response.json()

        # Handle different response formats based on provider
        if LLM_PROVIDER == "gemini":
            raw_text = data.get("text", "")
        else:
            # For OpenAI: data["choices"][0]["text"]
            # For Anthropic: data["completion"]
            raw_text = (
                data.get("choices", [{}])[0].get("text", "")
                if "choices" in data
                else data.get("completion", "")
            )

        try:
            llm_result = json.loads(raw_text)

            # Validate and ensure required fields exist
            if "extracted_data" not in llm_result:
                llm_result["extracted_data"] = {}
            if not isinstance(llm_result.get("extracted_data", {}).get("key_value_pairs"), dict):
                llm_result["extracted_data"]["key_value_pairs"] = {}

            # Ensure all required fields are present (matching orchestrator)
            required_fields = ["summary", "markdown_summary", "extracted_data", "confidence_score"]
            for field in required_fields:
                if field not in llm_result:
                    if field == "markdown_summary":
                        llm_result[field] = llm_result.get("summary", "No summary available")
                    elif field == "confidence_score":
                        llm_result[field] = 0.0
                    elif field == "extracted_data":
                        llm_result[field] = {"key_value_pairs": {}}

            return llm_result

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}. Raw response: {raw_text}")
            return get_fallback_response("Invalid JSON response from LLM")

    except httpx.TimeoutException:
        logger.error("LLM request timed out after 60 seconds")
        return get_fallback_response("LLM request timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API returned error status: {e.response.status_code}")
        return get_fallback_response(f"LLM API error: {e.response.status_code}")
    except Exception as exc:
        logger.error(f"LLM request failed: {exc}", exc_info=True)
        return get_fallback_response("LLM service unavailable")


def get_fallback_response(reason: str = "Unknown error") -> Dict[str, Any]:
    """
    Returns a standardized fallback response when LLM fails.
    """
    return {
        "summary": f"Analysis unavailable: {reason}",
        "markdown_summary": f"## Analysis Unavailable\n\n"
        f"Unable to process the content at this time. Reason: {reason}",
        "extracted_data": {"key_value_pairs": {}},
        "confidence_score": 0.0,
    }
