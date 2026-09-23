"""
The GPT-Live (gpt-live-1) session: WebRTC transport, session creation,
and the JSON event channel.

gpt-live-1 only accepts transport.type "webrtc" when creating a
session — a plain WebSocket transport is rejected with invalid_value
on transport.type — so a headless client needs a real WebRTC stack
(aiortc) rather than just streaming PCM over a socket.

Connection flow:
  1. Build an RTCPeerConnection, add the mic track, open the
     "oai-events" data channel, create an SDP offer.
  2. POST that offer to /v1/live/sessions with the session config.
     The response carries the session ID and an SDP answer.
  3. Apply the answer, then wait for "session.started".
"""

import json
import time
import asyncio
import threading
import traceback
import urllib.error
import urllib.request

from aiortc import RTCPeerConnection, RTCSessionDescription

import config
import transcript
from audio_bridge import MicrophoneStreamTrack, SpeakerPlayer
from transcript import TranscriptLogger


SESSIONS_URL = "https://api.openai.com/v1/live/sessions"


def _create_session(offer_sdp):
    """
    POST /v1/live/sessions to start the session and exchange SDP.

    delegation: {"type": "client"} keeps everything in this process —
    the alternative ("responses" delegation) wires in a separate
    backend model for reasoning and tool use, which this app doesn't
    need. audio.format is deliberately omitted: WebRTC negotiates the
    wire format through SDP.
    """

    instructions = f"{config.PERSONALITY_PROMPT}\n\n{config.SYSTEM_PROMPT}"

    body = json.dumps({
        "session": {
            "model": config.MODEL,
            "instructions": instructions,
            "audio": {
                "output": {
                    "voice": config.VOICE
                }
            },
            "delegation": {
                "type": "client"
            }
        },
        "transport": {
            "type": "webrtc",
            "sdp": offer_sdp
        }
    }).encode("utf-8")

    request = urllib.request.Request(
        SESSIONS_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        print("Session creation failed:", error.code)
        print(error.read().decode("utf-8"))
        raise


class LiveSession:
    """
    One live voice conversation with gpt-live-1.

    Owns the peer connection, the mic/speaker bridge, and the
    "oai-events" data channel that carries JSON events in both
    directions.
    """

    def __init__(self):
        self.session_id = None
        self.log = TranscriptLogger()

        self._pc = RTCPeerConnection()
        self._mic = MicrophoneStreamTrack()
        self._speaker = SpeakerPlayer()
        self._events = None
        self._started = asyncio.Event()
        self._idle_flusher = None
        self._loop = None
        self._event_count = 0

        # Ordinary chat waiting to be sent as background context.
        # Appended from the Twitch thread, drained on the event loop.
        self._chat_buffer = []
        self._chat_lock = threading.Lock()
        self._chat_buffered_at = None
        self._chat_flusher = None

    def send_event(self, event):
        """
        Send a JSON event over the data channel.

        Must be called on the asyncio event loop thread — aiortc's
        data channel is not thread-safe. Anything running on another
        thread has to go through send_event_threadsafe().
        """

        if self._events and self._events.readyState == "open":
            self._events.send(json.dumps(event))

    def send_event_threadsafe(self, event):
        """
        send_event() for callers on other threads (the Twitch IRC
        listener), handing the work to the event loop instead of
        touching the data channel directly.
        """

        if self._loop:
            self._loop.call_soon_threadsafe(self.send_event, event)

    def inject_chat(self, username, message):
        """
        Push a viewer's chat message into the conversation as
        something to respond to out loud.

        Uses session.commentary.append (the "speakable updates"
        channel) rather than session.instructions.append, because
        chat is untrusted input and the docs warn against copying
        untrusted text into instructions. The message is quoted and
        attributed so it reads as a third party talking, not as
        something for the model to recite.
        """

        self._event_count += 1

        self.send_event_threadsafe({
            "type": "session.commentary.append",
            "event_id": f"chat_{self._event_count}",
            "delegation_id": None,
            "content": (
                f"Viewer \"{username}\" in the stream chat (not the "
                f"streamer you're talking to) is talking to you:\n"
                f"\"{message}\"\n"
                f"Fire back at {username} out loud now — by name, "
                f"with an opinion. Don't be polite about it."
            )
        })

    def add_chat_context(self, username, message):
        """
        Buffer an ordinary chat message as background context.

        Goes out via session.thinking.append (the "quiet context"
        channel), so it's remembered and available to reference but
        doesn't make him say anything. That way if the streamer
        brings up something chat was talking about, he already has it.

        Safe to call from the Twitch thread — this only touches the
        buffer; the sending happens on the event loop.
        """

        trimmed = message.strip()[:config.CHAT_CONTEXT_MAX_MESSAGE_CHARS]

        if not trimmed:
            return

        with self._chat_lock:
            self._chat_buffer.append(f"{username}: {trimmed}")

            if self._chat_buffered_at is None:
                self._chat_buffered_at = time.monotonic()

    def _flush_chat_context(self):
        """Send buffered chat as one digest. Event loop only."""

        with self._chat_lock:
            if not self._chat_buffer:
                return

            # Only take a capped batch: a burst of chat has to go out
            # across several digests rather than one oversized append
            # that busts the 500-token limit.
            lines = self._chat_buffer[:config.CHAT_CONTEXT_MAX_MESSAGES]
            del self._chat_buffer[:config.CHAT_CONTEXT_MAX_MESSAGES]

            self._chat_buffered_at = (
                time.monotonic() if self._chat_buffer else None
            )

        self._event_count += 1

        self.send_event({
            "type": "session.thinking.append",
            "event_id": f"chat_context_{self._event_count}",
            "delegation_id": None,
            "content": (
                "BACKGROUND STREAM CHAT — SAY NOTHING ABOUT THIS NOW.\n"
                "Viewers watching the stream, not the streamer you're "
                "talking to, and not addressed to you. Take it in "
                "quietly and bank it as ammunition — don't reply to "
                "it, don't read it out, don't let it interrupt you. "
                "Use it later, when it's funny or the streamer brings "
                "the topic up.\n\n"
                + "\n".join(lines)
            )
        })

    async def _run_chat_context_flusher(self):
        """
        Sends the buffered chat digest once it's either old enough or
        big enough, so a quiet chat still gets through promptly and a
        busy one doesn't spam the session.
        """

        while True:
            await asyncio.sleep(1)

            with self._chat_lock:
                count = len(self._chat_buffer)

                stale = (
                    self._chat_buffered_at is not None
                    and time.monotonic() - self._chat_buffered_at
                    >= config.CHAT_CONTEXT_FLUSH_SECONDS
                )

            if count >= config.CHAT_CONTEXT_MAX_MESSAGES or stale:
                self._flush_chat_context()

    async def connect(self):
        if not config.OPENAI_API_KEY:
            raise SystemExit(
                "Set the OPENAI_API_KEY environment variable before running."
            )

        # Captured so other threads can hand events back to the loop.
        self._loop = asyncio.get_running_loop()

        self._pc.addTrack(self._mic)
        self._events = self._pc.createDataChannel("oai-events")

        self._events.on("message")(self._on_message)
        self._pc.on("track")(self._on_track)

        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)

        # Wait for ICE gathering before sending the offer, same as
        # OpenAI's own example client does.
        while self._pc.iceGatheringState != "complete":
            await asyncio.sleep(0.1)

        self.log.system("Creating GPT-Live session...")
        result = _create_session(self._pc.localDescription.sdp)

        self.session_id = result["session"]["id"]
        self.log.system(f"Session created: {self.session_id}")

        await self._pc.setRemoteDescription(
            RTCSessionDescription(
                sdp=result["transport"]["sdp"],
                type="answer"
            )
        )

        self._idle_flusher = asyncio.ensure_future(
            self.log.run_idle_flusher()
        )
        self._chat_flusher = asyncio.ensure_future(
            self._run_chat_context_flusher()
        )

        await self._started.wait()

    async def close(self):
        self.send_event({"type": "session.close"})
        await asyncio.sleep(1)

        if self._idle_flusher:
            self._idle_flusher.cancel()

        if self._chat_flusher:
            self._chat_flusher.cancel()

        self.log.flush()

        self._mic.stop()
        self._speaker.stop()
        await self._pc.close()

    # --------------------------------------------------------
    # EVENT HANDLING
    # --------------------------------------------------------

    def _on_message(self, message):
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            return

        event_type = event.get("type")

        if event_type == "session.started":
            self.log.system("Session started — talk normally.")
            self._started.set()

        elif event_type == "session.input_transcript.delta":
            self.log.add(
                transcript.YOU,
                event.get("delta", ""),
                start_ms=event.get("start_ms"),
                end_ms=event.get("end_ms")
            )

        elif event_type == "session.output_transcript.delta":
            self.log.add(
                transcript.ASSISTANT,
                event.get("delta", ""),
                start_ms=event.get("start_ms"),
                end_ms=event.get("end_ms")
            )

        elif event_type == "session.closed":
            self.log.system(f"Session closed. Usage: {event.get('usage')}")

        elif event_type == "error":
            self.log.system("GPT-LIVE ERROR:")
            print(json.dumps(event, indent=2))

    def _on_track(self, track):
        if track.kind != "audio":
            return

        async def play():
            try:
                await self._speaker.consume(track)
            except Exception:
                # Without this the task dies silently and playback
                # just stops with no explanation.
                self.log.system("Audio playback task crashed:")
                traceback.print_exc()

        asyncio.ensure_future(play())
