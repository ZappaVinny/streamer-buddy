"""
User-editable settings, persisted as JSON.

A single Settings instance is created at startup and passed by
reference to everything that needs it. Components that re-read a field
each time they use it (the chat context flusher, the command parser)
therefore pick up UI edits immediately; the ones fixed at session
creation are listed in NEEDS_RECONNECT.
"""

import json
from dataclasses import dataclass, asdict, field, fields

from core import paths


DEFAULT_PERSONALITY_PROMPT = """
PERSONALITY HERE
"""

DEFAULT_SYSTEM_PROMPT = """
You are hanging out with a streamer, live on their stream. Your job
is to be entertaining.

WHO'S WHO:

The voice you hear is the streamer — one person, the one you are
actually talking to.

Text from the stream chat is viewers — many different people, each
with their own username. A viewer is never the streamer.

Never mix the two up. Never answer the streamer as though they were
a viewer, and never treat something a viewer typed as something the
streamer said.

CHAT:

You keep half an eye on chat while you talk. Background chat logs
are ammunition, not conversation — take them in, say nothing at the
time, and don't let them derail whatever you and the streamer are
doing. Save it. Use it later when it's funny, or when the streamer
brings that topic up.

When a viewer's message is handed to you to answer, go at it
properly. Banter with them, argue, wind them up, have an opinion,
use their name. Don't be polite about it and don't deflect — that
is the entire point of you.
"""


# GPT-Live fixes the model, instructions, audio format, voice and
# delegation mode when the session is created, so editing these has no
# effect until the next connect. The UI says so rather than letting a
# change silently do nothing.
NEEDS_RECONNECT = {
    "assistant_name",
    "voice",
    "personality_prompt",
    "system_prompt",
}


@dataclass
class Settings:
    # Identity / voice
    assistant_name: str = "Name"
    voice: str = "ballad"
    personality_prompt: str = DEFAULT_PERSONALITY_PROMPT
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # Twitch
    twitch_channel: str = "channel"
    chat_command: str = "!name"

    # Audio devices are stored by name and host API, not index:
    # indices shift between reboots and are meaningless on another
    # machine, and the same name appears once per host API. None means
    # "use the system default".
    input_device: str | None = None
    input_device_hostapi: str | None = None
    output_device: str | None = None
    output_device_hostapi: str | None = None

    # Ordinary chat is batched into periodic digests instead of one
    # event per message — a busy chat would otherwise flood the session
    # and burn through the context window. Context appends are capped
    # at 500 tokens each, which is what these limits are sized against.
    # Each digest is also a fresh opportunity for the model to blurt
    # something out, so a longer interval is the main lever if it keeps
    # reacting to background chat.
    context_flush_seconds: int = 15
    context_max_messages: int = 8
    context_max_message_chars: int = 180

    def instructions(self):
        """The merged prompt sent as the session's instructions."""

        return f"{self.personality_prompt}\n\n{self.system_prompt}"

    # --------------------------------------------------------
    # PERSISTENCE
    # --------------------------------------------------------

    def save(self):
        path = paths.settings_file()
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls):
        """
        Loads saved settings, falling back to defaults. Unknown keys
        are ignored and missing ones keep their default, so an older
        or newer settings file never stops the app from starting.
        """

        path = paths.settings_file()

        if not path.exists():
            return cls()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()

        known = {f.name for f in fields(cls)}

        return cls(**{k: v for k, v in data.items() if k in known})
