"""
The left pane: the running conversation.

A read-only Text widget with one tag per line kind, carrying over the
colour scheme the console used.
"""

import tkinter as tk
from tkinter import ttk

from core import transcript
from ui.theme import PALETTE, FONTS


class TranscriptPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Base.TFrame")

        ttk.Label(
            self,
            text="TRANSCRIPT",
            style="SectionTitle.TLabel"
        ).pack(anchor="w", padx=2, pady=(0, 5))

        frame = ttk.Frame(self, style="Card.TFrame")
        frame.pack(fill="both", expand=True)

        self._text = tk.Text(
            frame,
            wrap="word",
            bg=PALETTE["bg_surface"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["text"],
            selectbackground=PALETTE["bg_active"],
            selectforeground=PALETTE["text"],
            font=FONTS["mono"],
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            padx=14,
            pady=12,
            spacing1=2,
            spacing3=4,
            state="disabled",
            cursor="arrow",
            # Speaker labels sit in their own column via a tab stop.
            tabs=(104,),
        )
        self._text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self._text.yview,
            style="Vertical.TScrollbar",
        )
        scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=2)
        self._text.configure(yscrollcommand=scrollbar.set)

        self._text.tag_configure("label", foreground=PALETTE["text_muted"])

        # lmargin2 is a tag option (not a widget one) and keeps wrapped
        # lines aligned under the text column instead of running back
        # under the speaker label.
        for tag, colour in (
            ("you", PALETTE["you"]),
            ("assistant", PALETTE["assistant"]),
            ("chat", PALETTE["chat"]),
            ("chat_react", PALETTE["text"]),
            ("system", PALETTE["system"]),
            ("error", PALETTE["err"]),
        ):
            self._text.tag_configure(tag, foreground=colour, lmargin2=104)

    # --------------------------------------------------------

    def _append(self, label, text, tag):
        """
        Lines are laid out with a tab stop rather than a padded label,
        so a name longer than the column pushes its text across
        instead of being cut off.
        """

        self._text.configure(state="normal")

        self._text.insert("end", f"{label}\t", "label")
        self._text.insert("end", f"{text}\n", tag)

        self._text.configure(state="disabled")
        self._text.see("end")

    def add_speech(self, speaker, text, assistant_name):
        label = "YOU" if speaker == transcript.YOU else assistant_name
        tag = "you" if speaker == transcript.YOU else "assistant"

        self._append(label, text, tag)

    def add_chat(self, username, message, mode):
        # Messages sent in for a reply are shown brighter, so they
        # stand out from the background chatter.
        marker = "→CHAT" if mode == "react" else "·CHAT"
        tag = "chat_react" if mode == "react" else "chat"

        self._append(marker, f"{username}: {message}", tag)

    def add_system(self, message, is_error=False):
        self._append("··", message, "error" if is_error else "system")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
