import google.generativeai as genai
import json
from typing import Dict, Any
from app.api.core.config import settings
from app.api.modules.v1.scraping.schemas.ai_analysis import ChangeDetectionResult
from logging import getLogger

logger = getLogger(__name__)

class DiffAIService:
    """
    Responsible ONLY for semantically comparing two datasets.
    """
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def detect_semantic_change(
        self, 
        old_data: Dict[str, Any], 
        new_data: Dict[str, Any],
        context: str
    ) -> ChangeDetectionResult:
        
        prompt = f"""
        ROLE: You are a Senior Regulatory Compliance Auditor.
        
        --- TASK ---
        Compare OLD DATA vs NEW DATA. Determine if there is a MATERIAL FACTUAL CHANGE.
        
        --- CONTEXT ---
        {context}
        
        --- DATA ---
        OLD DATA: {json.dumps(old_data, default=str)}
        NEW DATA: {json.dumps(new_data, default=str)}
        
        --- RULES ---
        1. Ignore formatting, key reordering, or minor phrasing.
        2. Flag changes in: Prices, Limits, Dates, Requirements, Statuses.
        3. If one dataset is empty and other is not, that IS a change.
        
        --- OUTPUT ---
        Return strictly valid JSON matching this schema:
        {json.dumps(ChangeDetectionResult.model_json_schema(), indent=2)}
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            raw = response.text.replace("```json", "").replace("```", "").strip()
            return ChangeDetectionResult.model_validate_json(raw)
            
        except Exception as e:
            logger.error(f"AI Diff Failed: {e}")
            return ChangeDetectionResult(
                has_changed=True, 
                change_summary=f"Manual Review Required. AI Diff Error: {str(e)}",
                risk_level="LOW"
            )