"""
Readable console logging for a live conversation.

Transcripts arrive as a stream of small deltas ("Hey", ",", " what's
up") for both speakers, and because GPT-Live is full-duplex those two
streams can interleave. Printing deltas as they arrive produces one
undifferentiated smear of text, so this buffers per speaker and emits
a labelled line once that speaker's turn looks finished.

A turn is considered finished when any of these happen:
  - the other speaker starts talking
  - there's a gap in the session timeline (GAP_MS)
  - nothing new arrives for IDLE_FLUSH_SECONDS of real time
"""

import sys
import time
import asyncio

import config


# A pause longer than this in the session timeline starts a new line
# for the same speaker.
GAP_MS = 1500

# Flush a pending line after this much real-world silence, so the last
# thing said still shows up promptly instead of waiting for whatever
# gets said next.
IDLE_FLUSH_SECONDS = 1.0

YOU = "you"
ASSISTANT = "assistant"

_COLORS = {
    YOU: "\033[36m",        # cyan
    ASSISTANT: "\033[33m",  # yellow
    "chat": "\033[90m",     # grey
    "system": "\033[35m",   # magenta
}

_RESET = "\033[0m"


def _supports_color():
    return sys.stdout.isatty()


def _paint(text, kind):
    if not _supports_color():
        return text

    return f"{_COLORS.get(kind, '')}{text}{_RESET}"


class TranscriptLogger:
    """
    Buffers transcript deltas per speaker and prints labelled lines.
    """

    def __init__(self):
        self._speaker = None
        self._buffer = ""
        self._last_end_ms = None
        self._last_delta_at = None

    # --------------------------------------------------------
    # SPEECH
    # --------------------------------------------------------

    def add(self, speaker, delta, start_ms=None, end_ms=None):
        if not delta:
            return

        if self._speaker is not None:
            changed_speaker = speaker != self._speaker

            gapped = (
                start_ms is not None
                and self._last_end_ms is not None
                and start_ms - self._last_end_ms > GAP_MS
            )

            if changed_speaker or gapped:
                self.flush()

        self._speaker = speaker
        self._buffer += delta
        self._last_delta_at = time.monotonic()

        if end_ms is not None:
            self._last_end_ms = end_ms

    def flush(self):
        text = self._buffer.strip()

        self._buffer = ""
        self._last_end_ms = None
        self._last_delta_at = None

        if not text:
            self._speaker = None
            return

        label = "YOU" if self._speaker == YOU else config.ASSISTANT_NAME
        kind = self._speaker

        print(_paint(f"{label:>6} │ {text}", kind), flush=True)

        self._speaker = None

    # --------------------------------------------------------
    # NON-SPEECH LINES
    # --------------------------------------------------------

    def chat(self, username, message, mode=None):
        """
        Log a Twitch chat message.

        mode marks which channel it took into the session:
          "react"   -> sent as something to respond to out loud
          "context" -> buffered as quiet background context
        """

        self.flush()

        marker = {"react": "→", "context": "·"}.get(mode, " ")
        line = f"{marker}{'CHAT':>5} │ {username}: {message}"

        print(_paint(line, "chat"), flush=True)

    def system(self, message):
        """Log an app/session lifecycle message."""

        self.flush()
        print(_paint(f"{'··':>6} │ {message}", "system"), flush=True)

    # --------------------------------------------------------
    # IDLE FLUSHING
    # --------------------------------------------------------

    async def run_idle_flusher(self):
        """
        Flushes a pending line once the speaker has gone quiet, so the
        console stays current instead of holding the last sentence
        until somebody talks again.
        """

        while True:
            await asyncio.sleep(0.3)

            if self._last_delta_at is None:
                continue

            if time.monotonic() - self._last_delta_at >= IDLE_FLUSH_SECONDS:
                self.flush()
