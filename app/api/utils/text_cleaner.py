import logging
import re
from typing import Optional
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

def clean_html_content(raw_html_bytes: Optional[bytes]) -> str:
    """
    Converts raw HTML bytes into clean, token-efficient text for AI analysis.
    
    Process:
    1. Decodes bytes to string (handling encoding errors).
    2. Removes non-content tags (scripts, styles, navs, footers).
    3. Strips comments and attributes.
    4. Normalizes whitespace (collapses multiple newlines/spaces).
    
    Args:
        raw_html_bytes (bytes): The raw HTML content from the scraper.

    Returns:
        str: Cleaned, human-readable text. Returns empty string on failure.
    """
    if not raw_html_bytes:
        return ""

    try:
        # 1. Decode Bytes
        # We try UTF-8 first, then fallback to Latin-1 if needed
        try:
            html_text = raw_html_bytes.decode('utf-8')
        except UnicodeDecodeError:
            html_text = raw_html_bytes.decode('latin-1', errors='replace')

        # 2. Parse HTML
        soup = BeautifulSoup(html_text, "html.parser")

        # 3. Remove Junk Tags (Noise Reduction)
        # These tags typically contain code, navigation, or irrelevant metadata
        noise_tags = [
            "script", "style", "meta", "noscript", "header", "footer", 
            "nav", "iframe", "svg", "path", "link", "button", "input", 
            "form", "select", "option", "aside", "ad", "banner"
        ]
        
        for tag in soup(noise_tags):
            tag.decompose()

        # 4. Remove Comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 5. Extract Text
        # separator=' ' ensures words don't merge when tags are removed (e.g., <div>A</div><div>B</div> -> A B)
        text = soup.get_text(separator="\n")

        # 6. Normalize Whitespace
        # Collapse multiple spaces into one, and massive newlines into manageable chunks
        # Regex explanation:
        # \s+ matches any whitespace character (spaces, tabs, newlines)
        
        # Step A: Replace generic horizontal whitespace (tabs, multi-spaces) with single space
        # We iterate line by line to preserve paragraph structure roughly
        lines = []
        for line in text.splitlines():
            clean_line = re.sub(r'\s+', ' ', line).strip()
            if clean_line:
                lines.append(clean_line)
        
        # Step B: Rejoin with newlines
        clean_text = "\n".join(lines)

        # 7. Final Length Check
        # If we stripped everything (e.g., a JS-only site that wasn't rendered properly), log warning
        if len(clean_text) < 50:
            logger.warning("Cleaned text is suspiciously short (<50 chars). Page might be empty or blocked.")

        return clean_text

    except Exception as e:
        logger.error(f"Error cleaning HTML content: {e}")
        # Return empty string so the pipeline doesn't crash, but AI will see empty input
        return ""