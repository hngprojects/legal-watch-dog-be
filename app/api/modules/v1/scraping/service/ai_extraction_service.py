import json
from typing import Dict, Any
from pydantic import BaseModel, ValidationError
from app.api.core.config import settings
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult
from logging import getLogger

try:
    import google.generativeai as genai
    _HAS_GENAI = True
except ImportError:
    genai = None
    _HAS_GENAI = False

logger = getLogger(__name__)

class AIExtractionServiceError(Exception):
    pass

class AIExtractionService:
    """
    Responsible ONLY for extracting structured data from raw text.
    """
    def __init__(self):
        if not _HAS_GENAI:
            raise Exception(
                "Missing optional dependency: `google-generativeai` package is not installed. Run `pip install google-generativeai` to enable AI extraction operations."
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
                temperature=0.0,
                top_p=1.0,
                top_k=1
            )
        )

    def _construct_system_prompt(self, project_prompt: str, jurisdiction_prompt: str) -> str:
        """
        Construct the initial extraction prompt for structured data extraction.
        
        Args:
            project_prompt (str): The main goal/context for extraction.
            jurisdiction_prompt (str): Jurisdiction-specific instructions and context.
        
        Returns:
            str: The system prompt for the LLM.
        """
        # Use the actual schema from ExtractionResult
        schema_json = ExtractionResult.model_json_schema()
        
        return f"""You are an expert Regulatory Data Extractor. Your ONLY job is to return valid JSON.

EXTRACT DATA FROM THE TEXT BASED ON:
MAIN GOAL: {project_prompt}
CONTEXT: {jurisdiction_prompt}

OUTPUT RULES (CRITICAL):
1. Return ONLY valid JSON - NO markdown, NO explanation, NO extra text
2. You must return an object with: summary, confidence_score (0.0-1.0), extracted_data
3. CONSISTENCY RULE: Use EXACT same field names and structure every time you extract
4. extracted_data keys: snake_case, derived from facts in the text
5. confidence_score: How confident you are (0.0=guessing, 1.0=explicit in text)
6. markdown_summary will be generated after extraction; leave it empty initially
7. If information is missing, use null values
8. DO NOT add extra fields beyond what is explicitly asked for
9. DO NOT vary field naming between runs (e.g., always use consistent naming like "rate_2025" not "2025_rate")

SCHEMA DEFINITION:
{json.dumps(schema_json, indent=2)}

DETERMINISM INSTRUCTIONS:
- Temperature is set to 0.0, so you MUST be completely deterministic
- The same input text must ALWAYS produce the IDENTICAL extracted_data structure
- Same field names, same key order, same value format every single time
- This is critical for change detection algorithms

RETURN YOUR JSON RESPONSE NOW (NO EXPLANATION):"""

    def _construct_summary_prompt(self, project_prompt: str, extracted_data: Dict[str, Any]) -> str:
        """
        Construct a prompt to generate a human-readable summary from extracted data.
        
        Args:
            project_prompt (str): The main goal/context for extraction.
            extracted_data (Dict[str, Any]): The structured data extracted from the source.
        
        Returns:
            str: A prompt instructing the LLM to generate a concise summary.
        
        Examples:
            >>> service = AIExtractionService()
            >>> data = {"visa_fee": "90 EUR", "processing_time": "10 days"}
            >>> prompt = service._construct_summary_prompt("Extract visa fees", data)
        """
        data_str = json.dumps(extracted_data, indent=2)
        return f"""Based on the following extracted data, generate a concise 1-2 sentence summary that answers: {project_prompt}

EXTRACTED DATA:
{data_str}

SUMMARY (1-2 sentences, factual, clear):"""

    def _construct_markdown_summary_prompt(self, extracted_data: Dict[str, Any]) -> str:
        """
        Construct a prompt to generate a markdown-formatted summary with extracted data.
        
        Args:
            extracted_data (Dict[str, Any]): The structured data extracted from the source.
        
        Returns:
            str: A prompt instructing the LLM to generate markdown-formatted output.
        
        Examples:
            >>> service = AIExtractionService()
            >>> data = {"visa_fee": "90 EUR", "processing_time": "10 days"}
            >>> prompt = service._construct_markdown_summary_prompt(data)
        """
        data_str = json.dumps(extracted_data, indent=2)
        return f"""Generate a well-formatted markdown summary of the following extracted data. Use markdown formatting with headers, bold, lists, or tables to present the information clearly.

EXTRACTED DATA:
{data_str}

MARKDOWN SUMMARY (use markdown formatting, no code blocks):"""

    async def generate_structured_data(
        self, 
        cleaned_text: str, 
        project_prompt: str, 
        jurisdiction_prompt: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Extract structured data from cleaned text and generate a contextual summary.
        
        This method performs two-stage extraction:
        1. Extract structured data from source text using LLM
        2. Generate a human-readable summary from the extracted data
        
        Args:
            cleaned_text (str): The preprocessed source text (HTML cleaned, etc.).
            project_prompt (str): The extraction goal (e.g., "Extract visa fees").
            jurisdiction_prompt (str): The context/jurisdiction instructions.
            max_retries (int, optional): Number of retry attempts on validation failure. Defaults to 3.
        
        Returns:
            Dict[str, Any]: A dictionary with keys:
                - summary (str): Human-readable summary incorporating extracted data
                - confidence_score (float): 0.0-1.0 confidence in extraction
                - extracted_data (Dict): Structured key-value pairs extracted
        
        Raises:
            AIExtractionServiceError: If extraction fails after all retries.
        
        Examples:
            >>> service = AIExtractionService()
            >>> result = await service.generate_structured_data(
            ...     cleaned_text="Short-stay visa costs 90 EUR...",
            ...     project_prompt="Extract visa fees",
            ...     jurisdiction_prompt="Context: France Schengen visa"
            ... )
            >>> print(result["summary"])
            "Short-stay Schengen visa to France costs 90 EUR for adults."
        """
        
        system_prompt = self._construct_system_prompt(project_prompt, jurisdiction_prompt)
        
        # First message with system prompt + source text
        initial_message = f"{system_prompt}\n\n--- SOURCE TEXT ---\n{cleaned_text}"
        
        for attempt in range(max_retries + 1):
            try:
                # Stage 1: Extract structured data
                response = await self.model.generate_content_async(initial_message)
                raw_content = response.text.strip()
                
                # Clean up markdown if present
                if "```" in raw_content:
                    raw_content = raw_content.replace("```json", "").replace("```", "").strip()
                
                # Validate JSON structure
                validated_data = ExtractionResult.model_validate_json(raw_content)
                
                # Sort extracted_data keys for deterministic output
                result = validated_data.model_dump()
                if isinstance(result.get('extracted_data'), dict):
                    result['extracted_data'] = dict(sorted(result['extracted_data'].items()))
                
                logger.info(f"Extraction successful on attempt {attempt + 1}")
                
                # Stage 2: Generate contextual summary from extracted data
                summary_prompt = self._construct_summary_prompt(project_prompt, result['extracted_data'])
                summary_response = await self.model.generate_content_async(summary_prompt)
                result['summary'] = summary_response.text.strip()
                
                logger.info("Summary generation successful")
                
                # Stage 3: Generate markdown-formatted summary
                markdown_prompt = self._construct_markdown_summary_prompt(result['extracted_data'])
                markdown_response = await self.model.generate_content_async(markdown_prompt)
                result['markdown_summary'] = markdown_response.text.strip()
                
                logger.info("Markdown summary generation successful")
                return result

            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Extraction Validation Failed (Attempt {attempt + 1}/{max_retries + 1}): {e}")
                
                if attempt == max_retries:
                    raise AIExtractionServiceError(
                        f"Extraction failed after {max_retries + 1} attempts: {str(e)}. "
                        f"LLM response was not valid JSON."
                    )
                
                # Retry with corrective prompt
                retry_prompt = (
                    f"You returned invalid JSON. Error: {str(e)}\n\n"
                    f"RETRY: Return ONLY a valid JSON object matching this schema: "
                    f"{json.dumps(ExtractionResult.model_json_schema(), indent=2)}\n\n"
                    f"Source text: {cleaned_text[:500]}..."
                )
                initial_message = retry_prompt

        raise AIExtractionServiceError("Extraction retry loop exhausted")