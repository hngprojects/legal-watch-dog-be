"""
Test script to fetch the Cloudflare-protected PDF page from France Visas
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api.modules.v1.scraping.service.http_client_service import HTTPClientService
from app.api.modules.v1.scraping.service.pdf_service import PDFService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

async def test_france_visas_fetch():
    """Test fetching the France Visas PDF page"""
    print("Testing fetch of France Visas PDF page...")
    print("URL: https://france-visas.gouv.fr/documents/d/france-visas/frais-de-visa-anglais")
    print()

    try:
        # Initialize the services
        http_client = HTTPClientService()
        pdf_service = PDFService()

        # Test the fetch method directly
        url = "https://france-visas.gouv.fr/documents/d/france-visas/frais-de-visa-anglais"
        auth_creds = {}  # No auth needed

        print("Attempting to fetch with HTTP client...")
        try:
            raw_content = await http_client.fetch_content(url, auth_creds)
            print(f"✓ Fetch successful! Content length: {len(raw_content)} bytes")

            # Check if it's PDF
            if pdf_service.is_pdf(raw_content):
                print("✓ Content is PDF format")
                # Try to extract text
                try:
                    text_content = pdf_service.extract_text(raw_content)
                    print(f"✓ PDF text extracted: {len(text_content)} characters")
                    print("Sample text:")
                    print(text_content[:500] + "..." if len(text_content) > 500 else text_content)
                except Exception as e:
                    print(f"✗ PDF extraction failed: {e}")
            else:
                print("✓ Content appears to be HTML")
                print("Sample content:")
                print(raw_content[:500].decode('utf-8', errors='ignore') + "...")

        except Exception as e:
            print(f"✗ Fetch failed: {e}")

    except Exception as e:
        print(f"✗ Setup failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_france_visas_fetch())