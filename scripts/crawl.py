"""One-shot crawler run: uv run python scripts/crawl.py"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level="INFO", format="%(levelname)s %(name)s %(message)s")

from src.config import get_config  # noqa: E402
from src.crawler.knowledge_builder import build_knowledge_base  # noqa: E402

cfg = get_config()
content = build_knowledge_base(
    facebook_page_id=cfg.facebook_page_id,
    facebook_token=cfg.facebook_page_access_token,
)
print(f"\nDone. knowledge.md is {len(content):,} chars ({len(content.encode()):,} bytes).")
