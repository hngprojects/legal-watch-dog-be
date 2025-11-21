# services/mock_ai_service.py
import hashlib


class MockAIService:
    """
    Temporary mock service to simulate AI summary generation.
    Replace this with real AI service later.
    """
    
    MOCK_SUMMARIES = [
        "Regulation requires annual compliance reporting by March 31st.",
        "New tax rate of 15% applies to all digital services.",
        "Updated safety standards mandate quarterly inspections.",
        "License renewal must be completed 30 days before expiration.",
        # "Environmental compliance requires monthly emission reports."
    ]
    
    @staticmethod
    def generate_summary(raw_content: str) -> str:
        # Create a hash of the raw content
        content_hash = hashlib.md5(raw_content.encode("utf-8")).hexdigest()
        # Return a summary based on content hash (deterministic)
        return f"Summary: {raw_content[:50]}... [hash:{content_hash[:8]}]"
    
    @staticmethod
    def generate_fixed_summary(raw_content: str, version: int = 1) -> str:
        """
        For controlled testing: return predictable summaries.
        """
        return f"Summary version {version}: {raw_content[:50]}..."