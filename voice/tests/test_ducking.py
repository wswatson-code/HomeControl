"""Ducking tests — exercise the pactl parsing + duck/restore flow with a fake subprocess."""

from __future__ import annotations

import pytest

from homecontrol_voice import ducking

_LIST_OUT = """Sink Input #45
\tDriver: PipeWire
\tOwner Module: n/a
\tapplication.name = "librespot"
\tmedia.name = "Spotify"
Sink Input #46
\tDriver: PipeWire
\tapplication.name = "paplay"
"""

_VOL_OUT = "Volume: front-left: 40000 /  61%   front-right: 40000 /  61%\n"


class _Proc:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


@pytest.fixture
def fake_pactl(monkeypatch):
    """Record pactl calls and serve canned output; reset module ducking state."""
    ducking._saved.clear()
    calls = []

    def run(args, **kw):
        calls.append(args)
        if args[:3] == ["pactl", "list", "sink-inputs"]:
            return _Proc(_LIST_OUT)
        if args[:2] == ["pactl", "get-sink-input-volume"]:
            return _Proc(_VOL_OUT)
        return _Proc("")

    monkeypatch.setattr(ducking.subprocess, "run", run)
    return calls


def test_finds_only_librespot_stream(fake_pactl):
    assert ducking._librespot_sink_inputs() == [45]  # not the paplay stream (#46)


def test_parses_raw_volume(fake_pactl):
    assert ducking._volume(45) == 40000


def test_duck_scales_from_original(fake_pactl):
    ducking.duck(0.25)
    sets = [c for c in fake_pactl if c[:2] == ["pactl", "set-sink-input-volume"]]
    assert sets == [["pactl", "set-sink-input-volume", "45", "10000"]]  # 40000 * 0.25


def test_reduck_scales_from_saved_original_not_current(fake_pactl):
    ducking.duck(0.25)  # -> 10000
    ducking.duck(0.50)  # must be 50% of ORIGINAL 40000 = 20000, not of 10000
    sets = [c[3] for c in fake_pactl if c[:2] == ["pactl", "set-sink-input-volume"]]
    assert sets == ["10000", "20000"]


def test_restore_returns_to_original_and_clears(fake_pactl):
    ducking.duck(0.25)
    ducking.restore()
    last = [c for c in fake_pactl if c[:2] == ["pactl", "set-sink-input-volume"]][-1]
    assert last == ["pactl", "set-sink-input-volume", "45", "40000"]
    assert ducking._saved == {}


def test_noop_when_nothing_playing(monkeypatch):
    ducking._saved.clear()
    monkeypatch.setattr(ducking.subprocess, "run", lambda args, **kw: _Proc(""))  # empty list
    ducking.duck(0.25)  # must not raise
    ducking.restore()
    assert ducking._saved == {}
