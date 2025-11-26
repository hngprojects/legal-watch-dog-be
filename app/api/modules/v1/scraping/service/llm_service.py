import asyncio
import json
import logging
import random
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
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult

logger = logging.getLogger(__name__)

# Constants
_MAX_PROMPT_TEXT_CHARS = 1_000_000

if _HAS_GENAI and settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)


class AIExtractionServiceError(Exception):
    """Raised when AI extraction fails after all retries."""

    pass


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
                        "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                        "required": ["key", "value"],
                    },
                }
            },
            "required": ["key_value_pairs"],
        },
        "confidence_score": {"type": "number"},
    },
    "required": ["summary", "markdown_summary", "extracted_data", "confidence_score"],
}


class AIExtractionService:
    """
    Service responsible for extracting structured data from raw text using Google's Gemini AI.

    This service utilizes Gemini's Native JSON mode to ensure deterministic and schema-compliant
    output. It handles the extraction of key-value pairs, generation of summaries, and
    creation of markdown-formatted analysis in a single API call.
    """

    def __init__(self):
        """
        Initialize the AIExtractionService with the Gemini model configuration.

        Raises:
            ImportError: If the google-generativeai package is not installed.
            ValueError: If the GEMINI_API_KEY environment variable is not set.
        """
        if not _HAS_GENAI:
            raise ImportError("`google-generativeai` package missing.")

        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set.")

        self.model = genai.GenerativeModel(
            model_name=settings.MODEL_NAME,
            generation_config=GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=EXTRACTION_SCHEMA,
            ),
        )

    async def run_llm_analysis(
        self, cleaned_text: str, project_prompt: str, jurisdiction_prompt: str, max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Executes the LLM analysis pipeline to extract structured data from the provided text.

        Constructs a prompt based on the project and jurisdiction context, sends it to the
        configured Gemini model, and parses the JSON response. It includes logic to transform
        list-based key-value pairs into a dictionary and validates the result against the
        ExtractionResult schema.

        Args:
            cleaned_text (str): The pre-processed text content to analyze.
            project_prompt (str): The main goal or monitoring instruction.
            jurisdiction_prompt (str): Context specific to the jurisdiction.
            max_retries (int, optional): Max retries for failed API calls.
                                         Defaults to 2.

        Returns:
            Dict[str, Any]: A dictionary with extracted data, summaries,
                            and confidence score, validated and formatted.

        Raises:
            AIExtractionServiceError: If extraction fails after the specified number of retries.
        """
        prompt = f"""You are an Expert Regulatory Data Analyst.
TASK: Extract structured information from the text below and generate summaries based on that data.

PROJECT GOAL: {project_prompt}
JURISDICTION CONTEXT: {jurisdiction_prompt}

OUTPUT RULES (CRITICAL):
1. Return ONLY valid JSON matching the schema.
2. CONSISTENCY RULE: Use EXACT same field names/structure every time.

DATA EXTRACTION RULES:
- "extracted_data": Return a LIST of key-value objects 
  (e.g. {{ "key": "current_price", "value": "600 NGN" }}).
- Keys MUST be snake_case. Use null if information is missing.

SUMMARY RULES (UI RENDER):
- "summary": A concise 2-3 sentence executive summary 
  answering the Project Goal based on extracted data.
- "markdown_summary": A detailed analysis formatted for Frontend Display.
    - Use ## Headers for sections.
    - Use bullet points (-) for lists.
    - Use **bold** for important figures (prices, dates).
    - Use Markdown Tables if comparing data (e.g., Old vs New prices).
    - MUST be based strictly on the 'extracted_data'.

--- SOURCE TEXT ---
{cleaned_text[:_MAX_PROMPT_TEXT_CHARS]} 
"""

        for attempt in range(max_retries + 1):
            try:
                response = await self.model.generate_content_async(prompt)

                result_json = json.loads(response.text)

                if (
                    "extracted_data" in result_json
                    and "key_value_pairs" in result_json["extracted_data"]
                ):
                    kv_list = result_json["extracted_data"]["key_value_pairs"]
                    if isinstance(kv_list, list):
                        result_json["extracted_data"]["key_value_pairs"] = {
                            item.get("key"): item.get("value") for item in kv_list if "key" in item
                        }

                validated_result = ExtractionResult.model_validate(result_json)

                result_dump = validated_result.model_dump()
                if (
                    "extracted_data" in result_dump
                    and "key_value_pairs" in result_dump["extracted_data"]
                ):
                    kv_pairs = result_dump["extracted_data"]["key_value_pairs"]
                    result_dump["extracted_data"]["key_value_pairs"] = dict(
                        sorted(kv_pairs.items())
                    )

                logger.info(
                    f"Extraction successful (Confidence: {validated_result.confidence_score})"
                )
                return result_dump

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    f"AI Extraction Failed (Attempt {attempt + 1}/{max_retries + 1}): {e}"
                )

                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2 ** attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter
                    
                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    error_msg = f"Extraction failed after {max_retries} retries. Error: {str(e)}"
                    logger.error(error_msg)
                    raise AIExtractionServiceError(error_msg)

            except Exception as e:
                logger.error(f"Unexpected AI Error: {e}")
                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2 ** attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter
                    
                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    raise AIExtractionServiceError(f"System Error: {str(e)}")