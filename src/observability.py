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
        import os

        from langfuse import Langfuse

        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", cfg.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", cfg.langfuse_secret_key)
        os.environ.setdefault("LANGFUSE_HOST", cfg.langfuse_host)
        _langfuse = Langfuse()
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
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    user_id: str = "",
    session_id: str = "",
) -> None:
    client = _get_client()
    if not client:
        return

    try:
        from langfuse import propagate_attributes

        with propagate_attributes(
            user_id=user_id or None,
            session_id=session_id or None,
            tags=[channel],
            trace_name="csc-agent-response",
        ):
            span = client.start_observation(
                name="csc-agent-response",
                as_type="generation",
                input=message,
                output=response,
                model=model or None,
                usage_details=(
                    {"input": input_tokens, "output": output_tokens}
                    if input_tokens or output_tokens
                    else None
                ),
                metadata={"channel": channel, "escalated": escalated, "latency_ms": latency_ms},
            )
            if escalated:
                span.score_trace(name="escalated", value=1)
            span.end()
    except Exception as exc:
        logger.warning("Langfuse trace failed: %s", exc)
