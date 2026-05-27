import logging
from datetime import date
from pathlib import Path

import anthropic

from src.agent.prompts import SYSTEM_INSTRUCTIONS, is_escalation
from src.agent.types import Message, Response
from src.config import get_config

logger = logging.getLogger(__name__)

_KNOWLEDGE_FILE = Path(__file__).parent.parent.parent / "data" / "knowledge.md"

# Loaded once at startup and refreshed by the nightly scheduler
_knowledge_block: str = ""


def load_knowledge() -> None:
    """Load (or reload) the knowledge base from disk into memory."""
    global _knowledge_block
    if not _KNOWLEDGE_FILE.exists():
        logger.warning("knowledge.md not found at %s; no club context loaded", _KNOWLEDGE_FILE)
        _knowledge_block = "(No club information available yet. Run the crawler first.)"
        return
    _knowledge_block = _KNOWLEDGE_FILE.read_text()
    logger.info("Loaded knowledge.md (%d chars)", len(_knowledge_block))


def respond(message: Message) -> Response:
    """Core entry point: given a member message, return a response."""
    cfg = get_config()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    knowledge = _knowledge_block or "(Knowledge base not loaded.)"

    result = client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=512,
        system=[
            # Block 1: static instructions (cached — rarely changes)
            {
                "type": "text",
                "text": SYSTEM_INSTRUCTIONS,
                "cache_control": {"type": "ephemeral"},
            },
            # Block 2: knowledge base (cached — changes nightly)
            {
                "type": "text",
                "text": f"## Club Knowledge Base\n\n{knowledge}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[
            {
                "role": "user",
                "content": f"[Today is {date.today().strftime('%A, %B %-d, %Y')}]\n\n{message.text}",
            }
        ],
    )

    response_text = result.content[0].text
    escalated = is_escalation(response_text)

    logger.info(
        "channel=%s model=%s input_tokens=%d output_tokens=%d escalated=%s",
        message.channel,
        cfg.anthropic_model,
        result.usage.input_tokens,
        result.usage.output_tokens,
        escalated,
    )

    return Response(text=response_text, escalated=escalated, channel=message.channel)
