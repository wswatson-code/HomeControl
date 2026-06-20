"""Map a transcribed command to an intent. Pure Python, no ML — fully unit-tested.

whisper.cpp hands us free-form text ("set a timer for ten minutes", "turn it up a bit").
We normalize and keyword/regex-match it to a small, closed set of intents the unit can act
on. Deliberately forgiving: spoken numbers ("ten") and digits ("10") both work, filler is
ignored, and anything we don't understand returns UNKNOWN so the caller can say "sorry".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class IntentKind(StrEnum):
    PLAY = "play"
    PAUSE = "pause"
    NEXT = "next"
    PREVIOUS = "previous"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    SET_VOLUME = "set_volume"  # args: {"volume": 0-100}
    CREATE_TIMER = "create_timer"  # args: {"duration_ms": int, "label": str}
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Intent:
    kind: IntentKind
    args: dict = field(default_factory=dict)


# --- number words ----------------------------------------------------------------

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60}
_NUMBER_WORDS = _ONES | _TENS


def _run_has_number(tokens: list[str]) -> bool:
    """True if the contiguous run starting here contains a real number word/digit."""
    for tok in tokens:
        if tok.isdigit() or tok in _NUMBER_WORDS:
            return True
        if tok in ("a", "an"):
            continue
        return False
    return False


def _words_to_number(tokens: list[str]) -> int | None:
    """Turn a run of number tokens into an int: ['twenty', 'five'] -> 25, ['10'] -> 10.

    'a'/'an' counts as 1 only when it's the article standing in for a number ('a minute'),
    not when a real number follows it ('a 3 minute timer' -> 3, the 'a' is just an article).
    """
    total = 0
    seen = False
    for i, tok in enumerate(tokens):
        if tok.isdigit():
            total += int(tok)
            seen = True
        elif tok in _TENS:
            total += _TENS[tok]
            seen = True
        elif tok in _ONES:
            total += _ONES[tok]
            seen = True
        elif tok in ("a", "an"):
            if not _run_has_number(tokens[i:]):
                total += 1
                seen = True
            # else: article before a real number — skip it
        else:
            break
    return total if seen else None


# --- duration parsing ------------------------------------------------------------

_UNIT_MS = {
    "hour": 3_600_000, "hours": 3_600_000, "hr": 3_600_000, "hrs": 3_600_000,
    "minute": 60_000, "minutes": 60_000, "min": 60_000, "mins": 60_000,
    "second": 1000, "seconds": 1000, "sec": 1000, "secs": 1000,
}


def _parse_duration_ms(tokens: list[str]) -> int:
    """Sum every '<number> <unit>' group: '1 hour 30 minutes' -> 5400000. 0 if none."""
    total = 0
    i = 0
    while i < len(tokens):
        if tokens[i] in _UNIT_MS:
            # No leading number (e.g. "a minute" already consumed, or bare "minute") -> 1.
            total += _UNIT_MS[tokens[i]]
            i += 1
            continue
        num = _words_to_number(tokens[i:])
        if num is not None:
            # Find the unit token right after the number run.
            j = i
            while j < len(tokens) and (
                tokens[j].isdigit() or tokens[j] in _NUMBER_WORDS or tokens[j] in ("a", "an")
            ):
                j += 1
            if j < len(tokens) and tokens[j] in _UNIT_MS:
                total += num * _UNIT_MS[tokens[j]]
                i = j + 1
                continue
        i += 1
    return total


_FILLER = re.compile(r"[^a-z0-9 ]+")


def _normalize(text: str) -> list[str]:
    return _FILLER.sub(" ", text.lower()).split()


# --- matching --------------------------------------------------------------------


def parse(text: str) -> Intent:
    """Parse a transcript into an Intent. Order matters: more specific first."""
    tokens = _normalize(text)
    joined = " ".join(tokens)
    if not tokens:
        return Intent(IntentKind.UNKNOWN)

    # Timers — match on the word "timer"/"alarm" so "set a timer" never trips the volume
    # "set" branch below.
    if "timer" in tokens or "alarm" in tokens:
        duration = _parse_duration_ms(tokens)
        if duration > 0:
            label = _timer_label(tokens)
            return Intent(IntentKind.CREATE_TIMER, {"duration_ms": duration, "label": label})
        return Intent(IntentKind.UNKNOWN)

    # Volume — explicit set, then relative.
    if "volume" in tokens or "sound" in tokens:
        num = _find_first_number(tokens)
        if num is not None and any(w in joined for w in ("set", "make", "to", "at", "percent")):
            return Intent(IntentKind.SET_VOLUME, {"volume": max(0, min(100, num))})
    if "mute" in tokens:
        return Intent(IntentKind.SET_VOLUME, {"volume": 0})
    if any(w in joined for w in ("louder", "turn it up", "turn up", "volume up", "increase")):
        return Intent(IntentKind.VOLUME_UP)
    if any(w in joined for w in ("quieter", "softer", "turn it down", "turn down", "volume down", "decrease")):
        return Intent(IntentKind.VOLUME_DOWN)
    # bare "set volume to 40" handled above; bare "volume 40"
    if "volume" in tokens:
        num = _find_first_number(tokens)
        if num is not None:
            return Intent(IntentKind.SET_VOLUME, {"volume": max(0, min(100, num))})

    # Transport.
    if any(w in tokens for w in ("next", "skip", "forward")):
        return Intent(IntentKind.NEXT)
    if any(w in joined for w in ("previous", "go back", "last track", "back")):
        return Intent(IntentKind.PREVIOUS)
    if any(w in tokens for w in ("pause", "stop")):
        return Intent(IntentKind.PAUSE)
    if any(w in tokens for w in ("play", "resume", "unpause")):
        return Intent(IntentKind.PLAY)

    return Intent(IntentKind.UNKNOWN)


def _find_first_number(tokens: list[str]) -> int | None:
    for i, tok in enumerate(tokens):
        if tok.isdigit() or tok in _NUMBER_WORDS:
            return _words_to_number(tokens[i:])
    return None


def _timer_label(tokens: list[str]) -> str:
    """Best-effort label after 'for' that isn't the duration, e.g. 'timer for pasta'."""
    if "for" in tokens:
        tail = tokens[tokens.index("for") + 1:]
        words = [
            t for t in tail
            if not t.isdigit() and t not in _NUMBER_WORDS and t not in _UNIT_MS and t not in ("a", "an", "and")
        ]
        return " ".join(words)
    return ""
