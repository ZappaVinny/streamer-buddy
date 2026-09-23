"""
Small shared runtime flag so every thread (mic, speaker, Twitch
listener, websocket) can agree on when to shut down, without the
modules that own those threads needing to import each other.
"""

running = True
