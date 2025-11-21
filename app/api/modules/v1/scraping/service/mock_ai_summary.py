# services/mock_ai_service.py
import random


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
        "Environmental compliance requires monthly emission reports."
    ]
    
    @staticmethod
    def generate_summary(raw_content: str) -> str:
        """
        Mock function that returns a random AI summary.
        In production, this will call the actual AI service.
        """
        # For testing: return random summary
        return random.choice(MockAIService.MOCK_SUMMARIES)
    
    @staticmethod
    def generate_fixed_summary(raw_content: str, version: int = 1) -> str:
        """
        For controlled testing: return predictable summaries.
        """
        return f"Summary version {version}: {raw_content[:50]}..."