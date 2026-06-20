"""Microphone capture + TTS playback via PipeWire's PulseAudio interface. Pi-only.

We capture with `parec` and play with `paplay` (both PulseAudio clients from
pulseaudio-utils) rather than PortAudio/sounddevice: on a PipeWire system the ALSA→pulse
bridge PortAudio uses is unreliable ("PulseAudio: Unable to create stream: Timeout"),
while parec/paplay speak the pulse protocol pipewire-pulse implements natively — the same
path that already carries librespot and TTS output. Capture is mono 16-bit at the wake
word / whisper rate (16 kHz).

INPUT_DEVICE / OUTPUT_DEVICE, when set, are PipeWire source / sink names (as shown by
`pactl list short sources|sinks`); empty means the system default.
"""

from __future__ import annotations

import subprocess
import wave
from collections.abc import Iterator
from typing import BinaryIO

import numpy as np

# openWakeWord expects 80 ms frames (1280 samples @ 16 kHz) of int16.
FRAME_SAMPLES = 1280


class AudioError(RuntimeError):
    """Raised when capture fails (parec exits / mic gone), so the failure is visible
    instead of degrading into empty audio that whisper reads as 'didn't catch that'."""


def _parec_cmd(sample_rate: int, device: str) -> list[str]:
    cmd = ["parec", "--format=s16le", f"--rate={sample_rate}", "--channels=1"]
    if device:
        cmd.append(f"--device={device}")
    return cmd


def _read_exact(stream: BinaryIO, n: int) -> bytes | None:
    """Read exactly n bytes from a stream; None if it closes first."""
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def frame_stream(sample_rate: int, device: str = "") -> Iterator[np.ndarray]:
    """Yield consecutive int16 mono frames from the mic until the caller stops iterating.

    Raises AudioError if parec exits unexpectedly — otherwise a dead mic would end the
    generator quietly and the caller would treat it as a (false) wake. parec's stderr is
    left inherited so its diagnostics land in the journal.
    """
    proc = subprocess.Popen(_parec_cmd(sample_rate, device), stdout=subprocess.PIPE)
    try:
        nbytes = FRAME_SAMPLES * 2  # int16
        while True:
            buf = _read_exact(proc.stdout, nbytes)
            if buf is None:
                raise AudioError(f"mic capture stream ended (parec exited rc={proc.poll()})")
            yield np.frombuffer(buf, dtype=np.int16)
    finally:
        proc.terminate()
        proc.wait()


def record(seconds: float, sample_rate: int, device: str = "") -> np.ndarray:
    """Record a fixed window of int16 mono audio (the command after the wake word).

    Raises AudioError on a short/failed capture instead of returning empty audio: empty
    audio transcribes to "" and looks exactly like a user who said nothing, hiding a dead
    mic. We capture parec's stderr to put the real reason in the error.
    """
    total = int(seconds * sample_rate) * 2  # bytes
    proc = subprocess.Popen(_parec_cmd(sample_rate, device), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        buf = _read_exact(proc.stdout, total)
    finally:
        proc.terminate()
        proc.wait()
    if buf is None:
        err = (proc.stderr.read() if proc.stderr else b"").decode(errors="replace").strip()
        raise AudioError(f"mic capture failed (parec rc={proc.returncode}): {err or 'stream closed early'}")
    return np.frombuffer(buf, dtype=np.int16)


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
        cmd.append(f"--device={device}")
    cmd.append(path)
    subprocess.run(cmd, check=False)
