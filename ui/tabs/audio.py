"""
Audio tab: device selection, an input level meter, and a test tone.

Devices are listed with their host API because the same hardware shows
up many times over (ALSA aliases on Linux, MME/WASAPI/DirectSound
duplicates on Windows), and are stored by name since indices aren't
stable.
"""

import threading
from tkinter import ttk

from core import audio_bridge
from ui.theme import PALETTE
from ui.widgets import Card, HintLabel, LabeledCombo


DEFAULT_LABEL = "System default"


class AudioTab(ttk.Frame):
    def __init__(self, parent, settings, on_change):
        super().__init__(parent, style="TFrame")

        self._settings = settings
        self._on_change = on_change
        self._inputs = []
        self._outputs = []

        inner = ttk.Frame(self, style="Base.TFrame")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_devices(inner)
        self._build_meter(inner)

        self.refresh_devices()

    # --------------------------------------------------------

    def _build_devices(self, parent):
        card = Card(parent, title="Devices")
        card.pack(fill="x", pady=(0, 14))

        self._input_combo = LabeledCombo(card.body, "Microphone")
        self._input_combo.pack(fill="x")
        self._input_combo.combo.bind(
            "<<ComboboxSelected>>", lambda _: self._save()
        )

        self._output_combo = LabeledCombo(card.body, "Speaker")
        self._output_combo.pack(fill="x", pady=(12, 0))
        self._output_combo.combo.bind(
            "<<ComboboxSelected>>", lambda _: self._save()
        )

        HintLabel(
            card.body,
            "Device changes apply the next time a session starts.",
        ).pack(fill="x", pady=(8, 0))

        buttons = ttk.Frame(card.body, style="TFrame")
        buttons.pack(fill="x", pady=(12, 0))

        ttk.Button(
            buttons,
            text="Refresh list",
            command=self.refresh_devices,
        ).pack(side="left")

        self._test_button = ttk.Button(
            buttons,
            text="Play test tone",
            command=self._play_test_tone,
        )
        self._test_button.pack(side="left", padx=(8, 0))

    def _build_meter(self, parent):
        card = Card(parent, title="Input level")
        card.pack(fill="x")

        self._meter = ttk.Progressbar(
            card.body,
            style="Meter.Horizontal.TProgressbar",
            maximum=100,
        )
        self._meter.pack(fill="x")

        self._meter_hint = ttk.Label(
            card.body,
            text="Connect a session, or test the mic, to see input.",
            style="Muted.TLabel",
        )
        self._meter_hint.pack(anchor="w", pady=(8, 0))

        self._mic_button = ttk.Button(
            card.body,
            text="Test microphone (5s)",
            command=self._test_microphone,
        )
        self._mic_button.pack(anchor="w", pady=(10, 0))

    # --------------------------------------------------------

    def refresh_devices(self):
        self._inputs = audio_bridge.list_devices("input")
        self._outputs = audio_bridge.list_devices("output")

        self._input_combo.set_values(
            [DEFAULT_LABEL] + [d["label"] for d in self._inputs]
        )
        self._output_combo.set_values(
            [DEFAULT_LABEL] + [d["label"] for d in self._outputs]
        )

        self._input_combo.set(self._label_for(
            self._inputs,
            self._settings.input_device,
            self._settings.input_device_hostapi,
        ))
        self._output_combo.set(self._label_for(
            self._outputs,
            self._settings.output_device,
            self._settings.output_device_hostapi,
        ))

    def _label_for(self, devices, name, hostapi):
        if not name:
            return DEFAULT_LABEL

        for device in devices:
            if device["name"] == name and (
                not hostapi or device["hostapi"] == hostapi
            ):
                return device["label"]

        # Saved device isn't present on this machine any more.
        return DEFAULT_LABEL

    def _device_for(self, devices, label):
        for device in devices:
            if device["label"] == label:
                return device["name"], device["hostapi"]

        return None, None

    def _save(self):
        (
            self._settings.input_device,
            self._settings.input_device_hostapi,
        ) = self._device_for(self._inputs, self._input_combo.get())

        (
            self._settings.output_device,
            self._settings.output_device_hostapi,
        ) = self._device_for(self._outputs, self._output_combo.get())

        self._settings.save()
        self._on_change("audio_devices")
        self._validate_selection()

    def _validate_selection(self):
        """
        Checks the chosen devices straight away. Plenty of entries in
        these lists can't actually be opened — ALSA plugin aliases
        like dmix and upmix, or hardware already in use — and finding
        that out at connect time is far worse than finding out now.
        """

        for kind, name, hostapi in (
            ("input", self._settings.input_device,
             self._settings.input_device_hostapi),
            ("output", self._settings.output_device,
             self._settings.output_device_hostapi),
        ):
            try:
                audio_bridge.check_device(name, hostapi, kind)
            except Exception as error:
                self._report(
                    f"That {kind} device can't be used: {error}",
                    error=True,
                )
                return

        self._report("Devices look good.")

    def _play_test_tone(self):
        self._test_button.configure(state="disabled", text="Playing…")

        def run():
            error = None

            try:
                audio_bridge.play_test_tone(self._settings)
            except Exception as exc:
                error = str(exc)

            # Back to the Tk thread before touching widgets.
            self.after(0, lambda: self._tone_finished(error))

        threading.Thread(target=run, daemon=True).start()

    def _tone_finished(self, error):
        self._test_button.configure(state="normal", text="Play test tone")

        if error:
            self._report(f"Test tone failed: {error}", error=True)
        else:
            self._report("Test tone finished.")

    def _test_microphone(self):
        self._mic_button.configure(state="disabled", text="Listening…")
        self._report("Say something — the meter should move.")

        def run():
            error = None

            try:
                audio_bridge.probe_input(
                    self._settings,
                    # Peaks arrive on the audio thread, so hop back to
                    # Tk before touching the meter.
                    lambda peak: self.after(0, self.set_level, peak),
                )
            except Exception as exc:
                error = str(exc)

            self.after(0, lambda: self._mic_test_finished(error))

        threading.Thread(target=run, daemon=True).start()

    def _mic_test_finished(self, error):
        self._mic_button.configure(state="normal", text="Test microphone (5s)")
        self.set_level(0)

        if error:
            self._report(f"Microphone failed: {error}", error=True)
        else:
            self._report("Microphone test finished.")

    def _report(self, message, error=False):
        self._meter_hint.configure(
            text=message,
            foreground=PALETTE["err"] if error else PALETTE["text_muted"],
        )

    # --------------------------------------------------------

    def set_level(self, peak):
        self._meter.configure(value=min(peak, 1.0) * 100)

    def set_meter_hint(self, text):
        self._meter_hint.configure(text=text, foreground=PALETTE["text_muted"])
