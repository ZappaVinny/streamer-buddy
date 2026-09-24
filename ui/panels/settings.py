"""
The right-hand column: status panel above, tabbed settings below.
"""

from tkinter import ttk

from ui.panels.status import StatusPanel
from ui.tabs.general import GeneralTab
from ui.tabs.audio import AudioTab
from ui.tabs.context import ContextTab


class SettingsPanel(ttk.Frame):
    def __init__(self, parent, settings, on_connect, on_disconnect, on_change):
        super().__init__(parent, style="Base.TFrame")

        self.status = StatusPanel(self, on_connect, on_disconnect)
        self.status.pack(fill="x", pady=(0, 14))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.general = GeneralTab(notebook, settings, on_change)
        self.audio = AudioTab(notebook, settings, on_change)
        self.context = ContextTab(notebook, settings, on_change)

        notebook.add(self.general, text="General")
        notebook.add(self.audio, text="Audio")
        notebook.add(self.context, text="Context")
