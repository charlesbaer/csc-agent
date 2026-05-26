import hashlib
import hmac
import logging
import threading
from datetime import datetime, timezone

import requests as http_requests
from flask import Blueprint, abort, request

from src.agent import agent as agent_module
from src.agent.types import Channel, Message
from src.config import get_config
from src.db import ConversationLog, ProcessedMessage, get_session
from src.observability import trace_response

logger = logging.getLogger(__name__)
messenger_bp = Blueprint("messenger", __name__)

_GRAPH_URL = "https://graph.facebook.com/v21.0/me/messages"
_NON_TEXT_REPLY = (
    "Hi! I can only read text messages. "
    "If you have a question, just type it out and I'll do my best to help."
)


def _verify_signature(payload: bytes, signature_header: str) -> bool:
    cfg = get_config()
    expected = "sha256=" + hmac.new(
        cfg.messenger_app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _send_message(recipient_psid: str, text: str) -> None:
    cfg = get_config()
    try:
        resp = http_requests.post(
            _GRAPH_URL,
            params={"access_token": cfg.messenger_page_access_token},
            json={
                "recipient": {"id": recipient_psid},
                "message": {"text": text},
                "messaging_type": "RESPONSE",
            },
            timeout=10,
        )
        if not resp.ok:
            logger.error(
                "Failed to send Messenger message to %s: %s %s",
                recipient_psid,
                resp.status_code,
                resp.text,
            )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to send Messenger message to %s: %s", recipient_psid, exc)


def _handle_message_async(sender_psid: str, message_text: str) -> None:
    import time

    start = time.monotonic()
    msg = Message(text=message_text, channel=Channel.MESSENGER, sender_id=sender_psid)

    try:
        response = agent_module.respond(msg)
    except Exception as exc:
        logger.error("Agent error: %s", exc)
        response_text = (
            "Sorry, something went wrong on our end. "
            "Please try again or email secretary@communityswimclub.com."
        )
        escalated = True
    else:
        response_text = response.text
        escalated = response.escalated

    latency_ms = int((time.monotonic() - start) * 1000)
    _send_message(sender_psid, response_text)

    # Log to DB (hash the PSID — no raw PII)
    sender_hash = hashlib.sha256(sender_psid.encode()).hexdigest()
    with get_session() as session:
        session.add(
            ConversationLog(
                channel="messenger",
                sender_id_hash=sender_hash,
                message_text=message_text,
                response_text=response_text,
                latency_ms=latency_ms,
                escalated=escalated,
                created_at=datetime.now(timezone.utc),
            )
        )

    trace_response(
        channel="messenger",
        message=message_text,
        response=response_text,
        latency_ms=latency_ms,
        escalated=escalated,
    )


@messenger_bp.get("/webhook")
def verify():
    cfg = get_config()
    if (
        request.args.get("hub.mode") == "subscribe"
        and request.args.get("hub.verify_token") == cfg.messenger_verify_token
    ):
        return request.args.get("hub.challenge", ""), 200
    abort(403)


@messenger_bp.post("/webhook")
def receive():
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(request.data, sig):
        abort(403)

    payload = request.get_json(force=True, silent=True) or {}

    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            mid = event.get("message", {}).get("mid")
            sender_psid = event.get("sender", {}).get("id", "")
            message_text = event.get("message", {}).get("text")

            if not mid or not sender_psid:
                continue

            # Idempotency check
            with get_session() as session:
                if session.get(ProcessedMessage, mid):
                    continue
                session.add(ProcessedMessage(mid=mid, processed_at=datetime.now(timezone.utc)))

            if not message_text:
                threading.Thread(
                    target=_send_message, args=(sender_psid, _NON_TEXT_REPLY), daemon=True
                ).start()
                continue

            threading.Thread(
                target=_handle_message_async,
                args=(sender_psid, message_text),
                daemon=True,
            ).start()

    return "OK", 200
