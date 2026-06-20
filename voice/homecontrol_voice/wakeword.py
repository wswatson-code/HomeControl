"""Wake-word detection via openWakeWord. Pi-only.

Wraps an openWakeWord model and blocks until the configured wake word is heard above the
threshold, then returns. The pipeline runs this in a thread; on return it captures the
command. openWakeWord is tflite-based and runs comfortably on a Pi 5.
"""

from __future__ import annotations

import logging

import numpy as np
from openwakeword.model import Model

from .audio import frame_stream

log = logging.getLogger(__name__)


class WakeWord:
    def __init__(self, model: str, threshold: float, sample_rate: int, device: str = "") -> None:
        self._threshold = threshold
        self._sample_rate = sample_rate
        self._device = device
        # `model` is a bundled name ("hey_jarvis") or a path to a .tflite/.onnx model.
        self._model = Model(wakeword_models=[model])
        self._key = next(iter(self._model.models))

    def wait_for_wake(self) -> None:
        """Block until the wake word is detected. Reads the mic frame by frame."""
        for frame in frame_stream(self._sample_rate, self._device):
            scores = self._model.predict(np.asarray(frame, dtype=np.int16))
            if scores.get(self._key, 0.0) >= self._threshold:
                log.info("wake word detected (%.2f)", scores[self._key])
                self._model.reset()
                return
