from unittest.mock import patch
from uuid import uuid4

import pytest

from app.api.utils.extractor_service import (
    TextExtractorService,
    cleaned_html,
    normalize_text,
)

# ---------------------------------------------------
#  TEXT CLEANING TESTS
# ---------------------------------------------------


def test_normalize_text():
    assert normalize_text("hello   world") == "hello world"
    assert normalize_text("a\n\nb") == "a b"
    assert normalize_text("\xa0test\xa0") == "test"


def test_cleaned_html_basic():
    html = b"""
        <html>
            <body>
                <h1>Hello</h1>
                <p>World!</p>
            </body>
        </html>
    """

    result = cleaned_html(html)
    assert "Hello" in result
    assert "World" in result
    assert "<" not in result  # ensure tags removed


def test_cleaned_html_removes_junk():
    html = b"""
        <html>
            <script>var x = 1</script>
            <style>.x { color: red }</style>
            <div id="cookie-banner">Accept Cookies</div>
            <p>Useful data</p>
        </html>
    """

    result = cleaned_html(html)

    assert "Useful data" in result
    assert "cookie" not in result.lower()
    assert "script" not in result.lower()


# ---------------------------------------------------
#  MOCKED MINIO INTERACTION TESTS
# ---------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_minio_success():
    service = TextExtractorService()

    fake_html = b"<html><body><p>Hello world</p></body></html>"

    with patch(
        "app.api.modules.v1.scraping.service.extractor_service.fetch_raw_content_from_minio",
        return_value=fake_html,
    ):
        result = await service.extract_from_minio("bucket", "file.html")

    assert "Hello world" in result


@pytest.mark.asyncio
async def test_extract_from_minio_empty():
    service = TextExtractorService()

    with patch(
        "app.api.modules.v1.scraping.service.extractor_service.fetch_raw_content_from_minio",
        return_value=b"",
    ):
        result = await service.extract_from_minio("bucket", "file.html")

    assert result == ""


# ---------------------------------------------------
#  EXTRACT + UPLOAD TESTS
# ---------------------------------------------------


@pytest.mark.asyncio
async def test_extract_and_upload_success():
    service = TextExtractorService()

    fake_html = b"<html><body><p>Hello!</p></body></html>"

    with (
        patch(
            "app.api.modules.v1.scraping.service.extractor_service.fetch_raw_content_from_minio",
            return_value=fake_html,
        ),
        patch(
            "app.api.modules.v1.scraping.service.extractor_service.upload_raw_content",
            return_value=True,
        ) as mock_upload,
    ):
        resp = await service.extract_and_upload(
            src_bucket="raw-bucket",
            html_object="test.html",
            dest_bucket="clean-bucket",
            source_id=uuid4(),
        )

    assert resp["success"] is True
    assert resp["status_code"] == 200
    assert "minio_object_key" in resp["data"]
    assert resp["data"]["preview"].startswith("Hello")
    mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_extract_and_upload_upload_failure():
    service = TextExtractorService()

    fake_html = b"<html><body><p>Hello!</p></body></html>"

    with (
        patch(
            "app.api.modules.v1.scraping.service.extractor_service.fetch_raw_content_from_minio",
            return_value=fake_html,
        ),
        patch(
            "app.api.modules.v1.scraping.service.extractor_service.upload_raw_content",
            side_effect=Exception("MinIO error"),
        ),
    ):
        resp = await service.extract_and_upload(
            src_bucket="raw-bucket",
            html_object="test.html",
            dest_bucket="clean-bucket",
            source_id=uuid4(),
        )

    assert resp["success"] is False
    assert resp["status_code"] == 500
    assert "Failed to upload" in resp["message"]


@pytest.mark.asyncio
async def test_extract_and_upload_no_text_extracted():
    service = TextExtractorService()

    with patch(
        "app.api.modules.v1.scraping.service.extractor_service.fetch_raw_content_from_minio",
        return_value=b"      ",  # blank HTML
    ):
        resp = await service.extract_and_upload(
            src_bucket="raw-bucket",
            html_object="test.html",
            dest_bucket="clean-bucket",
            source_id=uuid4(),
        )

    assert resp["success"] is False
    assert resp["status_code"] == 400


# ---------------------------------------------------
#  MINIO KEY GENERATION TEST
# ---------------------------------------------------


def test_generate_minio_key():
    service = TextExtractorService()

    source_id = uuid4()
    revision_id = uuid4()

    key = service._generate_minio_key(source_id, revision_id)

    assert key.startswith(f"clean/{source_id}/")
    assert key.endswith(f"{revision_id}.txt")
    assert len(key.split("/")) == 3  # clean / source / timestamp_file
