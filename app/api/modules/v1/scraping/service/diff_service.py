import json
import logging
from typing import Dict, Tuple

import google.generativeai as genai

from app.api.core.config import settings
from app.api.modules.v1.scraping.models.diff_response_model import DiffResult

# Configure the SDK once
genai.configure(api_key=settings.GEMINI_API_KEY)
logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash"

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
    def __init__(self):
        # We initialize the model with the schema to enforce structure
        self.model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config={
                **GENERATION_CONFIG,
                "response_schema": DIFFRESULT_SCHEMA,
            },
        )

    async def compute_diff(self, old_data: Dict, new_data: Dict, context: str) -> Tuple[bool, Dict]:
        """
        Compares old and new data using Gemini 1.5 Flash.
        Returns: (was_change_detected, diff_patch_dict)
        """

        # 1. Pre-computation: If identical strings, skip AI to save quota
        if json.dumps(old_data, sort_keys=True) == json.dumps(new_data, sort_keys=True):
            return False, {"change_summary": "No changes (Exact Match)"}

        # 2. Handle Cold Start (First time scraping)
        if not old_data and new_data:
            return True, {
                "change_summary": "Initial data extraction (New Record)",
                "change_type": "New Record",
                "confidence_score": 1.0,
            }

        # 3. Construct the Prompt
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
            # 4. Call Gemini (Async)
            response = await self.model.generate_content_async(prompt)

            # 5. Parse using the Pydantic model implicitly
            # Gemini returns JSON because we set response_mime_type="application/json"
            # and response_schema=DiffResult
            result_json = json.loads(response.text)

            # Validate with Pydantic locally to be safe
            parsed_result = DiffResult(**result_json)

            # 6. Format return value
            diff_patch = {
                "change_summary": parsed_result.change_summary,
                "change_type": parsed_result.change_type,
                "raw_diff": result_json,
            }

            return parsed_result.detected, diff_patch

        except Exception as e:
            logger.error(f"AI Diff Service Error: {e}")
            # Fail safe: Assume change happened so humans can review
            return True, {"change_summary": f"Error during AI check: {str(e)}"}
