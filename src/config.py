import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    # Anthropic
    anthropic_api_key: str
    anthropic_model: str

    # Meta Messenger
    messenger_verify_token: str
    messenger_app_secret: str
    messenger_page_access_token: str

    # Facebook Graph API (crawling page posts)
    facebook_page_access_token: str
    facebook_page_id: str

    # Langfuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str

    # Crawler
    crawl_schedule_hour: int
    crawl_schedule_minute: int

    # App
    log_level: str


@lru_cache(maxsize=1)
def get_config() -> Config:
    load_dotenv()

    _required = [
        "ANTHROPIC_API_KEY",
        "MESSENGER_VERIFY_TOKEN",
        "MESSENGER_APP_SECRET",
        "MESSENGER_PAGE_ACCESS_TOKEN",
    ]
    missing = [k for k in _required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        messenger_verify_token=os.environ["MESSENGER_VERIFY_TOKEN"],
        messenger_app_secret=os.environ["MESSENGER_APP_SECRET"],
        messenger_page_access_token=os.environ["MESSENGER_PAGE_ACCESS_TOKEN"],
        facebook_page_access_token=os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", ""),
        facebook_page_id=os.getenv("FACEBOOK_PAGE_ID", "communityswimclub"),
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        langfuse_host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        crawl_schedule_hour=int(os.getenv("CRAWL_SCHEDULE_HOUR", "2")),
        crawl_schedule_minute=int(os.getenv("CRAWL_SCHEDULE_MINUTE", "0")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
