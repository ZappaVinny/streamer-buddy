"""
API key dialog.

The key is never written into settings.json — it goes to the OS
credential manager. When no credential store is available the dialog
says so and points at the environment variable instead of pretending
to save.
"""

import tkinter as tk
from tkinter import ttk

from core import credentials
from ui.theme import PALETTE
from ui.widgets import LabeledEntry


class ApiKeyDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.title("OpenAI API Key")
        self.configure(bg=PALETTE["bg_base"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        body = ttk.Frame(self, style="Base.TFrame")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        self._available = credentials.backend_available()
        stored = credentials.has_stored_key()

        ttk.Label(
            body,
            text=credentials.backend_status(),
            style="Muted.TLabel",
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        self._field = LabeledEntry(
            body,
            "API key",
            hint="Stored securely. Never written to the settings file.",
            show="•",
            width=44,
        )
        self._field.pack(fill="x")

        if stored:
            self._field.entry.configure(state="disabled")
            self._field.set("")

        self._status = ttk.Label(
            body,
            text="A key is saved." if stored else "",
            style="Muted.TLabel",
        )
        self._status.pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(body, style="Base.TFrame")
        buttons.pack(fill="x", pady=(16, 0))

        ttk.Button(buttons, text="Close", command=self.destroy).pack(
            side="right"
        )

        self._save_button = ttk.Button(
            buttons,
            text="Save",
            style="Accent.TButton",
            command=self._save,
        )
        self._save_button.pack(side="right", padx=(0, 8))

        self._clear_button = ttk.Button(
            buttons,
            text="Clear saved key",
            command=self._clear,
        )

        if stored:
            self._clear_button.pack(side="left")

        if not self._available:
            self._save_button.configure(state="disabled")
            self._field.entry.configure(state="disabled")

        self._center(parent)
        self._field.entry.focus_set()

    def _center(self, parent):
        self.update_idletasks()

        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3

        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _save(self):
        key = self._field.get().strip()

        if not key:
            self._set_status("Enter a key first.", error=True)
            return

        if credentials.set_api_key(key):
            self._field.set("")
            self._set_status("Saved.")
            self._clear_button.pack(side="left")
        else:
            self._set_status("Could not reach the credential store.", error=True)

    def _clear(self):
        credentials.clear_api_key()
        self._field.entry.configure(state="normal")
        self._field.set("")
        self._clear_button.pack_forget()
        self._set_status("Saved key removed.")

    def _set_status(self, message, error=False):
        self._status.configure(
            text=message,
            foreground=PALETTE["err"] if error else PALETTE["text_muted"],
        )
