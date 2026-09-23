import os
import random


# ------------------------------------------------------------
# GPT-LIVE
# ------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

MODEL = "gpt-live-1"

# Shown as the speaker label in the console transcript.
ASSISTANT_NAME = "Name"

# Voice for session.audio.output.voice. "marin" and "cedar" are the
# documented recommendations for GPT-Live; if this value is rejected
# the session-creation error will say so.
VOICE = "ballad"


# ------------------------------------------------------------
# AUDIO
# ------------------------------------------------------------

# WebRTC negotiates the wire format through SDP, so this is only what
# we capture/play locally. 48kHz is Opus's native rate, which keeps
# the mic path free of resampling.
SAMPLE_RATE = 48000
CHANNELS = 1
BLOCK_SIZE = 960  # 20 ms at 48 kHz — one Opus frame


# ------------------------------------------------------------
# TWITCH CHAT
# ------------------------------------------------------------

# Twitch channel to listen to, lowercase, without the leading #
# (e.g. the channel at twitch.tv/some_streamer is just "some_streamer").
TWITCH_CHANNEL = "channel"

# Anonymous, read-only IRC login. Twitch allows this for reading
# chat with no OAuth token needed.
TWITCH_IRC_HOST = "irc.chat.twitch.tv"
TWITCH_IRC_PORT = 6667
TWITCH_ANON_NICK = f"justinfan{random.randint(10000, 99999)}"

# Every chat message is printed to the console. Messages starting
# with this prefix are sent in as something to react to out loud;
# everything else goes in as quiet background context.
CHAT_COMMAND = "!name"

# Ordinary chat is batched into periodic digests instead of one event
# per message — a busy chat would otherwise flood the session and
# burn through the context window. Context appends are capped at 500
# tokens each, which is what these limits are sized against.
# Each digest is a fresh opportunity for him to blurt something out,
# so sending them less often is the main lever if he keeps reacting
# to background chat despite being told not to.
CHAT_CONTEXT_FLUSH_SECONDS = 15
CHAT_CONTEXT_MAX_MESSAGES = 8
CHAT_CONTEXT_MAX_MESSAGE_CHARS = 180


# ------------------------------------------------------------
# PERSONALITY / VOICE STYLE
# ------------------------------------------------------------

# There's no separate "accent" field in the API — accent, tone,
# energy, etc. are steered entirely through instructions text like
# this. Edit freely; it's merged into the model instructions
# alongside SYSTEM_PROMPT below.
PERSONALITY_PROMPT = """
PERSONALITYU HERE
"""


# ------------------------------------------------------------
# SYSTEM PROMPT
# ------------------------------------------------------------

SYSTEM_PROMPT = """
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
