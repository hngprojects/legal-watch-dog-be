import asyncio
import json
import logging
import os
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def build_gemini_prompt(final_prompt: str, extracted_text: str) -> str:
    """
    Combines the project+jurisdiction prompt with extracted text
    inside a structured gemini instruction template.
    """

    return f"""
You are an AI assistant helping an organization analyze updates from scraped sources.

### TASK INSTRUCTIONS
Use the following instructions (from project and jurisdiction setup):

[INSTRUCTIONS START]
{final_prompt}
[INSTRUCTIONS END]

Scraped text to analyze:

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
- Only return JSON, no extra commentary.
- Fill all fields.
""".strip()


async def run_gemini_analysis(gemini_input: str) -> Dict[str, Any]:
    """
    Sends prompt to Gemini and ensures JSON output.
    """
    await asyncio.sleep(0.5)

<<<<<<< HEAD
    headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}

<<<<<<< HEAD
    payload = {"model": GEMINI_MODEL, "prompt": llm_input, "temperature": 0.2}
=======
=======
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json",
    }
>>>>>>> 627fc92 (chore: reformat code to pass CI checks)

    payload = {"model": GEMINI_MODEL, "prompt": gemini_input, "temperature": 0.2}
>>>>>>> ee5e5a6 (feat(prompt_service & processing_pipeline): include project master prompt in jurisdiction)

    logger.info("Sending request to Gemini...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GEMINI_API_URL, json=payload, headers=headers)

        response.raise_for_status()
        data = response.json()
        raw_text = data.get("text", "")

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("Gemini returned invalid JSON. Returning fallback.")
            return {
                "summary": "Could not parse summary",
                "changes_detected": "",
                "risk_level": "Low",
                "recommendation": "",
            }

    except Exception as exc:
        logger.error(f"Gemini request failed: {exc}", exc_info=True)
        return {
            "summary": "Gemini processing failed",
            "changes_detected": "",
            "risk_level": "Low",
            "recommendation": "",
        }
