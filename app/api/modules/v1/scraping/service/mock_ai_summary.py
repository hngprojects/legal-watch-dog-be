import hashlib
import random
from datetime import datetime


class MockAIService:
    """
    Mock service to generate AI JSON summaries
    for testing the JSON change-detection pipeline.
    """

    MOCK_DATA_POINTS = [
        {
            "summary": "The cost to send money from Nigeria to Ghana has increased this week.",
            "key_points": [
                "Transfer direction: Nigeria → Ghana",
                "Current price: $190 USD (was $100 last week)",
                "Rate includes all fees",
                "Provider: Western Union official rate",
            ],
            "changes_detected": "Price increased due to exchange rate volatility.",
            "risk_level": "High",
            "recommendation": "Notify users immediately.",
        },
        {
            "summary": "A new policy requires all businesses to register yearly.",
            "key_points": [
                "Yearly registration",
                "Applies to all SMEs",
                "Penalty applies after 30 days delay",
            ],
            "changes_detected": "New requirement introduced.",
            "risk_level": "Medium",
            "recommendation": "Alert business owners.",
        },
        {
            "summary": "The tax for digital services has been reduced.",
            "key_points": [
                "New tax rate: 10%",
                "Old tax rate: 15%",
                "Effective from 2025",
            ],
            "changes_detected": "Tax rate dropped by 5%.",
            "risk_level": "Low",
            "recommendation": "Update tax calculation systems.",
        },
    ]

    @staticmethod
    def generate_summary(raw_content: str) -> dict:
        """
        Generate mock JSON summary based on content hashing.
        Always returns the JSON structure your system expects.
        """

        # Pick a predictable mock pattern
        base = random.choice(MockAIService.MOCK_DATA_POINTS)

        # Create stable hash for test tracking
        content_hash = hashlib.md5(raw_content.encode("utf-8")).hexdigest()

        return {
            "summary": base["summary"],
            "key_points": base["key_points"],
            "changes_detected": base["changes_detected"],
            "risk_level": base["risk_level"],
            "recommendation": base["recommendation"],
            "meta": {
                "scraped_from": "https://example.com",
                "generated_at": str(datetime.utcnow()),
                "hash": content_hash[:10],
            },
            "html_object": "<div>Mock HTML Content</div>",
            "text_object": raw_content[:200],
        }

    @staticmethod
    def generate_fixed_summary(version: int = 1) -> dict:
        """
        Force predictable output for unit tests.
        """

        return {
            "summary": f"Summary version {version}",
            "key_points": [f"Test point {version}"],
            "changes_detected": f"Change version {version}",
            "risk_level": "Medium",
            "recommendation": f"Recommendation {version}",
            "meta": {"version": version},
            "html_object": "<p>Test HTML</p>",
            "text_object": f"Test text for version {version}",
        }
