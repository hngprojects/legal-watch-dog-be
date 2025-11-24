import logging
import os

from google import genai

logger = logging.getLogger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
SYSTEM_PROMPT = """
You are a helpful assistant for answering questions.
"""


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise ValueError("LLM_API_KEY not set in environment")
        self.client = genai.Client(api_key=self.api_key)
        logger.info("LLM client initialized successfully")

    def ask(self, user_message: str):
        try:
            response = self.client.models.generate_content(
                model=LLM_MODEL,
                contents=[user_message],
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
                    "max_output_tokens": int(os.getenv("LLM_MAX_TOKENS", "300")),
                },
            )
            if hasattr(response, "text"):
                return response.text.strip()
            elif hasattr(response, "candidates") and response.candidates:
                return response.candidates[0].content.parts[0].text.strip()
            else:
                return str(response)
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return f"Error: {e}"