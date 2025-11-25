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
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult

logger = logging.getLogger(__name__)

# Initialize GenAI
if _HAS_GENAI and settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

# Custom Exception as requested
class AIExtractionServiceError(Exception):
    """Raised when AI extraction fails after all retries."""
    pass

# Define the JSON Schema for Gemini
# FIX: Gemini requires strict properties for objects. 
# We use an ARRAY of key-value objects to handle dynamic keys.
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "markdown_summary": {"type": "string"},
        "extracted_data": {
            "type": "object",
            "properties": {
                "key_value_pairs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["key", "value"]
                    }
                }
            },
            "required": ["key_value_pairs"]
        },
        "confidence_score": {"type": "number"}
    },
    "required": ["summary", "markdown_summary", "extracted_data", "confidence_score"]
}

class AIExtractionService:
    """
    AI-powered service for extracting structured data from raw text.
    Uses Native JSON Mode for stability and single-pass efficiency.
    """

    def __init__(self):
        if not _HAS_GENAI:
            raise ImportError("`google-generativeai` package missing.")
        
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")

        # Configure model with JSON Mode
        self.model = genai.GenerativeModel(
            model_name=settings.LLM_MODEL,
            generation_config=GenerationConfig(
                temperature=0.0, # Deterministic
                response_mime_type="application/json",
                response_schema=EXTRACTION_SCHEMA
            ),
        )

    async def run_llm_analysis(
        self, 
        cleaned_text: str, 
        project_prompt: str, 
        jurisdiction_prompt: str,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Extracts data using Gemini Native JSON mode.
        Combines Extraction, Summary, and Markdown generation into ONE call.
        """
        
        # We explicitly inject the formatting rules you wanted into the single-pass prompt.
        prompt = f"""You are an Expert Regulatory Data Analyst.
TASK: Extract structured information from the text below and generate summaries based on that data.

PROJECT GOAL: {project_prompt}
JURISDICTION CONTEXT: {jurisdiction_prompt}

OUTPUT RULES (CRITICAL):
1. Return ONLY valid JSON matching the schema.
2. CONSISTENCY RULE: Use EXACT same field names/structure every time.

DATA EXTRACTION RULES:
- "extracted_data": Return a LIST of key-value objects (e.g. {{ "key": "current_price", "value": "600 NGN" }}).
- Keys MUST be snake_case. Use null if information is missing.

SUMMARY RULES (UI RENDER):
- "summary": A concise 2-3 sentence executive summary answering the Project Goal based on the extracted data.
- "markdown_summary": A detailed analysis formatted for Frontend Display.
    - Use ## Headers for sections.
    - Use bullet points (-) for lists.
    - Use **bold** for important figures (prices, dates).
    - Use Markdown Tables if comparing data (e.g., Old vs New prices).
    - MUST be based strictly on the 'extracted_data'.

--- SOURCE TEXT ---
{cleaned_text[:1000000]} 
""" 
        
        # This simplifies the architecture significantly while maintaining high accuracy.

        for attempt in range(max_retries + 1):
            try:
                # 1. Generate Content (Returns Valid JSON string)
                response = await self.model.generate_content_async(prompt)
                
                # 2. Parse JSON
                result_json = json.loads(response.text)
                
                # FIX: Transform the List[Obj] back to Dict for your Pydantic model
                if "extracted_data" in result_json and "key_value_pairs" in result_json["extracted_data"]:
                    kv_list = result_json["extracted_data"]["key_value_pairs"]
                    if isinstance(kv_list, list):
                        # Convert [{"key": "k", "value": "v"}] -> {"k": "v"}
                        result_json["extracted_data"]["key_value_pairs"] = {
                            item.get("key"): item.get("value") for item in kv_list if "key" in item
                        }

                # 3. Validate with Pydantic
                validated_result = ExtractionResult.model_validate(result_json)
                
                # Sort keys for deterministic output
                result_dump = validated_result.model_dump()
                if "extracted_data" in result_dump and "key_value_pairs" in result_dump["extracted_data"]:
                    kv_pairs = result_dump["extracted_data"]["key_value_pairs"]
                    result_dump["extracted_data"]["key_value_pairs"] = dict(sorted(kv_pairs.items()))

                logger.info(f"Extraction successful (Confidence: {validated_result.confidence_score})")
                return result_dump

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"AI Extraction Failed (Attempt {attempt+1}/{max_retries+1}): {e}")
                
                if attempt == max_retries:
                    error_msg = f"Extraction failed after {max_retries} retries. Error: {str(e)}"
                    logger.error(error_msg)
                    raise AIExtractionServiceError(error_msg)
            
            except Exception as e:
                logger.error(f"Unexpected AI Error: {e}")
                if attempt == max_retries:
                     raise AIExtractionServiceError(f"System Error: {str(e)}")