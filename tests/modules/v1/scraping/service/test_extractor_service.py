from unittest.mock import patch

import pytest

from app.api.modules.v1.scraping.service.extractor_service import TextExtractorService

HTML_SAMPLE = "<html><body><p>Hello World</p></body></html>"


@pytest.mark.asyncio
async def test_extract_and_save_success():
    extractor = TextExtractorService()

    # Patch read/write where they are imported in extractor_service
    with (
        patch(
            "app.api.modules.v1.scraping.service.extractor_service.read_object",
            return_value=HTML_SAMPLE,
        ),
        patch("app.api.modules.v1.scraping.service.extractor_service.write_object") as mock_write,
        patch(
            "app.api.modules.v1.scraping.service.extractor_service.TextExtractorService._fallback_readability",
            return_value="Hello World",
        ),
    ):
        result = await extractor.extract_and_save(
            src_bucket="scraped-pages",
            html_object="test.html",
            dest_bucket="extracted-text",
            output_name="test.txt",
        )

        # Ensure write_object was called once
        mock_write.assert_called_once_with("extracted-text", "test.txt", "Hello World")

        # Check the returned result dictionary
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["data"]["object_name"] == "test.txt"
        assert result["data"]["bucket"] == "extracted-text"
        assert result["data"]["text_preview"] == "Hello World"
