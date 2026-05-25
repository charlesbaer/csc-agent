import logging

import requests

logger = logging.getLogger(__name__)

_GRAPH_URL = "https://graph.facebook.com/v21.0"
_MAX_POSTS = 50


def fetch_page_posts(page_id: str, access_token: str) -> str:
    """Fetch recent posts from a Facebook page and return them as markdown."""
    if not access_token:
        logger.warning("No FACEBOOK_PAGE_ACCESS_TOKEN set; skipping Facebook crawl")
        return ""

    try:
        resp = requests.get(
            f"{_GRAPH_URL}/{page_id}/posts",
            params={
                "fields": "message,story,created_time",
                "limit": _MAX_POSTS,
                "access_token": access_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to fetch Facebook posts: %s", exc)
        return ""

    posts = resp.json().get("data", [])
    if not posts:
        return ""

    lines = ["## Recent Facebook Page Posts\n"]
    for post in posts:
        text = post.get("message") or post.get("story", "")
        date = post.get("created_time", "")[:10]
        if text:
            lines.append(f"**{date}:** {text.strip()}\n")

    logger.info("Fetched %d Facebook posts", len(posts))
    return "\n".join(lines)
