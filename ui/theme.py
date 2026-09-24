"""
Dark theme for ttk.

Everything visual reads from PALETTE and FONTS here, so retheming is a
single-file change.

Two Tk realities shape this:
  - ttk's built-in themes mostly ignore colour options; "clam" is the
    one that honours them, so it's the base for all styling.
  - Combobox dropdown lists are classic Tk widgets living outside ttk
    styling, so they have to be coloured through option_add.

Tk also can't do rounded corners, shadows or transparency. The look
comes from spacing, restrained contrast and consistent type instead.
"""

import tkinter.font as tkfont
from tkinter import ttk


PALETTE = {
    "bg_base": "#17181c",      # window background
    "bg_surface": "#1e1f24",   # panels
    "bg_raised": "#26272e",    # inputs, hover states
    "bg_active": "#2f313a",    # pressed / selected
    "border": "#32333b",
    "text": "#e6e6ea",
    "text_muted": "#9a9aa4",
    "accent": "#5b9cf8",
    "ok": "#5fd38d",
    "warn": "#e8c468",
    "err": "#f2726f",

    # Transcript speaker colours, carried over from the console scheme.
    "you": "#6fd3e8",
    "assistant": "#e8c468",
    "chat": "#8a8a94",
    "system": "#b98ce0",
}

# Preference order per platform; first match wins.
_UI_FONTS = ["Inter", "Segoe UI", "Noto Sans", "DejaVu Sans", "Liberation Sans"]
_MONO_FONTS = ["JetBrains Mono", "Cascadia Mono", "Consolas",
               "Noto Sans Mono", "DejaVu Sans Mono"]

FONTS = {}

# One padding value for every tab state — see the TNotebook.Tab map.
_TAB_PADDING = (16, 9, 16, 9)


def _pick(candidates, fallback):
    available = set(tkfont.families())

    for name in candidates:
        if name in available:
            return name

    return fallback


def _build_fonts():
    ui = _pick(_UI_FONTS, "TkDefaultFont")
    mono = _pick(_MONO_FONTS, "TkFixedFont")

    FONTS.update({
        "ui": (ui, 10),
        "ui_bold": (ui, 10, "bold"),
        "heading": (ui, 11, "bold"),
        "small": (ui, 9),
        "mono": (mono, 10),
    })


def apply(root):
    """Applies the theme to a root window. Call once, before building UI."""

    _build_fonts()

    root.configure(bg=PALETTE["bg_base"])

    style = ttk.Style(root)
    style.theme_use("clam")

    # Base
    style.configure(
        ".",
        background=PALETTE["bg_surface"],
        foreground=PALETTE["text"],
        fieldbackground=PALETTE["bg_raised"],
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["bg_surface"],
        darkcolor=PALETTE["bg_surface"],
        focuscolor=PALETTE["accent"],
        font=FONTS["ui"],
    )

    style.configure("TFrame", background=PALETTE["bg_surface"])
    style.configure("Base.TFrame", background=PALETTE["bg_base"])

    style.configure("TLabel", background=PALETTE["bg_surface"])
    style.configure(
        "Muted.TLabel",
        foreground=PALETTE["text_muted"],
        font=FONTS["small"],
    )
    style.configure("Heading.TLabel", font=FONTS["heading"])
    style.configure(
        "SectionTitle.TLabel",
        background=PALETTE["bg_base"],
        foreground=PALETTE["text_muted"],
        font=FONTS["ui_bold"],
    )

    # Cards: flat panels with a hairline border, since Tk has no
    # rounded corners or shadows to work with.
    style.configure(
        "Card.TFrame",
        background=PALETTE["bg_surface"],
        borderwidth=1,
        relief="solid",
        bordercolor=PALETTE["border"],
    )

    # Buttons
    style.configure(
        "TButton",
        background=PALETTE["bg_raised"],
        foreground=PALETTE["text"],
        borderwidth=1,
        relief="solid",
        padding=(12, 7),
    )
    style.map(
        "TButton",
        background=[("pressed", PALETTE["bg_active"]),
                    ("active", PALETTE["bg_active"])],
        bordercolor=[("focus", PALETTE["accent"])],
    )

    style.configure(
        "Accent.TButton",
        background=PALETTE["accent"],
        foreground="#0d1117",
        font=FONTS["ui_bold"],
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", "#3f7fd8"), ("active", "#6fa9fa")],
    )

    # Entries
    style.configure(
        "TEntry",
        fieldbackground=PALETTE["bg_raised"],
        foreground=PALETTE["text"],
        insertcolor=PALETTE["text"],
        borderwidth=1,
        relief="solid",
        padding=6,
    )
    style.map("TEntry", bordercolor=[("focus", PALETTE["accent"])])

    # Combobox — the widget itself is ttk, but its dropdown is not.
    style.configure(
        "TCombobox",
        fieldbackground=PALETTE["bg_raised"],
        background=PALETTE["bg_raised"],
        foreground=PALETTE["text"],
        arrowcolor=PALETTE["text_muted"],
        borderwidth=1,
        relief="solid",
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", PALETTE["bg_raised"])],
        bordercolor=[("focus", PALETTE["accent"])],
    )

    root.option_add("*TCombobox*Listbox.background", PALETTE["bg_raised"])
    root.option_add("*TCombobox*Listbox.foreground", PALETTE["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", PALETTE["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#0d1117")
    root.option_add("*TCombobox*Listbox.borderWidth", 0)

    # Notebook
    style.configure(
        "TNotebook",
        background=PALETTE["bg_base"],
        borderwidth=0,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=PALETTE["bg_base"],
        foreground=PALETTE["text_muted"],
        bordercolor=PALETTE["bg_base"],
        lightcolor=PALETTE["bg_base"],
        darkcolor=PALETTE["bg_base"],
        borderwidth=0,
        padding=_TAB_PADDING,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", PALETTE["bg_surface"]),
                    ("active", PALETTE["bg_raised"])],
        foreground=[("selected", PALETTE["text"]),
                    ("active", PALETTE["text"])],
        lightcolor=[("selected", PALETTE["bg_surface"])],
        darkcolor=[("selected", PALETTE["bg_surface"])],
        bordercolor=[("selected", PALETTE["bg_surface"])],
        # clam ships padding as a *state map* — "6 2 6 2" normally and
        # "6 4 6 2" when selected — so the selected tab grows and the
        # strip shifts as you click between tabs. Pinning padding to
        # one value for every state is what actually stops it; the
        # selection then reads purely as a colour change.
        padding=[("selected", _TAB_PADDING), ("!selected", _TAB_PADDING)],
    )

    # Scrollbars render light unless every part is set explicitly.
    style.configure(
        "Vertical.TScrollbar",
        background=PALETTE["bg_raised"],
        troughcolor=PALETTE["bg_base"],
        bordercolor=PALETTE["bg_base"],
        arrowcolor=PALETTE["text_muted"],
        borderwidth=0,
        width=12,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("pressed", PALETTE["accent"]),
                    ("active", PALETTE["bg_active"])],
    )

    # Meters (mic level, context usage)
    style.configure(
        "Meter.Horizontal.TProgressbar",
        background=PALETTE["accent"],
        troughcolor=PALETTE["bg_raised"],
        bordercolor=PALETTE["bg_raised"],
        lightcolor=PALETTE["accent"],
        darkcolor=PALETTE["accent"],
        borderwidth=0,
        thickness=8,
    )

    style.configure("TSeparator", background=PALETTE["border"])

    return style
