"""
Owns the engine: an asyncio event loop on its own thread, the live
session, and the Twitch listener.

This exists so the main thread is free for Tk. Everything aiortc
touches happens on the loop thread; callers from elsewhere (the UI,
the IRC thread) go through submit() or the session's threadsafe
helpers. Nothing here knows the UI exists — it reports by emitting
events.
"""

import asyncio
import threading

from core import credentials, twitch_chat
from core.live_session import LiveSession, SessionError
from core.events import (
    Status,
    StatusEvent,
    SystemEvent,
    ChatEvent,
    SESSION,
    CHAT,
)


class Runtime:
    def __init__(self, settings, emit):
        self.settings = settings
        self.session = None

        self._emit = emit
        self._loop = None
        self._thread = None
        self._ready = threading.Event()
        self._chat = None

    # --------------------------------------------------------
    # LOOP LIFECYCLE
    # --------------------------------------------------------

    def start(self):
        """Starts the asyncio thread. Returns once the loop is live."""

        if self._thread:
            return

        self._thread = threading.Thread(
            target=self._run_loop,
            name="engine",
            daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def shutdown(self):
        """Disconnects and stops the loop. Safe to call more than once."""

        if not self._loop:
            return

        if self.session:
            self.disconnect(wait=True)

        self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5)

        self._thread = None
        self._loop = None

    def submit(self, coro):
        """
        Schedules a coroutine on the loop from any thread. Returns a
        concurrent.futures.Future.
        """

        if not self._loop:
            raise RuntimeError("Engine is not running")

        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    @property
    def connected(self):
        return self.session is not None

    def connect(self):
        """
        Starts a session. Non-blocking; progress arrives as status
        events.
        """

        if self.session:
            return

        return self.submit(self._connect())

    async def _connect(self):
        api_key = credentials.get_api_key()

        if not api_key:
            self._emit(StatusEvent(
                SESSION,
                Status.ERROR,
                "No API key. Add one in Settings, or set OPENAI_API_KEY."
            ))
            return

        session = LiveSession(self.settings, self._emit)

        try:
            await session.connect(api_key)
        except SessionError as error:
            self._emit(StatusEvent(SESSION, Status.ERROR, str(error)))
            await self._safe_close(session)
            return
        except Exception as error:
            self._emit(StatusEvent(SESSION, Status.ERROR, repr(error)))
            await self._safe_close(session)
            return

        self.session = session
        self._start_chat()

    async def _safe_close(self, session):
        try:
            await session.close()
        except Exception:
            pass

    def disconnect(self, wait=False):
        if not self.session:
            return

        self._stop_chat()

        future = self.submit(self._disconnect())

        if wait:
            try:
                future.result(timeout=10)
            except Exception:
                pass

    async def _disconnect(self):
        session, self.session = self.session, None

        if session:
            await self._safe_close(session)

    # --------------------------------------------------------
    # TWITCH
    # --------------------------------------------------------

    def _start_chat(self):
        if self._chat:
            return

        self._chat = twitch_chat.TwitchChatListener(
            self.settings,
            self._emit,
            self._on_chat_message
        )
        self._chat.start()

    def _stop_chat(self):
        if not self._chat:
            return

        chat, self._chat = self._chat, None
        chat.stop()

    def restart_chat(self):
        """Used when the channel changes while connected."""

        self._stop_chat()

        if self.session:
            self._start_chat()

    def _on_chat_message(self, username, message):
        """
        Runs on the IRC thread. Injection uses the session's
        threadsafe paths, so nothing here touches aiortc directly.
        """

        command = twitch_chat.parse_command(
            message,
            self.settings.chat_command
        )

        self._emit(ChatEvent(
            username=username,
            message=message,
            mode="react" if command else "context"
        ))

        session = self.session

        if not session:
            return

        if command:
            session.inject_chat(username, command)
        else:
            session.add_chat_context(username, message)
