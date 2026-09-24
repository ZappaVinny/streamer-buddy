"""
General tab: identity, voice, credentials, prompts, and the Twitch
chat config.

Per the wireframe, Twitch config sits below the general config in this
same tab.
"""

from tkinter import ttk

from core import constants
from ui.widgets import Card, LabeledEntry, LabeledCombo, ReconnectHint
from ui.dialogs.api_key import ApiKeyDialog
from ui.dialogs.prompts import PromptsDialog


class GeneralTab(ttk.Frame):
    def __init__(self, parent, settings, on_change):
        super().__init__(parent, style="TFrame")

        self._settings = settings
        self._on_change = on_change

        inner = ttk.Frame(self, style="Base.TFrame")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_general(inner)
        self._build_twitch(inner)

    # --------------------------------------------------------

    def _build_general(self, parent):
        card = Card(parent, title="Assistant")
        card.pack(fill="x", pady=(0, 14))

        self._name = LabeledEntry(
            card.body,
            "Assistant name",
            hint="Shown in the transcript.",
        )
        self._name.set(self._settings.assistant_name)
        self._name.pack(fill="x")
        self._name.var.trace_add("write", lambda *_: self._save())

        self._voice = LabeledCombo(
            card.body,
            "Voice",
            values=constants.VOICES,
        )
        self._voice.set(self._settings.voice)
        self._voice.pack(fill="x", pady=(12, 0))
        self._voice.combo.bind("<<ComboboxSelected>>", lambda _: self._save())
        ReconnectHint(card.body).pack(anchor="w", pady=(3, 0))

        buttons = ttk.Frame(card.body, style="TFrame")
        buttons.pack(fill="x", pady=(14, 0))

        ttk.Button(
            buttons,
            text="API key…",
            command=lambda: ApiKeyDialog(self.winfo_toplevel()),
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Prompts & personality…",
            command=self._open_prompts,
        ).pack(side="left", padx=(8, 0))

    def _build_twitch(self, parent):
        card = Card(parent, title="Twitch chat")
        card.pack(fill="x")

        self._channel = LabeledEntry(
            card.body,
            "Target channel",
            hint="Channel name only — no # and no twitch.tv/ prefix.",
        )
        self._channel.set(self._settings.twitch_channel)
        self._channel.pack(fill="x")
        self._channel.var.trace_add("write", lambda *_: self._save())

        self._command = LabeledEntry(
            card.body,
            "Chat command",
            hint=(
                "Messages starting with this get answered out loud. "
                "Everything else becomes silent context."
            ),
        )
        self._command.set(self._settings.chat_command)
        self._command.pack(fill="x", pady=(12, 0))
        self._command.var.trace_add("write", lambda *_: self._save())

    # --------------------------------------------------------

    def _open_prompts(self):
        PromptsDialog(
            self.winfo_toplevel(),
            self._settings,
            on_save=lambda: self._on_change("prompts"),
        )

    def _save(self):
        previous_channel = self._settings.twitch_channel

        self._settings.assistant_name = self._name.get().strip() or "Name"
        self._settings.voice = self._voice.get() or self._settings.voice
        self._settings.twitch_channel = self._channel.get().strip()
        self._settings.chat_command = self._command.get().strip() or "!name"
        self._settings.save()

        if self._settings.twitch_channel != previous_channel:
            self._on_change("twitch_channel")
        else:
            self._on_change("general")
