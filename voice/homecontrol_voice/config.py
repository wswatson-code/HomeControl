"""Voice service configuration, env-driven (HOMECONTROL_VOICE_*).

Plain dataclass + os.getenv — the service's only base dependency is httpx, so we avoid
pulling in pydantic just for config. Paths default to the on-Pi layout that
phase5-voice.sh creates; override any of them per unit via /etc/homecontrol/unit.env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_PREFIX = "HOMECONTROL_VOICE_"


def _get(key: str, default: str) -> str:
    return os.getenv(_PREFIX + key, default)


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(_PREFIX + key, str(default)))
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(_PREFIX + key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class VoiceConfig:
    # Where the Core Service lives (same box).
    core_url: str = _get("CORE_URL", "http://localhost:8080")

    # Wake word (openWakeWord). A bundled model name ("hey_jarvis", "alexa", ...) or a path.
    wake_model: str = _get("WAKE_MODEL", "hey_jarvis")
    wake_threshold: float = _get_float("WAKE_THRESHOLD", 0.5)

    # whisper.cpp — invoked as a binary (built by phase5-voice.sh).
    whisper_bin: str = _get("WHISPER_BIN", "/opt/homecontrol/voice/whisper.cpp/build/bin/whisper-cli")
    whisper_model: str = _get("WHISPER_MODEL", "/opt/homecontrol/voice/models/ggml-tiny.en.bin")

    # Piper TTS — also a binary + an .onnx voice.
    piper_bin: str = _get("PIPER_BIN", "/opt/homecontrol/voice/piper/piper")
    piper_voice: str = _get("PIPER_VOICE", "/opt/homecontrol/voice/models/en_US-amy-medium.onnx")

    # Audio. Device strings are passed to sounddevice; empty = system default (the HAT,
    # once it's the PipeWire default — see docs/audio-hat.md).
    input_device: str = _get("INPUT_DEVICE", "")
    output_device: str = _get("OUTPUT_DEVICE", "")
    sample_rate: int = _get_int("SAMPLE_RATE", 16000)

    # How long to record after the wake word before transcribing (seconds).
    command_seconds: float = _get_float("COMMAND_SECONDS", 5.0)

    # Relative volume step for "louder"/"quieter".
    volume_step: int = _get_int("VOLUME_STEP", 10)
