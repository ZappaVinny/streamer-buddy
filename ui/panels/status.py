"""
The status panel: connection state for each moving part, plus the
Connect button.

The button lives here because this is where session state is already
shown, and the wireframe has no other obvious home for it.
"""

from tkinter import ttk

from core import events
from ui.widgets import Card, StatusDot


class StatusPanel(Card):
    def __init__(self, parent, on_connect, on_disconnect):
        super().__init__(parent, title="Status")

        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._connected = False

        self.dots = {}

        for component, label in (
            (events.SESSION, "Live session"),
            (events.CHAT, "Twitch chat"),
            (events.MIC, "Microphone"),
            (events.SPEAKER, "Speaker"),
        ):
            dot = StatusDot(self.body, label)
            dot.pack(fill="x", pady=3)
            self.dots[component] = dot

        ttk.Separator(self.body, orient="horizontal").pack(
            fill="x", pady=(12, 10)
        )

        self._button = ttk.Button(
            self.body,
            text="Connect",
            style="Accent.TButton",
            command=self._toggle,
        )
        self._button.pack(fill="x")

    def _toggle(self):
        if self._connected:
            self._on_disconnect()
        else:
            self._on_connect()

    def set_status(self, component, status, detail=""):
        dot = self.dots.get(component)

        if dot:
            dot.set_status(status, detail)

        if component == events.SESSION:
            self._sync_button(status)

    def _sync_button(self, status):
        if status == events.Status.CONNECTING.value:
            self._button.configure(text="Connecting…", state="disabled")
            return

        self._connected = status == events.Status.ONLINE.value

        self._button.configure(
            state="normal",
            text="Disconnect" if self._connected else "Connect",
            style="TButton" if self._connected else "Accent.TButton",
        )
