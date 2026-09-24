"""
Small shared widgets used across the panels.
"""

import tkinter as tk
from tkinter import ttk

from ui.theme import PALETTE, FONTS


class HintLabel(ttk.Label):
    """
    Muted helper text that wraps to its container instead of being
    clipped. Tk labels don't wrap on their own, and the width isn't
    known until layout runs, so wraplength is set from the actual
    width — with a guard so the reconfigure doesn't feed back into
    itself.
    """

    def __init__(self, parent, text):
        super().__init__(
            parent,
            text=text,
            style="Muted.TLabel",
            justify="left",
        )

        self._wrap = 0
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event):
        width = max(event.width - 4, 120)

        if abs(width - self._wrap) > 8:
            self._wrap = width
            self.configure(wraplength=width)


class Card(ttk.Frame):
    """
    A titled panel. Tk can't round corners, so a card is a hairline
    border plus generous padding, with the title sitting above it.
    """

    def __init__(self, parent, title=None, **kwargs):
        self.container = ttk.Frame(parent, style="Base.TFrame")

        if title:
            ttk.Label(
                self.container,
                text=title.upper(),
                style="SectionTitle.TLabel"
            ).pack(anchor="w", padx=2, pady=(0, 5))

        super().__init__(self.container, style="Card.TFrame", **kwargs)
        super().pack(fill="both", expand=True)

        self.body = ttk.Frame(self, style="TFrame")
        self.body.pack(fill="both", expand=True, padx=14, pady=12)

    def pack(self, **kwargs):
        self.container.pack(**kwargs)
        return self

    def grid(self, **kwargs):
        self.container.grid(**kwargs)
        return self


class StatusDot(ttk.Frame):
    """A coloured dot plus label, used for the status readouts."""

    _COLORS = {
        "offline": PALETTE["text_muted"],
        "connecting": PALETTE["warn"],
        "online": PALETTE["ok"],
        "error": PALETTE["err"],
    }

    def __init__(self, parent, label):
        super().__init__(parent, style="TFrame")

        self._canvas = tk.Canvas(
            self,
            width=10,
            height=10,
            highlightthickness=0,
            bg=PALETTE["bg_surface"],
        )
        self._canvas.pack(side="left", pady=(4, 0))
        self._dot = self._canvas.create_oval(
            1, 1, 9, 9,
            fill=self._COLORS["offline"],
            outline="",
        )

        ttk.Label(self, text=label).pack(side="left", padx=(8, 0))

        self._detail = ttk.Label(self, text="offline", style="Muted.TLabel")
        self._detail.pack(side="right")

    def set_status(self, status, detail=""):
        colour = self._COLORS.get(status, PALETTE["text_muted"])
        self._canvas.itemconfig(self._dot, fill=colour)

        text = detail or status

        # Keep long error text from stretching the panel.
        if len(text) > 34:
            text = text[:33] + "…"

        self._detail.configure(
            text=text,
            foreground=(
                PALETTE["err"] if status == "error" else PALETTE["text_muted"]
            ),
        )


class LabeledEntry(ttk.Frame):
    """Label above an entry, with an optional hint underneath."""

    def __init__(self, parent, label, hint=None, show=None, width=None):
        super().__init__(parent, style="TFrame")

        ttk.Label(self, text=label).pack(anchor="w")

        self.var = tk.StringVar()
        self.entry = ttk.Entry(
            self,
            textvariable=self.var,
            show=show,
            width=width or 20,
        )
        self.entry.pack(fill="x", pady=(4, 0))

        if hint:
            HintLabel(self, hint).pack(fill="x", pady=(3, 0))

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value or "")


class LabeledCombo(ttk.Frame):
    """Label above a read-only combobox."""

    def __init__(self, parent, label, values=(), hint=None):
        super().__init__(parent, style="TFrame")

        ttk.Label(self, text=label).pack(anchor="w")

        self.var = tk.StringVar()
        self.combo = ttk.Combobox(
            self,
            textvariable=self.var,
            values=list(values),
            state="readonly",
        )
        self.combo.pack(fill="x", pady=(4, 0))

        if hint:
            HintLabel(self, hint).pack(fill="x", pady=(3, 0))

    def set_values(self, values):
        self.combo.configure(values=list(values))

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value or "")


class ReconnectHint(ttk.Label):
    """
    Marks settings that GPT-Live fixes at session creation, so editing
    them mid-session visibly does nothing until reconnect.
    """

    def __init__(self, parent):
        super().__init__(
            parent,
            text="Applies on next connect",
            style="Muted.TLabel",
        )
