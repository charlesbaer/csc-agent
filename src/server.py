import json
import logging
from pathlib import Path

from flask import Flask

from src.adapters.messenger import messenger_bp
from src.agent import agent as agent_module
from src.config import get_config
from src.db import init_db
from src.scheduler import shutdown, start

logger = logging.getLogger(__name__)

_META_FILE = Path(__file__).parent.parent / "data" / "knowledge_meta.json"


def create_app() -> Flask:
    cfg = get_config()
    logging.basicConfig(level=cfg.log_level)

    app = Flask(__name__)
    app.register_blueprint(messenger_bp)

    init_db()
    agent_module.load_knowledge()
    start(hour=cfg.crawl_schedule_hour, minute=cfg.crawl_schedule_minute)

    import atexit

    atexit.register(shutdown)

    @app.get("/health")
    def health():
        meta = {}
        if _META_FILE.exists():
            meta = json.loads(_META_FILE.read_text())
        return {"status": "ok", **meta}, 200

    return app
