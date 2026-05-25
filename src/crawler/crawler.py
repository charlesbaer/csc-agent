import logging
from urllib.parse import urljoin, urlparse

import html2text
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_SITE_ROOT = "https://communityswimclub.com"
_CONVERTER = html2text.HTML2Text()
_CONVERTER.ignore_links = False
_CONVERTER.ignore_images = True
_CONVERTER.body_width = 0


def crawl_website() -> str:
    """Crawl communityswimclub.com and return all content as a single markdown string."""
    visited: set[str] = set()
    to_visit = [_SITE_ROOT]
    pages: list[str] = []

    while to_visit:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "CSC-Agent/1.0"})
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove nav, footer, scripts — keep main content
        for tag in soup.select("script, style, nav, footer, header"):
            tag.decompose()

        markdown = _CONVERTER.handle(str(soup))
        if markdown.strip():
            pages.append(f"<!-- Source: {url} -->\n\n{markdown.strip()}")

        # Follow internal links
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            parsed = urlparse(href)
            if parsed.netloc in ("", urlparse(_SITE_ROOT).netloc) and parsed.scheme in (
                "http",
                "https",
                "",
            ):
                clean = parsed._replace(fragment="", query="").geturl()
                if clean not in visited and clean.startswith(_SITE_ROOT):
                    to_visit.append(clean)

    logger.info("Crawled %d pages from %s", len(pages), _SITE_ROOT)
    return "\n\n---\n\n".join(pages)
