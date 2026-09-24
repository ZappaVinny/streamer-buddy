"""
Bridges real microphone/speaker hardware (via sounddevice) to aiortc's
WebRTC audio tracks. aiortc speaks in av.AudioFrame objects; our mic
and speakers speak in raw PCM16 bytes, so this module is the adapter
between the two.
"""

import time
import array
import asyncio
import queue
import threading
from fractions import Fraction

import sounddevice as sd
from aiortc import MediaStreamTrack
from av import AudioFrame
from av.audio.resampler import AudioResampler

from core import constants
from core.events import LevelEvent, StatusEvent, Status, MIC, SPEAKER


# ------------------------------------------------------------
# DEVICES
# ------------------------------------------------------------

def list_devices(kind):
    """
    Returns selectable devices as [{"name", "hostapi", "label"}].

    kind is "input" or "output". Devices are identified by name rather
    than index: indices shift between reboots and mean nothing on
    another machine. The host API is part of the label because the
    same hardware appears once per API (ALSA lists a dozen aliases;
    Windows repeats devices across MME/WASAPI/DirectSound).
    """

    channel_key = (
        "max_input_channels" if kind == "input" else "max_output_channels"
    )

    hostapis = sd.query_hostapis()
    found = []
    seen = set()

    for device in sd.query_devices():
        if device[channel_key] < 1:
            continue

        name = device["name"]
        hostapi = hostapis[device["hostapi"]]["name"]
        key = (name, hostapi)

        if key in seen:
            continue

        seen.add(key)
        found.append({
            "name": name,
            "hostapi": hostapi,
            "label": f"{name}  ({hostapi})",
        })

    return found


def resolve_device(name, hostapi, kind):
    """
    Maps a stored device back to an index, or None for the system
    default. Falls back to the default if the device is gone — moving
    between machines shouldn't stop audio from working.

    The host API has to be part of the match: the same name appears
    once per API (ALSA aliases, and MME/WASAPI/DirectSound on
    Windows), so matching on name alone can pick a different device
    than the one that was chosen in the dropdown.
    """

    if not name:
        return None

    channel_key = (
        "max_input_channels" if kind == "input" else "max_output_channels"
    )

    hostapis = sd.query_hostapis()
    fallback = None

    for index, device in enumerate(sd.query_devices()):
        if device["name"] != name or device[channel_key] < 1:
            continue

        if hostapi and hostapis[device["hostapi"]]["name"] == hostapi:
            return index

        if fallback is None:
            fallback = index

    return fallback


def check_device(name, hostapi, kind):
    """
    Confirms a device can actually run our format before we open a
    stream on it.

    sounddevice raises a clean Python error here, whereas letting
    PortAudio discover an unsupported rate or channel count while
    opening can take the whole process down with it.

    Returns the resolved device index. Raises on an unusable device.
    """

    index = resolve_device(name, hostapi, kind)

    settings = {
        "device": index,
        "samplerate": constants.SAMPLE_RATE,
        "channels": constants.CHANNELS,
        "dtype": "int16",
    }

    if kind == "input":
        sd.check_input_settings(**settings)
    else:
        sd.check_output_settings(**settings)

    return index


# ------------------------------------------------------------
# MICROPHONE
# ------------------------------------------------------------

class MicrophoneStreamTrack(MediaStreamTrack):
    """
    A WebRTC audio track backed by the real microphone. sounddevice
    fires _on_audio on its own audio thread; recv() (called from
    aiortc's asyncio event loop) blocks on a thread-safe queue to
    pick up each chunk as it arrives, so frames are paced by the
    real capture rate with no extra throttling needed.
    """

    kind = "audio"

    def __init__(self, settings, emit):
        super().__init__()

        self._emit = emit
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._samples_sent = 0
        self._last_level_at = 0.0

        try:
            device = check_device(
                settings.input_device,
                settings.input_device_hostapi,
                "input",
            )

            self._stream = sd.RawInputStream(
                samplerate=constants.SAMPLE_RATE,
                blocksize=constants.BLOCK_SIZE,
                dtype="int16",
                channels=constants.CHANNELS,
                device=device,
                callback=self._on_audio
            )
            self._stream.start()
        except Exception as error:
            emit(StatusEvent(MIC, Status.ERROR, str(error)))
            raise

        emit(StatusEvent(MIC, Status.ONLINE))

    def _on_audio(self, indata, frames, time_info, status):
        if status:
            self._emit(StatusEvent(MIC, Status.ONLINE, str(status)))

        raw = bytes(indata)
        self._queue.put(raw)
        self._report_level(raw)

    def _report_level(self, raw):
        """
        Feeds the UI level meter. This runs on the realtime audio
        thread, so it looks at a strided subsample and reports only a
        few times a second — keeping this callback cheap is what keeps
        the mic path stable.
        """

        now = time.monotonic()

        if now - self._last_level_at < constants.LEVEL_REPORT_INTERVAL:
            return

        self._last_level_at = now

        samples = array.array("h")
        samples.frombytes(raw)

        window = samples[::constants.LEVEL_SAMPLE_STRIDE]

        if not window:
            return

        peak = max(max(window), -min(window)) / 32768.0
        self._emit(LevelEvent(peak=min(peak, 1.0)))

    async def recv(self):
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self._queue.get)

        sample_count = len(raw) // 2  # int16 = 2 bytes/sample

        frame = AudioFrame(format="s16", layout="mono", samples=sample_count)
        frame.sample_rate = constants.SAMPLE_RATE
        frame.pts = self._samples_sent
        frame.time_base = Fraction(1, constants.SAMPLE_RATE)

        for plane in frame.planes:
            plane.update(raw)

        self._samples_sent += sample_count

        return frame

    def stop(self):
        super().stop()
        self._stream.stop()
        self._stream.close()
        self._emit(StatusEvent(MIC, Status.OFFLINE))


# ------------------------------------------------------------
# SPEAKER
# ------------------------------------------------------------

class SpeakerPlayer:
    """
    Consumes decoded audio frames from an incoming aiortc track and
    plays them through the real speakers via sounddevice.

    Playback is a blocking RawOutputStream driven by a dedicated
    writer thread rather than a realtime callback. A callback has to
    hand PortAudio an exact number of bytes every ~20ms and must
    zero-pad when the network hasn't delivered yet, which caused
    audible starvation. Blocking writes let PortAudio's own buffering
    absorb network jitter with no partial-buffer bookkeeping.
    """

    def __init__(self, settings, emit):
        self._emit = emit
        self._queue: "queue.Queue[bytes | None]" = queue.Queue()

        try:
            device = check_device(
                settings.output_device,
                settings.output_device_hostapi,
                "output",
            )

            self._stream = sd.RawOutputStream(
                samplerate=constants.SAMPLE_RATE,
                dtype="int16",
                channels=constants.CHANNELS,
                device=device,
            )
            self._stream.start()
        except Exception as error:
            emit(StatusEvent(SPEAKER, Status.ERROR, str(error)))
            raise

        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            daemon=True
        )
        self._writer_thread.start()

        emit(StatusEvent(SPEAKER, Status.ONLINE))

    def _writer_loop(self):
        while True:
            chunk = self._queue.get()

            if chunk is None:  # shutdown sentinel
                break

            try:
                self._stream.write(chunk)
            except Exception as error:
                self._emit(StatusEvent(SPEAKER, Status.ERROR, str(error)))

    async def consume(self, track):
        """
        Pulls decoded frames from an aiortc audio track and queues raw
        PCM for playback.

        Two things here are not optional, both found by dumping
        received audio to a file and analyzing it:

        1. Incoming frames are STEREO, not mono. Feeding those bytes
           straight to a mono output stream plays them at double rate
           with interleaved garbage. AudioResampler converts whatever
           the decoder hands back into the mono/rate the speaker
           stream expects.

        2. plane.buffer_size is LARGER than the actual audio (FFmpeg
           pads and aligns its buffers — e.g. 1984 bytes allocated for
           1920 bytes of samples). bytes(plane) returns that whole
           buffer, so it must be sliced to samples * 2 or the padding
           is played as audible junk between every frame.
        """

        resampler = AudioResampler(
            format="s16",
            layout="mono",
            rate=constants.SAMPLE_RATE
        )

        while True:
            frame = await track.recv()

            for converted in resampler.resample(frame):
                usable = converted.samples * 2
                self._queue.put(bytes(converted.planes[0])[:usable])

    def stop(self):
        self._queue.put(None)
        self._writer_thread.join(timeout=2)
        self._stream.stop()
        self._stream.close()
        self._emit(StatusEvent(SPEAKER, Status.OFFLINE))


# ------------------------------------------------------------
# TEST TONE
# ------------------------------------------------------------

def probe_input(settings, on_peak, seconds=5.0):
    """
    Opens the selected microphone briefly and reports its peak level,
    so input selection can be checked without starting a session.

    Blocking; callers on the UI thread should run it on a throwaway
    thread. on_peak is called from the audio thread.
    """

    device = check_device(
        settings.input_device,
        settings.input_device_hostapi,
        "input",
    )

    state = {"last": 0.0}

    def callback(indata, frames, time_info, status):
        now = time.monotonic()

        if now - state["last"] < constants.LEVEL_REPORT_INTERVAL:
            return

        state["last"] = now

        samples = array.array("h")
        samples.frombytes(bytes(indata))
        window = samples[::constants.LEVEL_SAMPLE_STRIDE]

        if window:
            peak = max(max(window), -min(window)) / 32768.0
            on_peak(min(peak, 1.0))

    stream = sd.RawInputStream(
        samplerate=constants.SAMPLE_RATE,
        blocksize=constants.BLOCK_SIZE,
        dtype="int16",
        channels=constants.CHANNELS,
        device=device,
        callback=callback,
    )

    stream.start()

    try:
        time.sleep(seconds)
    finally:
        stream.stop()
        stream.close()
        on_peak(0.0)


def play_test_tone(settings, seconds=1.5, frequency=440):
    """
    Plays a short tone on the selected output device so the user can
    confirm they picked the right one. Blocking, so callers on the UI
    thread should run it on a throwaway thread.
    """

    import math

    # Validated first: opening a stream on a device that can't do this
    # rate/channel count can take PortAudio — and the process — down
    # hard, with no Python traceback to show for it.
    device = check_device(
        settings.output_device,
        settings.output_device_hostapi,
        "output",
    )

    rate = constants.SAMPLE_RATE

    stream = sd.RawOutputStream(
        samplerate=rate,
        dtype="int16",
        channels=constants.CHANNELS,
        device=device,
    )
    stream.start()

    try:
        total = int(rate * seconds)
        written = 0

        while written < total:
            block = bytearray()

            for i in range(constants.BLOCK_SIZE):
                n = written + i
                # Fade the envelope so it doesn't click on start/stop.
                envelope = min(1.0, min(n, total - n) / (rate * 0.05))
                value = int(
                    6000 * envelope
                    * math.sin(2 * math.pi * frequency * n / rate)
                )
                block += value.to_bytes(2, "little", signed=True)

            stream.write(bytes(block))
            written += constants.BLOCK_SIZE
    finally:
        stream.stop()
        stream.close()
