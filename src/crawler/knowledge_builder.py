import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.crawler.crawler import crawl_website
from src.crawler.facebook import fetch_page_posts

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.md"
META_FILE = DATA_DIR / "knowledge_meta.json"
OVERRIDES_DIR = DATA_DIR / "overrides"


def build_knowledge_base(facebook_page_id: str = "", facebook_token: str = "") -> str:
    """Crawl all sources, merge with overrides, write knowledge.md. Returns the content."""
    sections: list[str] = []

    # 1. Website (authoritative)
    logger.info("Crawling website...")
    website_content = crawl_website()
    if website_content:
        sections.append(f"# Community Swim Club — Website Content\n\n{website_content}")

    # 2. Facebook page posts (secondary)
    if facebook_page_id and facebook_token:
        logger.info("Fetching Facebook posts...")
        fb_content = fetch_page_posts(facebook_page_id, facebook_token)
        if fb_content:
            sections.append(f"# Community Swim Club — Facebook Page\n\n{fb_content}")

    # 3. Manual overrides (always authoritative; merged last so they take precedence)
    if OVERRIDES_DIR.exists():
        for override_file in sorted(OVERRIDES_DIR.glob("*.md")):
            content = override_file.read_text().strip()
            if content:
                logger.info("Merging override: %s", override_file.name)
                sections.append(f"# Override: {override_file.stem}\n\n{content}")

    knowledge = "\n\n---\n\n".join(sections)

    # Only write if content changed
    existing = KNOWLEDGE_FILE.read_text() if KNOWLEDGE_FILE.exists() else ""
    if knowledge == existing:
        logger.info("Knowledge base unchanged; skipping write")
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        KNOWLEDGE_FILE.write_text(knowledge)
        logger.info(
            "Wrote knowledge.md (%d bytes, %d chars)", len(knowledge.encode()), len(knowledge)
        )

    META_FILE.write_text(
        json.dumps(
            {
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "bytes": len(knowledge.encode()),
                "sources": [
                    "https://communityswimclub.com",
                    f"https://www.facebook.com/{facebook_page_id}",
                ],
            },
            indent=2,
        )
    )

    return knowledge
