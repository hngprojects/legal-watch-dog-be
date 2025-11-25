import json
import logging
from typing import Dict, Any, Optional

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    _HAS_GENAI = True
except ImportError:
    genai = None
    _HAS_GENAI = False

from pydantic import ValidationError
from app.api.core.config import settings
from app.api.modules.v1.scraping.schemas.ai_analysis import ChangeDetectionResult

logger = logging.getLogger(__name__)

# Initialize outside to avoid re-auth on every request
if _HAS_GENAI and settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

# SCHEMA NOTE:
# While we could use ChangeDetectionResult.model_json_schema(), 
# defining a simplified schema manually is often safer for Gemini 
# to avoid it getting confused by Pydantic-specific metadata (like 'title' or '$defs').
CHANGE_DETECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "has_changed": {"type": "boolean"},
        "change_summary": {"type": "string"},
        "risk_level": {
            "type": "string",
            "enum": ["LOW", "MEDIUM", "HIGH"]
        },
    },
    "required": ["has_changed", "change_summary", "risk_level"],
}

class DiffAIService:
    """
    AI-powered service for detecting semantic differences.
    Uses Native JSON Mode for 100% schema compliance.
    """

    def __init__(self):
        if not _HAS_GENAI:
            raise ImportError("`google-generativeai` package missing. Install it to use AI Diff.")
        
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")

        self.model = genai.GenerativeModel(
            model_name=settings.LLM_MODEL, 
            generation_config=GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=CHANGE_DETECTION_SCHEMA
            ),
        )

    async def detect_semantic_change(
        self, 
        old_data: Dict[str, Any], 
        new_data: Dict[str, Any], 
        monitoring_instruction: str, 
        max_retries: int = 2
    ) -> ChangeDetectionResult:
        
        # 1. Fast Path: Exact Match
        # BACKEND TIP: Use default=str to handle datetime objects from DB without crashing
        old_json = json.dumps(old_data, sort_keys=True, default=str)
        new_json = json.dumps(new_data, sort_keys=True, default=str)

        if old_json == new_json:
            return ChangeDetectionResult(
                has_changed=False,
                change_summary="No changes (Exact Match)",
                risk_level="LOW"
            )

        # 2. Fast Path: New Record
        if not old_data and new_data:
            return ChangeDetectionResult(
                has_changed=True,
                change_summary="Initial data extraction (New Record)",
                risk_level="LOW" 
            )

        # 3. AI Analysis
        prompt = f"""You are a Regulatory Compliance Auditor.
TASK: Compare OLD vs NEW data. 
USER GOAL: "{monitoring_instruction}"

INSTRUCTIONS:
1. Ignore formatting, whitespace, or metadata (timestamps).
2. If a change does NOT impact the USER GOAL, output has_changed=false.
3. If extracted data is missing or null in both, it is NOT a change.
4. risk_level must be LOW, MEDIUM, or HIGH.

--- OLD DATA ---
{old_json}

--- NEW DATA ---
{new_json}
"""

        for attempt in range(max_retries + 1):
            try:
                # Gemini Native JSON Mode returns valid JSON matching the schema
                response = await self.model.generate_content_async(prompt)
                
                # Parse JSON
                result_dict = json.loads(response.text)
                
                # PYDANTIC TIP: Use model_validate for robust type checking
                return ChangeDetectionResult.model_validate(result_dict)

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"AI Diff Parsing Failed (Attempt {attempt+1}): {e}")
                
                if attempt == max_retries:
                    # Fail Safe: If AI fails, assume change to prevent missing alerts
                    logger.error("Diff Service exhausted retries. Defaulting to has_changed=True.")
                    return ChangeDetectionResult(
                        has_changed=True,
                        change_summary="AI Analysis Failed. Manual Review Required.",
                        risk_level="HIGH"
                    )
            except Exception as e:
                logger.error(f"Unexpected AI Error: {e}")
                return ChangeDetectionResult(
                    has_changed=True,
                    change_summary=f"System Error: {str(e)}",
                    risk_level="HIGH"
                )