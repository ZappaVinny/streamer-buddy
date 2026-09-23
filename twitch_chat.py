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

import config
import state


_PRIVMSG_RE = re.compile(
    r"^:(?P<username>[^!]+)!.*PRIVMSG #\S+ :(?P<message>.*)$"
)


def parse_command(message):
    """
    Returns the text after the command prefix if this message is
    addressed to the assistant, otherwise None.

        "!bigj how's the run going?"  ->  "how's the run going?"
        "just chatting"               ->  None
        "!bigjoke lol"                ->  None  (prefix must be its own word)
        "!bigj"                       ->  None  (nothing to react to)
    """

    stripped = message.strip()
    prefix = config.CHAT_COMMAND

    if not stripped[:len(prefix)].lower() == prefix.lower():
        return None

    rest = stripped[len(prefix):]

    # The prefix has to be a whole word, so "!bigjoke" isn't a command.
    if rest and not rest[0].isspace():
        return None

    rest = rest.strip()

    # A bare "!bigj" carries nothing to react to.
    return rest or None


def twitch_chat_thread(on_chat_message):
    """
    Connects to Twitch IRC anonymously (read-only, no OAuth token
    needed) and streams messages from config.TWITCH_CHANNEL.

    on_chat_message(username, message) is called for every chat
    message. Runs on its own thread, so anything it touches on the
    asyncio side has to be handed over thread-safely.
    """

    print(f"Connecting to Twitch chat: #{config.TWITCH_CHANNEL}")

    while state.running:
        try:
            irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            irc.settimeout(30)
            irc.connect((config.TWITCH_IRC_HOST, config.TWITCH_IRC_PORT))

            irc.send(f"NICK {config.TWITCH_ANON_NICK}\r\n".encode("utf-8"))
            irc.send(f"JOIN #{config.TWITCH_CHANNEL}\r\n".encode("utf-8"))

            print(f"Connected to Twitch chat as {config.TWITCH_ANON_NICK}.")

            buffer = ""

            while state.running:
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
                    if line.startswith("PING"):
                        irc.send(
                            line.replace("PING", "PONG").encode("utf-8") + b"\r\n"
                        )
                        continue

                    match = _PRIVMSG_RE.match(line)

                    if not match:
                        continue

                    on_chat_message(
                        match.group("username"),
                        match.group("message")
                    )

        except Exception as error:
            print("Twitch chat connection error:", error)

        if state.running:
            print("Reconnecting to Twitch chat in 5s...")
            time.sleep(5)
