"""
The application window.

Threading contract, which everything here depends on:

  - Tk owns the main thread. Only main-thread code touches widgets.
  - The engine owns its own asyncio thread. Only that thread touches
    aiortc.
  - Engine events arrive on a queue from whichever thread produced
    them, and are drained here on a timer, so rendering always happens
    on the main thread.
  - UI actions reach the engine through Runtime, which hands work off
    to the loop.
"""

import queue
import tkinter as tk
from tkinter import ttk

from core import constants
from core.events import (
    ChatEvent,
    LevelEvent,
    SpeechEvent,
    Status,
    StatusEvent,
    SystemEvent,
    UsageEvent,
    MIC,
    SESSION,
)
from core.runtime import Runtime
from core.settings import Settings

from ui import theme
from ui.panels.transcript import TranscriptPanel
from ui.panels.settings import SettingsPanel


# How often the UI drains engine events. 20Hz is well under the rate
# transcript deltas arrive at, and cheap enough to be invisible.
PUMP_INTERVAL_MS = 50


class App:
    def __init__(self):
        self.settings = Settings.load()

        # Every thread pushes here; only the main thread reads.
        self._events = queue.Queue()

        self.runtime = Runtime(self.settings, self._events.put)

        self.root = tk.Tk()
        self.root.title(constants.APP_NAME)
        self.root.geometry("1180x760")
        self.root.minsize(900, 600)

        theme.apply(self.root)

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --------------------------------------------------------
    # LAYOUT
    # --------------------------------------------------------

    def _build(self):
        container = ttk.Frame(self.root, style="Base.TFrame")
        container.pack(fill="both", expand=True, padx=16, pady=16)

        container.columnconfigure(0, weight=3, uniform="cols")
        container.columnconfigure(1, weight=2, uniform="cols")
        container.rowconfigure(0, weight=1)

        self.transcript = TranscriptPanel(container)
        self.transcript.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        self.settings_panel = SettingsPanel(
            container,
            self.settings,
            on_connect=self._connect,
            on_disconnect=self._disconnect,
            on_change=self._on_setting_changed,
        )
        self.settings_panel.grid(row=0, column=1, sticky="nsew")

    # --------------------------------------------------------
    # ACTIONS
    # --------------------------------------------------------

    def _connect(self):
        self.settings_panel.context.reset_usage()
        self.runtime.connect()

    def _disconnect(self):
        self.runtime.disconnect()
        self.settings_panel.audio.set_meter_hint(
            "Connect a session to see live input."
        )
        self.settings_panel.audio.set_level(0)

    def _on_setting_changed(self, what):
        """
        Settings save themselves; this only handles the ones that need
        something restarted to take effect.
        """

        if what == "twitch_channel" and self.runtime.connected:
            self.runtime.restart_chat()

    # --------------------------------------------------------
    # EVENT PUMP
    # --------------------------------------------------------

    def _pump(self):
        try:
            while True:
                self._handle(self._events.get_nowait())
        except queue.Empty:
            pass

        self.root.after(PUMP_INTERVAL_MS, self._pump)

    def _handle(self, event):
        if isinstance(event, SpeechEvent):
            self.transcript.add_speech(
                event.speaker,
                event.text,
                self.settings.assistant_name,
            )

        elif isinstance(event, ChatEvent):
            self.transcript.add_chat(
                event.username,
                event.message,
                event.mode,
            )

        elif isinstance(event, SystemEvent):
            self.transcript.add_system(event.message)

        elif isinstance(event, StatusEvent):
            self.settings_panel.status.set_status(
                event.component,
                event.status.value,
                event.detail,
            )

            if event.status == Status.ERROR:
                self.transcript.add_system(
                    f"{event.component}: {event.detail}",
                    is_error=True,
                )

            if event.component == MIC and event.status == Status.ONLINE:
                self.settings_panel.audio.set_meter_hint("Listening.")

            if event.component == SESSION and event.status == Status.OFFLINE:
                self.settings_panel.audio.set_level(0)

        elif isinstance(event, UsageEvent):
            self.settings_panel.context.set_usage(
                event.seconds,
                event.context_ratio,
            )

        elif isinstance(event, LevelEvent):
            self.settings_panel.audio.set_level(event.peak)

    # --------------------------------------------------------
    # LIFECYCLE
    # --------------------------------------------------------

    def _on_close(self):
        self.transcript.add_system("Shutting down…")
        self.root.update_idletasks()

        self.runtime.shutdown()
        self.root.destroy()

    def run(self):
        self.runtime.start()
        self.transcript.add_system(
            f"{constants.APP_NAME} ready. Press Connect to start a session."
        )

        self._pump()
        self.root.mainloop()
