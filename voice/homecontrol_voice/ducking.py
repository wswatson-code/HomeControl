"""Duck (attenuate) librespot's music while the voice pipeline is active.

Targets librespot's PipeWire **sink-input** (its own playback stream) via pactl — NOT the
sink — so the voice service's chime/TTS (separate streams) stay at full volume, and the
user's overall device volume is untouched. Each stream's pre-duck volume is captured so
re-ducking to a different level (listen -> speak) and restore() are exact.

Best-effort: if pactl is missing or nothing is playing, these are no-ops and never raise —
ducking must never break the voice loop.
"""

from __future__ import annotations

import logging
import re
import subprocess

log = logging.getLogger(__name__)

# sink-input id -> pre-duck volume (raw pulse scale, 0..65536). Saved on the first duck of
# a cycle so later re-ducks scale from the original, and restore() puts it back exactly.
_saved: dict[int, int] = {}


def _run(args: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        log.debug("pactl call failed (%s): %s", args, e)
        return None


def _librespot_sink_inputs() -> list[int]:
    """IDs of every sink-input whose properties mention librespot. [] if none / pactl absent."""
    proc = _run(["pactl", "list", "sink-inputs"])
    if proc is None or proc.returncode != 0:
        return []
    ids: list[int] = []
    current: int | None = None
    is_librespot = False
    for line in proc.stdout.splitlines():
        m = re.match(r"Sink Input #(\d+)", line)
        if m:
            if current is not None and is_librespot:
                ids.append(current)
            current, is_librespot = int(m.group(1)), False
        elif "librespot" in line.lower():
            is_librespot = True
    if current is not None and is_librespot:
        ids.append(current)
    return ids


def _volume(sink_input_id: int) -> int | None:
    proc = _run(["pactl", "get-sink-input-volume", str(sink_input_id)])
    if proc is None or proc.returncode != 0:
        return None
    # e.g. "Volume: front-left: 40000 /  61% ...": grab the first raw value before the slash.
    m = re.search(r":\s*(\d+)\s*/", proc.stdout)
    return int(m.group(1)) if m else None


def _set_volume(sink_input_id: int, volume: int) -> None:
    _run(["pactl", "set-sink-input-volume", str(sink_input_id), str(max(0, volume))])


def duck(level: float) -> None:
    """Attenuate librespot stream(s) to `level` (0..1) of their ORIGINAL volume.

    0.25 = duck 75%. Re-ducking scales from the saved original (not the already-ducked
    value), so a listen(0.25) -> speak(0.50) transition and restore() are both exact.
    """
    level = max(0.0, min(1.0, level))
    for sid in _librespot_sink_inputs():
        if sid not in _saved:
            v = _volume(sid)
            if v is None:
                continue
            _saved[sid] = v
        _set_volume(sid, int(_saved[sid] * level))


def restore() -> None:
    """Restore every ducked stream to its captured pre-duck volume."""
    for sid, vol in list(_saved.items()):
        _set_volume(sid, vol)
    _saved.clear()
