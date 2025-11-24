import google.generativeai as genai
import json
from typing import Type, Dict, Any
from pydantic import BaseModel, ValidationError
from app.api.core.config import settings
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult
from logging import getLogger

logger = getLogger(__name__)

# Configure Gemini
try:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
except Exception as e:
    logger.error(f"Failed to configure Gemini AI: {e}")

class AIExtractionServiceError(Exception):
    pass

class AIExtractionService:
    """
    Responsible ONLY for extracting structured data from raw text.
    """
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def _construct_system_prompt(self, project_prompt: str, jurisdiction_prompt: str, schema: Type[BaseModel]) -> str:
        schema_json = schema.model_json_schema()
        return f"""
        ROLE: You are an expert Regulatory Data Extractor.
        
        --- OBJECTIVE ---
        Extract precise factual data from the input text based strictly on the USER PROMPTS below.
        
        --- USER PROMPTS ---
        1. MAIN GOAL: {project_prompt}
        2. CONTEXT/FILTERS: {jurisdiction_prompt}
        
        --- CRITICAL OUTPUT RULES ---
        1. Return ONLY a valid JSON object matching this schema:
        {json.dumps(schema_json, indent=2)}
        2. KEY NAMING CONVENTION: snake_case keys derived from facts found.
        3. CONFIDENCE SCORING: 0.0 to 1.0 based on explicit presence in text.
        """

    async def generate_structured_data(
        self, 
        cleaned_text: str, 
        project_prompt: str, 
        jurisdiction_prompt: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        
        full_prompt = self._construct_system_prompt(project_prompt, jurisdiction_prompt, ExtractionResult)
        
        history = [
            {"role": "user", "parts": [f"System Instructions:\n{full_prompt}\n\n--- SOURCE TEXT ---\n{cleaned_text}"]}
        ]

        chat = self.model.start_chat(history=[])
        
        for attempt in range(max_retries + 1):
            try:
                if attempt == 0:
                    response = await chat.send_message_async(history[0]['parts'][0])
                else:
                    pass 
                
                raw_content = response.text.replace("```json", "").replace("```", "").strip()
                validated_data = ExtractionResult.model_validate_json(raw_content)
                return validated_data.model_dump()

            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Extraction Validation Failed (Attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise AIExtractionServiceError(f"Extraction failed: {e}")
                
                response = await chat.send_message_async(f"Error: {str(e)}. Fix JSON and retry.")

        raise AIExtractionServiceError("Retry loop failed")