import asyncio
import json
import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Service")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("MODEL_NAME", "gemini-2.0-flash")
GEMINI_API_URL = os.getenv("LLM_API_URL", "https://api.fake-gemini.com/v1/generate")


LLM_COOLDOWN = 0.5  

class LLMRequest(BaseModel):
    content: str                
    project_id: str
    jurisdiction_id: str        

@app.post("/run-llm")
async def run_llm(request: LLMRequest):
    """
    Receives extracted content (any domain), sends to Gemini LLM,
    and returns comparison-ready structured response.
    """

    llm_input = f"""
You are a highly analytical LLM generating insights for an automated monitoring platform.

PROJECT ID: {request.project_id}
JURISDICTION / SOURCE ID: {request.jurisdiction_id}

CONTENT TO ANALYZE:
{request.content}

Return STRICT JSON with the following structure:
{{
  "summary": "Short human-readable summary of the content",
  "key_points": "Important points extracted",
  (
    "… typical prior versions of similar content — "
    "if unsure, respond with 'Not enough data'"
),

  "risk_level": "Low | Medium | High — based on severity or importance",
  "recommendation": "Recommended action or next steps"
}}
"""

    await asyncio.sleep(LLM_COOLDOWN)

    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GEMINI_MODEL,
        "prompt": llm_input,
        "temperature": 0.2,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GEMINI_API_URL, json=payload, headers=headers)

        response.raise_for_status()
        raw_text = response.json().get("text", "")

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON")
            result = {
                "summary": "Could not parse summary",
                "key_points": "",
                "changes_detected": "",
                "risk_level": "Low",
                "recommendation": "",
            }

       
        result.update({
            "project_id": request.project_id,
            "jurisdiction_id": request.jurisdiction_id,
            "content": request.content,
        })

        return result

    except Exception as exc:
        logger.error(f"LLM request failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="LLM processing failed")
