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
You are an AI assistant helping an organization analyze updates from scraped sources.

### TASK INSTRUCTIONS
Use the following instructions (from project and jurisdiction setup):

[INSTRUCTIONS START]
{combined_prompt}
[INSTRUCTIONS END]

Scraped text to analyze:

[EXTRACTED TEXT START]
{extracted_text}
[EXTRACTED TEXT END]

### OUTPUT FORMAT (STRICT JSON ONLY)
Respond ONLY with valid JSON in the following format:

{{
  "summary": "string",
  "extracted_data": {{
    "key_findings": "string",
    "changes_detected": "string",
    "risk_level": "Low | Medium | High",
    "recommendation": "string"
  }},
  "confidence_score": 0.85
}}

### RULES
- Only return JSON, no extra commentary.
- Fill all fields.
- confidence_score should be between 0.0 and 1.0
""".strip()


async def run_llm_analysis(llm_input: str) -> Dict[str, Any]:
    """
    Sends prompt to LLM and ensures JSON output.
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
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
        }
    else:
        # For other providers like OpenAI, Anthropic, etc.
        payload = {
            "model": LLM_MODEL,
            "prompt": llm_input,
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "300")),
        }

    logger.info("Sending request to LLM...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
            return json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON. Returning fallback.")
            return {
                "summary": "Could not parse summary",
                "extracted_data": {
                    "key_findings": "",
                    "changes_detected": "",
                    "risk_level": "Low",
                    "recommendation": "",
                },
                "confidence_score": 0.0,
            }

    except Exception as exc:
        logger.error(f"LLM request failed: {exc}", exc_info=True)
        return {
            "summary": "LLM processing failed",
            "extracted_data": {
                "key_findings": "",
                "changes_detected": "",
                "risk_level": "Low",
                "recommendation": "",
            },
            "confidence_score": 0.0,
        }
