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
    def __init__(self, models: str, threshold: float, sample_rate: int, device: str = "") -> None:
        self._threshold = threshold
        self._sample_rate = sample_rate
        self._device = device
        # ONNX backend (not the default tflite): tflite-runtime has no Python 3.13 wheel,
        # so the pipeline runs openWakeWord on onnxruntime. `models` is a comma-separated
        # list of bundled names ("hey_jarvis,alexa") and/or paths to .onnx models; the unit
        # wakes on whichever scores highest above the threshold.
        names = [m.strip() for m in models.split(",") if m.strip()]
        self._model = Model(wakeword_models=names, inference_framework="onnx")

    def wait_for_wake(self) -> None:
        """Block until any configured wake word is detected. Reads the mic frame by frame."""
        for frame in frame_stream(self._sample_rate, self._device):
            scores = self._model.predict(np.asarray(frame, dtype=np.int16))
            hit = max(scores, key=scores.get, default=None)
            if hit is not None and scores[hit] >= self._threshold:
                log.info("wake word detected: %s (%.2f)", hit, scores[hit])
                self._model.reset()
                return
