"""
Entry point: opens a GPT-Live voice session, listens to Twitch chat,
and keeps both running until Ctrl+C.

Every chat message is printed to the console and goes into the
session one of two ways: messages starting with config.CHAT_COMMAND
are sent in as something to react to out loud, and everything else is
batched in as quiet background context he can reference later.
"""

import asyncio
import threading

import state
import twitch_chat
from live_session import LiveSession


def start_twitch_listener(session):
    """
    Runs the Twitch listener on its own thread. The callback fires on
    that thread, so injection goes through the session's thread-safe
    path rather than touching the data channel directly.
    """

    def on_chat_message(username, message):
        command = twitch_chat.parse_command(message)

        session.log.chat(
            username,
            message,
            mode="react" if command else "context"
        )

        if command:
            session.inject_chat(username, command)
        else:
            session.add_chat_context(username, message)

    thread = threading.Thread(
        target=twitch_chat.twitch_chat_thread,
        args=(on_chat_message,),
        daemon=True
    )
    thread.start()

    return thread


async def main():
    session = LiveSession()

    await session.connect()

    start_twitch_listener(session)

    try:
        while state.running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        state.running = False
        await session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
