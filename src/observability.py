import logging

logger = logging.getLogger(__name__)

_langfuse = None


def _get_client():
    global _langfuse
    if _langfuse is not None:
        return _langfuse

    from src.config import get_config

    cfg = get_config()
    if not cfg.langfuse_public_key or not cfg.langfuse_secret_key:
        return None

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=cfg.langfuse_public_key,
            secret_key=cfg.langfuse_secret_key,
            host=cfg.langfuse_host,
        )
    except Exception as exc:
        logger.warning("Langfuse init failed: %s", exc)

    return _langfuse


def trace_response(
    *,
    channel: str,
    message: str,
    response: str,
    latency_ms: int,
    escalated: bool,
) -> None:
    """Fire-and-forget: log a completed conversation turn to Langfuse."""
    client = _get_client()
    if not client:
        return

    try:
        trace = client.trace(
            name="csc-agent-response",
            tags=[channel],
            metadata={"channel": channel, "escalated": escalated, "latency_ms": latency_ms},
        )
        trace.generation(
            name="agent-reply",
            input=message,
            output=response,
            metadata={"escalated": escalated},
        )
        if escalated:
            trace.score(name="escalated", value=1)
    except Exception as exc:
        logger.warning("Langfuse trace failed: %s", exc)
