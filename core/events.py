"""
Events the engine emits for whatever is rendering it.

The engine never prints and never touches a widget — it calls an emit
callable. Headless mode points that at the console renderer; the UI
points it at a queue the Tk main thread drains. Because events cross
threads, they're plain immutable dataclasses carrying no live objects.
"""

from enum import Enum
from dataclasses import dataclass


class Status(Enum):
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ONLINE = "online"
    ERROR = "error"


# Components that report status, in display order.
SESSION = "session"
CHAT = "chat"
MIC = "mic"
SPEAKER = "speaker"


@dataclass(frozen=True)
class StatusEvent:
    component: str
    status: Status
    detail: str = ""


@dataclass(frozen=True)
class SpeechEvent:
    """A completed turn of transcript, ready to display as one line."""

    speaker: str  # transcript.YOU or transcript.ASSISTANT
    text: str


@dataclass(frozen=True)
class ChatEvent:
    username: str
    message: str
    mode: str  # "react" (sent to be answered) or "context" (silent)


@dataclass(frozen=True)
class SystemEvent:
    message: str


@dataclass(frozen=True)
class UsageEvent:
    seconds: float
    context_ratio: float


@dataclass(frozen=True)
class LevelEvent:
    """Mic input peak, 0.0–1.0, for the level meter."""

    peak: float
