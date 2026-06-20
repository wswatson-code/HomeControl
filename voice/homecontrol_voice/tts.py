"""Text-to-speech via Piper. Pi-only (needs the piper binary + an .onnx voice).

Synthesize a reply to a temp wav and play it on the unit's speaker. Like whisper, Piper is
invoked as a subprocess (built/installed by phase5-voice.sh).
"""

from __future__ import annotations

import logging
import subprocess
import tempfile

from .audio import play_wav

log = logging.getLogger(__name__)


class Speaker:
    def __init__(self, piper_bin: str, voice: str, output_device: str = "") -> None:
        self._bin = piper_bin
        self._voice = voice
        self._output_device = output_device

    def say(self, text: str) -> None:
        if not text:
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            proc = subprocess.run(
                [self._bin, "--model", self._voice, "--output_file", tmp.name],
                input=text,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                log.error("piper failed (%d): %s", proc.returncode, proc.stderr.strip())
                return
            play_wav(tmp.name, self._output_device)
