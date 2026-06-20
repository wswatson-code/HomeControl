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


def _get_bool(key: str, default: bool) -> bool:
    v = os.getenv(_PREFIX + key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


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

    # Audio. Device strings are PipeWire source/sink names for parec/paplay; empty = system
    # default (the HAT, once it's the PipeWire default — see docs/audio-hat.md).
    input_device: str = _get("INPUT_DEVICE", "")
    output_device: str = _get("OUTPUT_DEVICE", "")
    # 16 kHz is not a tunable: openWakeWord and whisper.cpp are both fixed at 16 kHz, and the
    # 80 ms wake-word frame size assumes it. Exposed only so the guard below can reject a
    # mistaken override loudly instead of silently feeding both models garbage.
    sample_rate: int = _get_int("SAMPLE_RATE", 16000)

    # Play a short chime when the wake word is heard, before recording the command
    # (audible "I'm listening" cue). Set false to stay silent.
    listen_chime: bool = _get_bool("LISTEN_CHIME", True)

    # How long to record after the wake word before transcribing (seconds).
    command_seconds: float = _get_float("COMMAND_SECONDS", 5.0)

    # Relative volume step for "louder"/"quieter".
    volume_step: int = _get_int("VOLUME_STEP", 10)

    def __post_init__(self) -> None:
        if self.sample_rate != 16000:
            raise ValueError(
                f"HOMECONTROL_VOICE_SAMPLE_RATE must be 16000 (openWakeWord + whisper.cpp "
                f"require it); got {self.sample_rate}"
            )
