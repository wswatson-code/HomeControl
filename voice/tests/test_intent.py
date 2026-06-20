"""Intent parser tests — the one piece of the voice pipeline testable off-hardware."""

from __future__ import annotations

import pytest

from homecontrol_voice.intent import Intent, IntentKind, parse


@pytest.mark.parametrize(
    "text,kind",
    [
        ("play", IntentKind.PLAY),
        ("resume the music", IntentKind.PLAY),
        ("pause", IntentKind.PAUSE),
        ("stop", IntentKind.PAUSE),
        ("next", IntentKind.NEXT),
        ("skip this song", IntentKind.NEXT),
        ("previous track", IntentKind.PREVIOUS),
        ("go back", IntentKind.PREVIOUS),
        ("turn it up", IntentKind.VOLUME_UP),
        ("louder", IntentKind.VOLUME_UP),
        ("turn it down", IntentKind.VOLUME_DOWN),
        ("quieter please", IntentKind.VOLUME_DOWN),
        ("mute", IntentKind.SET_VOLUME),
    ],
)
def test_simple_intents(text, kind):
    assert parse(text).kind == kind


def test_mute_sets_zero():
    assert parse("mute").args["volume"] == 0


@pytest.mark.parametrize(
    "text,volume",
    [
        ("set volume to 40", 40),
        ("set the volume to fifty", 50),
        ("volume 75 percent", 75),
        ("make the volume 20", 20),
        ("set volume to 150", 100),  # clamped
    ],
)
def test_set_volume(text, volume):
    intent = parse(text)
    assert intent.kind == IntentKind.SET_VOLUME
    assert intent.args["volume"] == volume


@pytest.mark.parametrize(
    "text,ms",
    [
        ("set a timer for 10 minutes", 600_000),
        ("set a timer for ten minutes", 600_000),
        ("timer for 5 minutes 30 seconds", 330_000),
        ("set a 3 minute timer", 180_000),
        ("set an alarm for 1 hour", 3_600_000),
        ("timer for 1 hour 30 minutes", 5_400_000),
        ("set a timer for twenty five seconds", 25_000),
        ("set a timer for a minute", 60_000),
    ],
)
def test_create_timer_durations(text, ms):
    intent = parse(text)
    assert intent.kind == IntentKind.CREATE_TIMER
    assert intent.args["duration_ms"] == ms


def test_timer_label():
    intent = parse("set a timer for 10 minutes for pasta")
    assert intent.kind == IntentKind.CREATE_TIMER
    assert intent.args["duration_ms"] == 600_000
    assert "pasta" in intent.args["label"]


def test_timer_without_duration_is_unknown():
    # "set a timer" with no time we can parse — better to ask again than guess.
    assert parse("set a timer").kind == IntentKind.UNKNOWN


def test_timer_beats_volume_set_branch():
    # "set a timer ..." must not be hijacked by the volume "set" keyword.
    assert parse("set a timer for 2 minutes").kind == IntentKind.CREATE_TIMER


@pytest.mark.parametrize(
    "text,kind",
    [
        ("go back", IntentKind.PREVIOUS),
        ("back", IntentKind.PREVIOUS),
        ("previous", IntentKind.PREVIOUS),
        # "back" must not hijack a PLAY, and must be a token not a substring.
        ("play that song back", IntentKind.PLAY),
        ("playback", IntentKind.UNKNOWN),
    ],
)
def test_back_does_not_hijack_play(text, kind):
    assert parse(text).kind == kind


@pytest.mark.parametrize("text", ["", "what's the weather", "tell me a joke", "asdf qwer"])
def test_unknown(text):
    assert parse(text).kind == IntentKind.UNKNOWN


def test_intent_is_hashable_value():
    # frozen dataclass — safe to use as a stable value.
    assert isinstance(parse("play"), Intent)
