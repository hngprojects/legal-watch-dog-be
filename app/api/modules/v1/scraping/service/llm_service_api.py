import asyncio
import json
import logging
import os
import re

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Service")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
)

LLM_COOLDOWN = 0.5


class LLMRequest(BaseModel):
    content: str
    project_id: str
    jurisdiction_id: str


def extract_json_from_text(text: str) -> dict:
    """Extract JSON from text response, even if it's wrapped in other text"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    return None


@app.post("/run-llm")
async def run_llm(request: LLMRequest):
    """
    Receives extracted content and sends to Gemini LLM
    """
    llm_input = f"""
You are a legal analysis AI. Analyze the following content and return ONLY valid JSON.

CONTENT TO ANALYZE:
{request.content}

Return STRICT JSON with this exact structure - no other text:
{{
  "summary": "Brief summary of the content",
  "key_points": "List the main points",
  "changes_detected": "Describe any changes or new information",
  "risk_level": "Low",
  "recommendation": "Suggested actions"
}}

Project: {request.project_id}
Jurisdiction: {request.jurisdiction_id}

IMPORTANT: Return ONLY the JSON object, no additional text, no markdown, no code blocks.
"""

    await asyncio.sleep(LLM_COOLDOWN)

    headers = {
        "Content-Type": "application/json",
    }

    payload = {
        "contents": [{"parts": [{"text": llm_input}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000},
    }

    try:
        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

        logger.info("Sending request to Gemini API")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        response.raise_for_status()
        data = response.json()

        if "candidates" in data and len(data["candidates"]) > 0:
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            logger.info(f"Raw LLM response: {raw_text}")
        else:
            logger.error("No candidates in response")
            raise HTTPException(status_code=500, detail="No response from Gemini")

        result = extract_json_from_text(raw_text)

        if result is None:
            logger.warning(f"Could not parse JSON from response, using fallback. Raw: {raw_text}")

            result = {
                "summary": raw_text[:200] + "..." if len(raw_text) > 200 else raw_text,
                "key_points": "Analysis completed",
                "changes_detected": "Content analyzed",
                "risk_level": "Medium",
                "recommendation": "Review the full analysis",
            }

        required_fields = [
            "summary",
            "key_points",
            "changes_detected",
            "risk_level",
            "recommendation",
        ]

        for field in required_fields:
            if field not in result:
                result[field] = "Not specified"

        result.update(
            {
                "project_id": request.project_id,
                "jurisdiction_id": request.jurisdiction_id,
            }
        )

        logger.info(f"Final result: {result}")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail=f"Gemini API error: {e.response.status_code}")
    except Exception as exc:
        logger.error(f"LLM request failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="LLM processing failed")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": GEMINI_MODEL}
