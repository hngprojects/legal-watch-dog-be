import json
import logging
from typing import Dict, Tuple

import google.generativeai as genai

from app.api.core.config import settings
from app.api.modules.v1.scraping.schemas.diff_response import DiffResult

# Configure the SDK once
genai.configure(api_key=settings.GEMINI_API_KEY)
logger = logging.getLogger(__name__)


GENERATION_CONFIG = {
    "temperature": 0.0,
    "response_mime_type": "application/json",
}

DIFFRESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "detected": {"type": "boolean"},
        "change_summary": {"type": "string"},
        "confidence_score": {"type": "number"},
        "change_type": {"type": "string"},
    },
    "required": ["detected", "change_summary", "confidence_score"],
}


class DiffAIService:
    """
    AI-powered service for detecting semantic differences between data snapshots.

    Uses Google's Gemini model to intelligently compare old and new data,
    identifying material changes while ignoring irrelevant modifications like
    formatting, timestamps, or metadata updates.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL_NAME,
            generation_config={
                **GENERATION_CONFIG,
                "response_schema": DIFFRESULT_SCHEMA,
            },
        )

    async def compute_diff(self, old_data: Dict, new_data: Dict, context: str) -> Tuple[bool, Dict]:
        """
        Compare old and new data to detect meaningful changes.

        Args:
            old_data: Previous data snapshot as dictionary
            new_data: Current data snapshot as dictionary
            context: Business context describing what changes matter

        Returns:
            Tuple containing:
                - bool: True if meaningful change detected, False otherwise
                - Dict: Change details including summary, type, and raw diff
        """
        if json.dumps(old_data, sort_keys=True) == json.dumps(new_data, sort_keys=True):
            return False, {"change_summary": "No changes (Exact Match)"}

        if not old_data and new_data:
            return True, {
                "change_summary": "Initial data extraction (New Record)",
                "change_type": "New Record",
                "confidence_score": 1.0,
            }

        prompt = f"""
            You are a **Semantic Data Auditor**. Compare the 'Old Data' and 'New Data'
            JSON objects below.
            Determine if a **MATERIAL change** occurred relevant
            to the 'Context / Project Goal'.

            RULES:
            - Ignore whitespace, formatting, key ordering, or 
            scraping metadata (timestamps) unless relevant.
            - Focus only on meaningful changes that impact the
            User's Goal provided in the context.
            - Output **must be valid JSON wrapped in a
            Markdown code block** as shown below.
            - Do NOT include any text outside the JSON code block.

            CONTEXT / PROJECT GOAL:
            {context}

            --- OLD DATA ---
            {json.dumps(old_data, indent=2)} 

            --- NEW DATA ---
            {json.dumps(new_data, indent=2)}

            EXPECTED OUTPUT FORMAT:

            ```json
            {{
            "detected": true,
            "change_summary": "A concise, human-readable summary of changes",
            "confidence_score": 0.0
            }}
            """

        try:
            response = await self.model.generate_content_async(prompt)
            result_json = json.loads(response.text)
            parsed_result = DiffResult(**result_json)

            diff_patch = {
                "change_summary": parsed_result.change_summary,
                "change_type": parsed_result.change_type,
                "raw_diff": result_json,
            }

            return parsed_result.detected, diff_patch

        except Exception as e:
            logger.error(f"AI Diff Service Error: {e}")
            return True, {"change_summary": f"Error during AI check: {str(e)}"}
