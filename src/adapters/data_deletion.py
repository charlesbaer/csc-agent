import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import delete

from src.config import get_config
from src.db import ConversationLog, get_session

logger = logging.getLogger(__name__)

data_deletion_bp = Blueprint("data_deletion", __name__)


def _decode_signed_request(signed_request: str, app_secret: str) -> dict:
    """Verify and decode a Meta signed_request parameter."""
    try:
        encoded_sig, payload = signed_request.split(".", 1)
    except ValueError:
        raise ValueError("Malformed signed_request")

    def _b64_decode(s: str) -> bytes:
        s += "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s)

    sig = _b64_decode(encoded_sig)
    expected = hmac.new(app_secret.encode(), payload.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid signature")

    return json.loads(_b64_decode(payload))


@data_deletion_bp.post("/data-deletion")
def handle_deletion():
    """
    Meta Data Deletion Callback endpoint.
    Called when a user removes the app and requests data deletion via Facebook settings.
    https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
    """
    cfg = get_config()
    signed_request = request.form.get("signed_request", "")

    try:
        data = _decode_signed_request(signed_request, cfg.messenger_app_secret)
    except Exception as exc:
        logger.warning("Invalid data deletion signed_request: %s", exc)
        abort(400)

    user_id = data.get("user_id", "")
    if not user_id:
        logger.warning("Data deletion request missing user_id")
        abort(400)

    # Our DB stores sha256(psid) — hash the incoming user_id the same way
    sender_hash = hashlib.sha256(user_id.encode()).hexdigest()

    with get_session() as session:
        result = session.execute(
            delete(ConversationLog).where(ConversationLog.sender_id_hash == sender_hash)
        )

    deleted_count = result.rowcount
    logger.info(
        "Data deletion: removed %d conversation_log rows for user_id hash %s",
        deleted_count,
        sender_hash[:12] + "...",
    )

    # Confirmation code: short hex derived from user + timestamp (no PII)
    ts = datetime.now(timezone.utc).isoformat()
    confirmation_code = hashlib.sha256(f"{sender_hash}:{ts}".encode()).hexdigest()[:16]

    return jsonify({
        "url": "https://csc-agent.fly.dev/data-deletion/status",
        "confirmation_code": confirmation_code,
    })


@data_deletion_bp.get("/data-deletion/status")
def deletion_status():
    """Human-readable status page linked from the deletion callback response."""
    return (
        "<h1>Data Deletion</h1>"
        "<p>Your data has been deleted from the Community Swim Club automated assistant. "
        "If you have questions, contact "
        "<a href='mailto:secretary@communityswimclub.com'>secretary@communityswimclub.com</a>.</p>"
    )
