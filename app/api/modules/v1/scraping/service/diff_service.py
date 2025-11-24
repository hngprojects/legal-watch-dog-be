import json
from typing import Dict, Any
from app.api.core.config import settings
from app.api.modules.v1.scraping.schemas.ai_analysis import ChangeDetectionResult
from logging import getLogger
try:
    import google.generativeai as genai
    _HAS_GENAI = True
except ImportError:
    genai = None
    _HAS_GENAI = False

logger = getLogger(__name__)

class DiffAIService:
    """
    Responsible ONLY for semantically comparing two datasets.
    """
    def __init__(self):
        if not _HAS_GENAI:
            raise Exception(
                "Missing optional dependency: `google-generativeai` package is not installed. Run `pip install google-generativeai` to enable AI diff operations."
            )
        if not settings.GOOGLE_API_KEY:
            raise Exception(
                "GOOGLE_API_KEY not configured. Set GOOGLE_API_KEY in environment variables."
            )
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        # Use deterministic settings: temperature=0 for reproducibility
        self.model = genai.GenerativeModel(
            settings.LLM_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.0,  # Deterministic: always same response for same input
                top_p=1.0,
                top_k=1
            )
        )

    async def detect_semantic_change(
        self, 
        old_data: Dict[str, Any], 
        new_data: Dict[str, Any],
        context: str,
        max_retries: int = 2
    ) -> ChangeDetectionResult:
        
        # Build a clear, concise prompt that forces JSON output
        prompt = f"""TASK: Compare two datasets and return ONLY a JSON object.

OLD: {json.dumps(old_data, default=str)}
NEW: {json.dumps(new_data, default=str)}

CONTEXT: {context}

INSTRUCTIONS:
- Detect ONLY factual changes (prices, dates, requirements)
- Ignore formatting or phrasing
- Do NOT write any explanation
- Do NOT write any text before or after JSON
- Return ONLY this exact JSON format:

{{"has_changed": boolean, "change_summary": "one sentence", "risk_level": "LOW|MEDIUM|HIGH"}}

NOW OUTPUT ONLY THE JSON OBJECT:"""
        
        for attempt in range(max_retries + 1):
            try:
                response = await self.model.generate_content_async(prompt)
                raw = response.text.strip()
                
                # Extract JSON if wrapped in backticks
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.strip()
                
                # Try to find JSON object if there's extra text
                if "{" in raw and "}" in raw:
                    start = raw.index("{")
                    end = raw.rindex("}") + 1
                    raw = raw[start:end]
                
                # Validate and parse
                result = ChangeDetectionResult.model_validate_json(raw)
                logger.info(f"Semantic diff successful on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                logger.warning(f"Diff attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                logger.debug(f"Raw response was: {response.text[:200]}")
                
                if attempt == max_retries:
                    logger.error(f"Diff service exhausted retries. Using fallback.")
                    # Fallback: Return safe defaults
                    return ChangeDetectionResult(
                        has_changed=True, 
                        change_summary="Unable to determine. Manual review required.",
                        risk_level="MEDIUM"
                    )