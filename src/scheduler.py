import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()

_RETENTION_DAYS = 365


def _run_crawl() -> None:
    from src.agent import agent as agent_module
    from src.config import get_config
    from src.crawler.knowledge_builder import build_knowledge_base

    logger.info("Nightly crawl starting...")
    cfg = get_config()
    try:
        build_knowledge_base(
            facebook_page_id=cfg.facebook_page_id,
            facebook_token=cfg.facebook_page_access_token,
        )
        agent_module.load_knowledge()
        logger.info("Nightly crawl complete; knowledge base reloaded")
    except Exception as exc:
        logger.error("Nightly crawl failed: %s", exc)


def _purge_old_records() -> None:
    from sqlalchemy import delete

    from src.db import ConversationLog, ProcessedMessage, get_session

    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    try:
        with get_session() as session:
            log_result = session.execute(
                delete(ConversationLog).where(ConversationLog.created_at < cutoff)
            )
            dedup_result = session.execute(
                delete(ProcessedMessage).where(ProcessedMessage.processed_at < cutoff)
            )
        logger.info(
            "Purged %d conversation log rows and %d dedup rows older than %d days",
            log_result.rowcount,
            dedup_result.rowcount,
            _RETENTION_DAYS,
        )
    except Exception as exc:
        logger.error("Record purge failed: %s", exc)


def start(hour: int = 2, minute: int = 0) -> None:
    _scheduler.add_job(_run_crawl, "cron", hour=hour, minute=minute, id="nightly_crawl")
    # Purge runs 30 minutes after the crawl to avoid contention
    purge_total = hour * 60 + minute + 30
    _scheduler.add_job(
        _purge_old_records,
        "cron",
        hour=(purge_total // 60) % 24,
        minute=purge_total % 60,
        id="nightly_purge",
    )
    _scheduler.start()
    logger.info("Scheduler started; crawl scheduled at %02d:%02d", hour, minute)


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
