"""
Bridges real microphone/speaker hardware (via sounddevice) to aiortc's
WebRTC audio tracks. aiortc speaks in av.AudioFrame objects; our mic
and speakers speak in raw PCM16 bytes, so this module is the adapter
between the two.
"""

import asyncio
import queue
import threading
from fractions import Fraction

import sounddevice as sd
from aiortc import MediaStreamTrack
from av import AudioFrame
from av.audio.resampler import AudioResampler

import config


class MicrophoneStreamTrack(MediaStreamTrack):
    """
    A WebRTC audio track backed by the real microphone. sounddevice
    fires _on_audio on its own audio thread; recv() (called from
    aiortc's asyncio event loop) blocks on a thread-safe queue to
    pick up each chunk as it arrives, so frames are paced by the
    real capture rate with no extra throttling needed.
    """

    kind = "audio"

    def __init__(self):
        super().__init__()

        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._samples_sent = 0

        self._stream = sd.RawInputStream(
            samplerate=config.SAMPLE_RATE,
            blocksize=config.BLOCK_SIZE,
            dtype="int16",
            channels=config.CHANNELS,
            callback=self._on_audio
        )
        self._stream.start()

    def _on_audio(self, indata, frames, time, status):
        if status:
            print("Microphone:", status)

        self._queue.put(bytes(indata))

    async def recv(self):
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self._queue.get)

        sample_count = len(raw) // 2  # int16 = 2 bytes/sample

        frame = AudioFrame(format="s16", layout="mono", samples=sample_count)
        frame.sample_rate = config.SAMPLE_RATE
        frame.pts = self._samples_sent
        frame.time_base = Fraction(1, config.SAMPLE_RATE)

        for plane in frame.planes:
            plane.update(raw)

        self._samples_sent += sample_count

        return frame

    def stop(self):
        super().stop()
        self._stream.stop()
        self._stream.close()


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

    def __init__(self):
        self._queue: "queue.Queue[bytes | None]" = queue.Queue()

        self._stream = sd.RawOutputStream(
            samplerate=config.SAMPLE_RATE,
            dtype="int16",
            channels=config.CHANNELS,
        )
        self._stream.start()

        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            daemon=True
        )
        self._writer_thread.start()

    def _writer_loop(self):
        while True:
            chunk = self._queue.get()

            if chunk is None:  # shutdown sentinel
                break

            try:
                self._stream.write(chunk)
            except Exception as error:
                print("Speaker write failed:", error)

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
            rate=config.SAMPLE_RATE
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
