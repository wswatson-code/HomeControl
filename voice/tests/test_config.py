"""Config validation tests."""

from __future__ import annotations

import pytest

from homecontrol_voice.config import VoiceConfig


def test_accepts_16k():
    assert VoiceConfig(sample_rate=16000).sample_rate == 16000


@pytest.mark.parametrize("rate", [8000, 44100, 48000])
def test_rejects_non_16k(rate):
    # 16 kHz is required by openWakeWord + whisper.cpp; a mistaken override must fail loudly.
    with pytest.raises(ValueError):
        VoiceConfig(sample_rate=rate)
