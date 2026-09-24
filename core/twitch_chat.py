"""
Twitch chat listener: reads a channel's chat over anonymous IRC and
hands every message to a callback.

Deliberately knows nothing about GPT-Live. It reports what was said
and offers a helper for spotting the command prefix; deciding what to
do with either is the caller's job.
"""

import re
import time
import socket
import threading

from core import constants
from core.events import Status, StatusEvent, CHAT


_PRIVMSG_RE = re.compile(
    r"^:(?P<username>[^!]+)!.*PRIVMSG #\S+ :(?P<message>.*)$"
)


def parse_command(message, prefix):
    """
    Returns the text after the command prefix if this message is
    addressed to the assistant, otherwise None.

        "!name how's the run going?"  ->  "how's the run going?"
        "just chatting"               ->  None
        "!namefoo lol"                ->  None  (prefix must be its own word)
        "!name"                       ->  None  (nothing to react to)
    """

    stripped = message.strip()

    if not stripped[:len(prefix)].lower() == prefix.lower():
        return None

    rest = stripped[len(prefix):]

    # The prefix has to be a whole word, so "!namefoo" isn't a command.
    if rest and not rest[0].isspace():
        return None

    return rest.strip() or None


class TwitchChatListener:
    """
    Runs the IRC connection on its own thread until stop() is called.

    The callback fires on that thread, so anything it touches on the
    asyncio or UI side has to be handed over thread-safely.
    """

    def __init__(self, settings, emit, on_chat_message):
        self.settings = settings

        self._emit = emit
        self._on_chat_message = on_chat_message
        self._running = False
        self._thread = None
        self._socket = None

    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

        # Shutting the socket down unblocks recv() immediately rather
        # than waiting out its timeout.
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        if self._thread:
            self._thread.join(timeout=3)

        self._emit(StatusEvent(CHAT, Status.OFFLINE))

    def _run(self):
        while self._running:
            try:
                self._emit(StatusEvent(CHAT, Status.CONNECTING))
                self._connect_and_listen()
            except Exception as error:
                if self._running:
                    self._emit(StatusEvent(CHAT, Status.ERROR, str(error)))

            if self._running:
                time.sleep(5)

    def _connect_and_listen(self):
        channel = self.settings.twitch_channel.strip().lstrip("#").lower()

        if not channel:
            self._emit(StatusEvent(CHAT, Status.ERROR, "No channel set"))
            self._running = False
            return

        irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        irc.settimeout(30)
        self._socket = irc

        try:
            irc.connect((constants.TWITCH_IRC_HOST, constants.TWITCH_IRC_PORT))

            irc.send(f"NICK {constants.TWITCH_ANON_NICK}\r\n".encode("utf-8"))
            irc.send(f"JOIN #{channel}\r\n".encode("utf-8"))

            self._emit(StatusEvent(CHAT, Status.ONLINE, f"#{channel}"))

            buffer = ""

            while self._running:
                try:
                    data = irc.recv(4096).decode("utf-8", errors="ignore")
                except socket.timeout:
                    continue

                if not data:
                    break

                buffer += data
                lines = buffer.split("\r\n")
                buffer = lines.pop()

                for line in lines:
                    self._handle_line(irc, line)
        finally:
            self._socket = None

            try:
                irc.close()
            except OSError:
                pass

    def _handle_line(self, irc, line):
        if line.startswith("PING"):
            irc.send(line.replace("PING", "PONG").encode("utf-8") + b"\r\n")
            return

        match = _PRIVMSG_RE.match(line)

        if not match:
            return

        self._on_chat_message(
            match.group("username"),
            match.group("message")
        )
