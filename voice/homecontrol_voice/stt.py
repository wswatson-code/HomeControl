"""Speech-to-text via whisper.cpp. Pi-only (needs the built whisper-cli binary + a model).

We shell out to whisper-cli rather than bind a library: phase5-voice.sh builds whisper.cpp
from source for the Pi, and a subprocess keeps the heavy native code out of our process.
Transcribe a wav and return the recognized text.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile

import numpy as np

from .audio import write_wav

log = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, whisper_bin: str, model: str, sample_rate: int) -> None:
        self._bin = whisper_bin
        self._model = model
        self._sample_rate = sample_rate

    def transcribe(self, audio: np.ndarray) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            write_wav(tmp.name, audio, self._sample_rate)
            # -nt: no timestamps, -np: no progress prints -> stdout is just the transcript.
            proc = subprocess.run(
                [self._bin, "-m", self._model, "-f", tmp.name, "-nt", "-np", "-l", "en"],
                capture_output=True,
                text=True,
                check=False,
            )
        if proc.returncode != 0:
            log.error("whisper failed (%d): %s", proc.returncode, proc.stderr.strip())
            return ""
        text = proc.stdout.strip()
        log.info("transcript: %r", text)
        return text
