import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


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


def start(hour: int = 2, minute: int = 0) -> None:
    _scheduler.add_job(_run_crawl, "cron", hour=hour, minute=minute, id="nightly_crawl")
    _scheduler.start()
    logger.info("Scheduler started; crawl scheduled at %02d:%02d", hour, minute)


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
