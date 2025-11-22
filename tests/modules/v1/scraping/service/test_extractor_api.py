import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
MOCK_HTML = "<html><body><h1>Hello World</h1></body></html>"

@pytest.mark.anyio
async def test_extract_text():
    with patch(
        "app.api.modules.v1.scraping.service.extractor_service.get_minio_client",
        return_value=AsyncMock()
    ) as mock_client, patch(
        "app.api.modules.v1.scraping.service.extractor_service.read_object",
        new_callable=AsyncMock
    ) as mock_read, patch(
        "app.api.modules.v1.scraping.service.extractor_service.write_object",
        new_callable=AsyncMock
    ) as mock_write:

        # Mock the MinIO functions
        mock_read.return_value = MOCK_HTML
        mock_write.return_value = None

        # Make the request
        response = client.post("/scraping/extract/test_page.html")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["html_object"] == "test_page.html"
        assert data["text_object"] == "test_page.txt"
        assert "Hello World" in data["preview"]

        mock_write.assert_called_once()

'''
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123
MINIO_SECURE=False
'''