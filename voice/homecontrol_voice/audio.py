"""Microphone capture + TTS playback. Pi-only (needs sounddevice + a real audio device).

Kept thin and synchronous; the pipeline calls these via asyncio.to_thread so the blocking
PortAudio/PipeWire calls don't stall the event loop. Capture is mono 16-bit at the wake
word / whisper sample rate (16 kHz).
"""

from __future__ import annotations

import subprocess
import wave
from collections.abc import Iterator

import numpy as np
import sounddevice as sd

# openWakeWord expects 80 ms frames (1280 samples @ 16 kHz) of int16.
FRAME_SAMPLES = 1280


def _device(name: str) -> str | int | None:
    if not name:
        return None
    return int(name) if name.isdigit() else name


def frame_stream(sample_rate: int, device: str = "") -> Iterator[np.ndarray]:
    """Yield consecutive int16 mono frames from the mic forever (until the caller stops)."""
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
        device=_device(device),
    ) as stream:
        while True:
            data, _overflowed = stream.read(FRAME_SAMPLES)
            yield data[:, 0]


def record(seconds: float, sample_rate: int, device: str = "") -> np.ndarray:
    """Record a fixed window of int16 mono audio (the command after the wake word)."""
    frames = int(seconds * sample_rate)
    audio = sd.rec(
        frames, samplerate=sample_rate, channels=1, dtype="int16", device=_device(device)
    )
    sd.wait()
    return audio[:, 0]


def write_wav(path: str, audio: np.ndarray, sample_rate: int) -> None:
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # int16
        wav.setframerate(sample_rate)
        wav.writeframes(audio.tobytes())


def play_wav(path: str, device: str = "") -> None:
    """Play a wav via paplay (PipeWire pulse). Device is a PipeWire sink name, or default."""
    cmd = ["paplay"]
    if device:
        cmd += [f"--device={device}"]
    cmd.append(path)
    subprocess.run(cmd, check=False)
