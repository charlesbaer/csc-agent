from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Channel(str, Enum):
    MESSENGER = "messenger"
    WIDGET = "widget"


@dataclass
class Message:
    text: str
    channel: Channel
    sender_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Prior turns as [{"role": "user"|"assistant", "content": "..."}, ...], oldest first
    history: list[dict[str, str]] = field(default_factory=list)


@dataclass
class Response:
    text: str
    escalated: bool = False
    channel: Channel = Channel.MESSENGER
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
