import json
import logging
from typing import Any, Dict

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

if _HAS_GENAI and settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)


CHANGE_DETECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "has_changed": {"type": "boolean"},
        "change_summary": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
    },
    "required": ["has_changed", "change_summary", "risk_level"],
}


class DiffAIService:
    """
    Provides semantic change detection between old and new structured data using
    Gemini's Native JSON Mode. Ensures responses strictly conform to the required
    schema and fallbacks guarantee no silent failures.

    Raises:
        ImportError: If google-generativeai is not installed.
        ValueError: If GEMINI_API_KEY is not configured.
    """

    def __init__(self):
        """
        Initializes the DiffAIService by configuring the Gemini model with the
        correct schema-enforced JSON output.

        Raises:
            ImportError: If the Gemini SDK is unavailable.
            ValueError: If the GEMINI_API_KEY environment variable is missing.
        """
        if not _HAS_GENAI:
            raise ImportError("google-generativeai package is required for DiffAIService.")
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")

        self.model = genai.GenerativeModel(
            model_name=settings.MODEL_NAME,
            generation_config=GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=CHANGE_DETECTION_SCHEMA,
            ),
        )

    async def detect_semantic_change(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        monitoring_instruction: str,
        max_retries: int = 2,
    ) -> ChangeDetectionResult:
        """
        Compares old and new data structures and determines whether a meaningful,
        goal-relevant change has occurred. Performs deterministic AI analysis with
        JSON schema enforcement and safe fallbacks.

        Args:
            old_data (Dict[str, Any]):
                The previously stored structured data.
            new_data (Dict[str, Any]):
                The newly scraped or updated structured data.
            monitoring_instruction (str):
                A human-readable rule describing what type of changes matter.
            max_retries (int):
                Number of attempts allowed if the AI produces invalid JSON.

        Returns:
            ChangeDetectionResult:
                A validated result containing:
                    - has_changed (bool)
                    - change_summary (str)
                    - risk_level ("LOW" | "MEDIUM" | "HIGH")

        Raises:
            Exception:
                Surfaces unexpected errors only after generating a safe fallback
                response for the caller. All handled exceptions still return a
                valid ChangeDetectionResult to avoid breaking downstream systems.
        """

        old_json = json.dumps(old_data, sort_keys=True, default=str)
        new_json = json.dumps(new_data, sort_keys=True, default=str)

        if old_json == new_json:
            return ChangeDetectionResult(
                has_changed=False,
                change_summary="No changes (Exact Match)",
                risk_level="LOW",
            )

        if not old_data and new_data:
            return ChangeDetectionResult(
                has_changed=True,
                change_summary="Initial data extraction (New Record)",
                risk_level="LOW",
            )

        prompt = f"""
            You are a Regulatory Compliance Auditor.
            TASK: Compare OLD vs NEW data.
            USER GOAL: "{monitoring_instruction}"

            INSTRUCTIONS:
            1. Ignore formatting, whitespace, or metadata.
            2. Only report changes that affect the USER GOAL.
            3. Missing or null fields in both versions are not changes.
            4. risk_level must be LOW, MEDIUM, or HIGH.

            --- OLD DATA ---
            {old_json}

            --- NEW DATA ---
            {new_json}
            """

        for attempt in range(max_retries + 1):
            try:
                response = await self.model.generate_content_async(prompt)
                result_dict = json.loads(response.text)
                return ChangeDetectionResult.model_validate(result_dict)

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"AI parsing failure (Attempt {attempt + 1}): {e}")

                if attempt == max_retries:
                    logger.error("Max retries reached. Falling back to default high-risk result.")
                    return ChangeDetectionResult(
                        has_changed=True,
                        change_summary="AI Analysis Failed. Manual Review Required.",
                        risk_level="HIGH",
                    )

            except Exception as e:
                logger.error(f"Unexpected AI error: {e}")
                return ChangeDetectionResult(
                    has_changed=True,
                    change_summary=f"System Error: {str(e)}",
                    risk_level="HIGH",
                )
