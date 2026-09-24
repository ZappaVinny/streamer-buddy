"""
Values that are never edited by the user.

Anything a person might reasonably want to change from the UI lives in
settings.py instead.
"""

import random


APP_NAME = "Streamer Buddy"

# Used for the config directory and the keyring entry. Left as-is even
# though the display name changed — renaming it would orphan the saved
# settings and API key of anyone already running the app.
APP_SLUG = "stream-buddy"


# ------------------------------------------------------------
# GPT-LIVE
# ------------------------------------------------------------

MODEL = "gpt-live-1"

SESSIONS_URL = "https://api.openai.com/v1/live/sessions"

# Offered in the voice dropdown. "marin" and "cedar" are OpenAI's
# documented recommendations; the rest come from the published voice
# list. An unsupported value fails loudly at session creation.
VOICES = [
    "alloy",
    "ash",
    "ballad",
    "cedar",
    "coral",
    "echo",
    "marin",
    "sage",
    "shimmer",
    "verse",
]


# ------------------------------------------------------------
# AUDIO
# ------------------------------------------------------------

# WebRTC negotiates the wire format through SDP, so this is only what
# we capture/play locally. 48kHz is Opus's native rate, which keeps
# the mic path free of resampling.
SAMPLE_RATE = 48000
CHANNELS = 1
BLOCK_SIZE = 960  # 20 ms at 48 kHz — one Opus frame

# Peak level is sampled from the mic callback for the UI meter. That
# callback is realtime-sensitive, so we look at every Nth sample and
# only report a few times a second.
LEVEL_SAMPLE_STRIDE = 16
LEVEL_REPORT_INTERVAL = 0.1


# ------------------------------------------------------------
# TWITCH
# ------------------------------------------------------------

# Anonymous, read-only IRC login. Twitch allows this for reading chat
# with no OAuth token needed.
TWITCH_IRC_HOST = "irc.chat.twitch.tv"
TWITCH_IRC_PORT = 6667
TWITCH_ANON_NICK = f"justinfan{random.randint(10000, 99999)}"
