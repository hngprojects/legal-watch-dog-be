import json
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


GEMINI_API_URL = "https://api.fake-gemini.com/v1/generate"
GEMINI_API_KEY = "YOUR_GEMINI_KEY"  


def build_llm_prompt(final_prompt: str, extracted_text: str) -> str:
    """
    Combines the project+jursidiction prompt with extracted text
    inside a structured LLM instruction template.
    """
    return f"""
You are an AI assistant helping an organization analyze regulatory, policy, and data updates.

### TASK INSTRUCTIONS
Using the following instructions (provided by the organization):

[INSTRUCTIONS START]
{final_prompt}
[INSTRUCTIONS END]

And the extracted text from the scraper:

[EXTRACTED TEXT START]
{extracted_text}
[EXTRACTED TEXT END]

### OUTPUT FORMAT (STRICT JSON ONLY)
Respond ONLY with valid JSON in the following format:

{{
  "summary": "string",
  "changes_detected": "string",
  "risk_level": "Low | Medium | High",
  "recommendation": "string"
}}

### RULES
- Do NOT output anything except JSON.
- Do NOT include commentary.
- Do NOT break the JSON format.
- Fill ALL fields.
    """.strip()


async def run_llm_analysis(llm_input: str) -> Dict[str, Any]:
    """
    Sends prompt to Gemini (placeholder) and ensures JSON output.
    """
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gemini-1.5-flash", 
        "prompt": llm_input,
        "temperature": 0.2
    }

    logger.info("Sending request to LLM...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GEMINI_API_URL, json=payload, headers=headers)

        response.raise_for_status()
        data = response.json()

       
        raw_text = data.get("text", "")

       
        try:
            result = json.loads(raw_text)
            return result
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON. Returning fallback.")
            return {
                "summary": "Could not parse summary",
                "changes_detected": "",
                "risk_level": "Low",
                "recommendation": ""
            }

    except Exception as exc:
        logger.error(f"LLM request failed: {exc}", exc_info=True)
        return {
            "summary": "LLM processing failed",
            "changes_detected": "",
            "risk_level": "Low",
            "recommendation": ""
        }
