"""
Headless renderer: prints engine events to the terminal.

This is the sink used by --headless, and keeps the CLI behaving as it
did before the UI existed.
"""

import sys

from core import transcript
from core.events import (
    ChatEvent,
    LevelEvent,
    SpeechEvent,
    StatusEvent,
    SystemEvent,
    UsageEvent,
)


_COLORS = {
    transcript.YOU: "\033[36m",        # cyan
    transcript.ASSISTANT: "\033[33m",  # yellow
    "chat": "\033[90m",                # grey
    "system": "\033[35m",              # magenta
}

_RESET = "\033[0m"


def _paint(text, kind):
    if not sys.stdout.isatty():
        return text

    return f"{_COLORS.get(kind, '')}{text}{_RESET}"


class ConsoleSink:
    """Callable event sink that prints to stdout."""

    def __init__(self, settings):
        self._settings = settings

    def __call__(self, event):
        if isinstance(event, SpeechEvent):
            label = (
                "YOU" if event.speaker == transcript.YOU
                else self._settings.assistant_name
            )
            print(
                _paint(f"{label:>6} │ {event.text}", event.speaker),
                flush=True
            )

        elif isinstance(event, ChatEvent):
            marker = {"react": "→", "context": "·"}.get(event.mode, " ")
            print(
                _paint(
                    f"{marker}{'CHAT':>5} │ {event.username}: {event.message}",
                    "chat"
                ),
                flush=True
            )

        elif isinstance(event, SystemEvent):
            print(_paint(f"{'··':>6} │ {event.message}", "system"), flush=True)

        elif isinstance(event, StatusEvent):
            detail = f" ({event.detail})" if event.detail else ""
            print(
                _paint(
                    f"{'··':>6} │ {event.component}: "
                    f"{event.status.value}{detail}",
                    "system"
                ),
                flush=True
            )

        elif isinstance(event, UsageEvent):
            print(
                _paint(
                    f"{'··':>6} │ {event.seconds:.0f}s used, "
                    f"context {event.context_ratio:.1%}",
                    "system"
                ),
                flush=True
            )

        elif isinstance(event, LevelEvent):
            # Only meaningful as a live meter; ignored on the console.
            pass
