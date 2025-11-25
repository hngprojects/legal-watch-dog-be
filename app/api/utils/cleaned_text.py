import logging
import re

try:
    from bs4 import BeautifulSoup, Comment

    _HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    Comment = None
    _HAS_BS4 = False


logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")
    return text.strip()


def cleaned_html(raw_bytes: bytes) -> str:
    if not raw_bytes:
        return ""

    if not _HAS_BS4:
        logger.error(
            "BeautifulSoup is not installed. Install `beautifulsoup4` to enable HTML cleaning."
        )
        return ""

    try:
        try:
            html_str = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_str = raw_bytes.decode("latin-1", errors="replace")

        soup = BeautifulSoup(html_str, "html.parser")

        junk_tags = [
            "script",
            "style",
            "meta",
            "noscript",
            "header",
            "footer",
            "nav",
            "iframe",
            "svg",
            "path",
            "link",
            "button",
            "input",
            "form",
            "select",
            "option",
            "aside",
            "ad",
            "banner",
        ]
        for tag_name in junk_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        junk_keywords = [
            "cookie",
            "popup",
            "modal",
            "banner",
            "footer",
            "header",
            "ads",
            "tracking",
            "subscribe",
            "newsletter",
            "consent",
        ]
        pattern = re.compile("|".join(junk_keywords), re.IGNORECASE)

        for element in soup.find_all(True):
            elem_id = element.get("id", "")
            elem_class = " ".join(element.get("class", []))
            if pattern.search(elem_id) or pattern.search(elem_class):
                element.decompose()

        lines = [
            normalize_text(line)
            for line in soup.get_text(separator="\n").splitlines()
            if line.strip()
        ]
        readable_text = "\n".join(lines)

        if len(readable_text) < 50:
            logger.warning(
                "Extracted text is very short (<50 chars). Source content may be blocked."
            )

        return readable_text

    except Exception as err:
        logger.error(f"Failed to clean HTML content: {err}")
        return ""
