"""
Turns streaming transcript deltas into complete, attributable lines.

Transcripts arrive as a stream of small deltas ("Hey", ",", " what's
up") for both speakers, and because GPT-Live is full-duplex those two
streams can interleave. Emitting deltas as they arrive produces one
undifferentiated smear, so this buffers per speaker and emits a whole
line once that speaker's turn looks finished.

A turn is considered finished when any of these happen:
  - the other speaker starts talking
  - there's a gap in the session timeline (GAP_MS)
  - nothing new arrives for IDLE_FLUSH_SECONDS of real time

This module produces events only. Rendering lives with whatever is
displaying them (console.py for headless, the UI otherwise).
"""

import time
import asyncio

from core.events import SpeechEvent


# A pause longer than this in the session timeline starts a new line
# for the same speaker.
GAP_MS = 1500

# Flush a pending line after this much real-world silence, so the last
# thing said still shows up promptly instead of waiting for whatever
# gets said next.
IDLE_FLUSH_SECONDS = 1.0

YOU = "you"
ASSISTANT = "assistant"


class TranscriptLogger:
    """Buffers transcript deltas per speaker and emits finished lines."""

    def __init__(self, emit):
        self._emit = emit
        self._speaker = None
        self._buffer = ""
        self._last_end_ms = None
        self._last_delta_at = None

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
        speaker = self._speaker

        self._buffer = ""
        self._speaker = None
        self._last_end_ms = None
        self._last_delta_at = None

        if text:
            self._emit(SpeechEvent(speaker=speaker, text=text))

    async def run_idle_flusher(self):
        """
        Flushes a pending line once the speaker has gone quiet, so the
        display stays current instead of holding the last sentence
        until somebody talks again.
        """

        while True:
            await asyncio.sleep(0.3)

            if self._last_delta_at is None:
                continue

            if time.monotonic() - self._last_delta_at >= IDLE_FLUSH_SECONDS:
                self.flush()
