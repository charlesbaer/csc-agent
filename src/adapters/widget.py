import hashlib
import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, make_response, render_template, request
from flask_limiter import Limiter

from src.agent import agent as agent_module
from src.agent.types import Channel, Message
from src.config import get_config
from src.db import ConversationLog, get_session
from src.observability import trace_response

logger = logging.getLogger(__name__)
widget_bp = Blueprint("widget", __name__)

MAX_MESSAGE_LENGTH = 1000
MAX_HISTORY_TURNS = 6

_FALLBACK_REPLY = (
    "Sorry, something went wrong on our end. "
    "Please try again or email secretary@communityswimclub.com."
)


def _client_ip() -> str:
    forwarded = request.headers.get("Fly-Client-IP")
    if forwarded:
        return forwarded
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


limiter = Limiter(key_func=_client_ip)


def _chat_rate_limit() -> str:
    cfg = get_config()
    return f"{cfg.widget_rate_limit_per_minute} per minute;{cfg.widget_rate_limit_per_day} per day"


def _page_rate_limit() -> str:
    cfg = get_config()
    return f"{cfg.widget_page_rate_limit_per_minute} per minute"


def _clean_history(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    cleaned = []
    for turn in raw[-MAX_HISTORY_TURNS:]:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = turn.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        cleaned.append({"role": role, "content": content.strip()[:MAX_MESSAGE_LENGTH]})
    return cleaned


@widget_bp.errorhandler(429)
def _rate_limited(_exc):
    return jsonify({
        "error": "rate_limited",
        "reply": "We're getting a lot of questions right now — please try again in a minute.",
    }), 429


@widget_bp.get("/widget")
@limiter.limit(_page_rate_limit)
def widget_page():
    cfg = get_config()
    resp = make_response(
        render_template("widget/index.html", privacy_policy_url=cfg.privacy_policy_url)
    )
    resp.headers["Content-Security-Policy"] = f"frame-ancestors {cfg.widget_frame_ancestors}"
    return resp


@widget_bp.post("/chat")
@limiter.limit(_chat_rate_limit)
def chat():
    payload = request.get_json(force=True, silent=True) or {}

    message_text = payload.get("message")
    if not isinstance(message_text, str) or not message_text.strip():
        return jsonify({"error": "message is required"}), 400
    message_text = message_text.strip()[:MAX_MESSAGE_LENGTH]

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return jsonify({"error": "session_id is required"}), 400

    history = _clean_history(payload.get("history"))

    msg = Message(
        text=message_text,
        channel=Channel.WIDGET,
        sender_id=session_id,
        history=history,
    )

    start = time.monotonic()
    try:
        response = agent_module.respond(msg)
    except Exception as exc:
        logger.error("Agent error: %s", exc)
        response_text = _FALLBACK_REPLY
        escalated = True
        model = ""
        input_tokens = 0
        output_tokens = 0
    else:
        response_text = response.text
        escalated = response.escalated
        model = response.model
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens

    latency_ms = int((time.monotonic() - start) * 1000)

    session_hash = hashlib.sha256(session_id.encode()).hexdigest()
    with get_session() as db_session:
        db_session.add(
            ConversationLog(
                channel="widget",
                sender_id_hash=session_hash,
                message_text=message_text,
                response_text=response_text,
                latency_ms=latency_ms,
                escalated=escalated,
                created_at=datetime.now(timezone.utc),
            )
        )

    trace_response(
        channel="widget",
        message=message_text,
        response=response_text,
        latency_ms=latency_ms,
        escalated=escalated,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        user_id=session_hash,
        session_id=session_hash,
    )

    return jsonify({"reply": response_text, "escalated": escalated})
