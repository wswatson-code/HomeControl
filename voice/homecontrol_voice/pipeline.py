"""The voice loop: wake → listen → transcribe → act → reply. Pi-only end to end.

Blocking audio/ML steps run in threads (asyncio.to_thread) so the async httpx dispatch and
state-reporting stay responsive. Each phase is reported to the Core Service so the kiosk can
show what the unit is doing. Any per-utterance error is logged and the loop returns to idle —
a bad transcription must never kill the service.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from .actions import Actions
from .audio import play_chime, record
from .config import VoiceConfig
from .ducking import duck, restore
from .intent import parse
from .stt import Transcriber
from .tts import Speaker
from .wakeword import WakeWord

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, cfg: VoiceConfig) -> None:
        self._cfg = cfg
        self._wake = WakeWord(cfg.wake_model, cfg.wake_threshold, cfg.sample_rate, cfg.input_device)
        self._stt = Transcriber(cfg.whisper_bin, cfg.whisper_model, cfg.sample_rate)
        self._tts = Speaker(cfg.piper_bin, cfg.piper_voice, cfg.output_device)

    async def run(self) -> None:
        cfg = self._cfg
        async with httpx.AsyncClient(base_url=cfg.core_url, timeout=10.0) as client:
            actions = Actions(client, cfg.volume_step)
            log.info("voice pipeline up; wake word=%r", cfg.wake_model)
            while True:
                try:
                    await actions.report_state("idle")
                    await asyncio.to_thread(self._wake.wait_for_wake)
                    # Duck the music on wake (covers the chime + listening + thinking).
                    if cfg.duck_enabled:
                        await asyncio.to_thread(duck, cfg.duck_listen)
                    try:
                        await self._handle_utterance(actions)
                    finally:
                        if cfg.duck_enabled:
                            await asyncio.to_thread(restore)  # always un-duck after a cycle
                except Exception:  # noqa: BLE001 — a bad utterance or mic blip must not kill the loop
                    # Includes AudioError from a dead mic; sleep so we don't spin if it stays dead.
                    log.exception("voice cycle failed")
                    if cfg.duck_enabled:
                        await asyncio.to_thread(restore)  # belt-and-suspenders: never leave music ducked
                    await asyncio.sleep(1)

    async def _handle_utterance(self, actions: Actions) -> None:
        cfg = self._cfg
        await actions.report_state("listening")
        # Chime BEFORE opening the mic so it finishes before recording and isn't captured.
        if cfg.listen_chime:
            await asyncio.to_thread(play_chime, cfg.output_device, cfg.sample_rate)
        audio = await asyncio.to_thread(
            record, cfg.command_seconds, cfg.sample_rate, cfg.input_device
        )

        await actions.report_state("thinking")
        text = await asyncio.to_thread(self._stt.transcribe, audio)
        intent = parse(text)
        log.info("intent: %s %s", intent.kind, intent.args)

        reply = await actions.dispatch(intent)
        await actions.report_state("speaking", transcript=text, reply=reply)
        # Ease the duck for the spoken reply (music a bit louder under TTS than under listen).
        if cfg.duck_enabled:
            await asyncio.to_thread(duck, cfg.duck_speak)
        await asyncio.to_thread(self._tts.say, reply)
