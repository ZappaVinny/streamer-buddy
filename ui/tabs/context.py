"""
Context Management tab: how much stream chat gets fed to the model,
and how full the session's context window is.

The usage numbers come from session.usage.updated events the session
already receives.
"""

import tkinter as tk
from tkinter import ttk

from ui.widgets import Card, HintLabel


# $ per minute of voice, used to turn session seconds into a rough
# running cost.
COST_PER_MINUTE = 0.05


class ContextTab(ttk.Frame):
    def __init__(self, parent, settings, on_change):
        super().__init__(parent, style="TFrame")

        self._settings = settings
        self._on_change = on_change

        inner = ttk.Frame(self, style="Base.TFrame")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_usage(inner)
        self._build_knobs(inner)

    # --------------------------------------------------------

    def _build_usage(self, parent):
        card = Card(parent, title="Session usage")
        card.pack(fill="x", pady=(0, 14))

        ttk.Label(card.body, text="Context window").pack(anchor="w")

        self._context_meter = ttk.Progressbar(
            card.body,
            style="Meter.Horizontal.TProgressbar",
            maximum=100,
        )
        self._context_meter.pack(fill="x", pady=(4, 0))

        self._context_label = ttk.Label(
            card.body, text="—", style="Muted.TLabel"
        )
        self._context_label.pack(anchor="w", pady=(4, 0))

        ttk.Separator(card.body, orient="horizontal").pack(
            fill="x", pady=(12, 10)
        )

        self._duration_label = ttk.Label(card.body, text="Not connected")
        self._duration_label.pack(anchor="w")

        self._cost_label = ttk.Label(
            card.body, text="", style="Muted.TLabel"
        )
        self._cost_label.pack(anchor="w", pady=(3, 0))

    def _build_knobs(self, parent):
        card = Card(parent, title="Chat context")
        card.pack(fill="x")

        HintLabel(
            card.body,
            "Chat that isn't addressed to the assistant is batched "
            "and sent as silent background context.",
        ).pack(fill="x", pady=(0, 12))

        self._flush = self._spin(
            card.body,
            "Send a batch every (seconds)",
            1, 300,
            self._settings.context_flush_seconds,
            "Longer intervals interrupt the conversation less often.",
        )

        self._max_messages = self._spin(
            card.body,
            "Max messages per batch",
            1, 30,
            self._settings.context_max_messages,
            "Batches are capped to stay under the 500-token limit.",
        )

        self._max_chars = self._spin(
            card.body,
            "Max characters per message",
            20, 500,
            self._settings.context_max_message_chars,
            None,
        )

    def _spin(self, parent, label, low, high, value, hint):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 0))

        var = tk.IntVar(value=value)
        spin = ttk.Spinbox(
            parent,
            from_=low,
            to=high,
            textvariable=var,
            width=8,
            command=self._save,
        )
        spin.pack(anchor="w", pady=(4, 0))
        spin.bind("<FocusOut>", lambda _: self._save())

        if hint:
            HintLabel(parent, hint).pack(fill="x", pady=(3, 0))

        return var

    def _save(self):
        try:
            self._settings.context_flush_seconds = int(self._flush.get())
            self._settings.context_max_messages = int(self._max_messages.get())
            self._settings.context_max_message_chars = int(
                self._max_chars.get()
            )
        except (tk.TclError, ValueError):
            # Mid-edit garbage in a spinbox; ignore until it's valid.
            return

        self._settings.save()
        self._on_change("context")

    # --------------------------------------------------------

    def set_usage(self, seconds, context_ratio):
        self._context_meter.configure(value=context_ratio * 100)
        self._context_label.configure(text=f"{context_ratio:.1%} used")

        minutes, secs = divmod(int(seconds), 60)
        self._duration_label.configure(
            text=f"Session length: {minutes}m {secs:02d}s"
        )
        self._cost_label.configure(
            text=f"≈ ${seconds / 60 * COST_PER_MINUTE:.2f} of voice time"
        )

    def reset_usage(self):
        self._context_meter.configure(value=0)
        self._context_label.configure(text="—")
        self._duration_label.configure(text="Not connected")
        self._cost_label.configure(text="")
