"""
Prompt editor: personality and system prompt.

Both are fixed when the session is created, so edits here take effect
on the next connect — which the dialog says out loud.
"""

import tkinter as tk
from tkinter import ttk

from ui.theme import PALETTE, FONTS


class PromptsDialog(tk.Toplevel):
    def __init__(self, parent, settings, on_save):
        super().__init__(parent)

        self.title("Prompts & Personality")
        self.configure(bg=PALETTE["bg_base"])
        self.transient(parent)
        self.grab_set()
        self.geometry("720x620")
        self.minsize(520, 420)

        self._settings = settings
        self._on_save = on_save

        body = ttk.Frame(self, style="Base.TFrame")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        ttk.Label(
            body,
            text=(
                "The personality defines who the assistant is. The system "
                "prompt defines the rules of the stream — who's talking and "
                "how chat is handled. Both are sent together when a session "
                "starts, so changes apply on the next connect."
            ),
            style="Muted.TLabel",
            wraplength=660,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        # Packed before the notebook and anchored to the bottom: pack
        # squeezes whatever it places last, and the text editors ask
        # for more room than the window has, which otherwise crushes
        # these buttons down to an invisible sliver.
        buttons = ttk.Frame(body, style="Base.TFrame")
        buttons.pack(side="bottom", fill="x", pady=(14, 0))

        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(
            side="right"
        )
        ttk.Button(
            buttons,
            text="Save",
            style="Accent.TButton",
            command=self._save,
        ).pack(side="right", padx=(0, 8))

        notebook = ttk.Notebook(body)
        notebook.pack(side="top", fill="both", expand=True)

        self._personality = self._editor(notebook, "Personality")
        self._system = self._editor(notebook, "System prompt")

        self._personality.insert("1.0", settings.personality_prompt.strip())
        self._system.insert("1.0", settings.system_prompt.strip())

    def _editor(self, notebook, title):
        frame = ttk.Frame(notebook, style="TFrame")
        notebook.add(frame, text=title)

        text = tk.Text(
            frame,
            # Small requested size; the pack geometry gives it the
            # real space. Left at the default 80x24 it demands more
            # than the window has and starves everything else.
            width=40,
            height=10,
            wrap="word",
            bg=PALETTE["bg_surface"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["text"],
            selectbackground=PALETTE["bg_active"],
            font=FONTS["mono"],
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            padx=12,
            pady=10,
            undo=True,
        )
        text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=text.yview,
            style="Vertical.TScrollbar",
        )
        scrollbar.pack(side="right", fill="y")
        text.configure(yscrollcommand=scrollbar.set)

        return text

    def _save(self):
        self._settings.personality_prompt = self._personality.get(
            "1.0", "end"
        ).strip()
        self._settings.system_prompt = self._system.get("1.0", "end").strip()
        self._settings.save()

        self._on_save()
        self.destroy()
