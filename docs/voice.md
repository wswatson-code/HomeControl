# Phase 5 — Voice (wake word + STT + TTS)

Hands-free control on a single unit: say the wake word, give a command, the unit acts and
speaks back. Fully on-device — no cloud. Music control + countdown timers/alarms.

```
mic ─▶ openWakeWord ─▶ (wake) ─▶ record ─▶ whisper.cpp ─▶ intent ─▶ Core API ─▶ Piper ─▶ speaker
                                                                       │
                                                                       └▶ /internal/voice/state ─▶ kiosk overlay
```

## Architecture

`homecontrol-voice` is a **separate service**, not part of the Core Service — same split as
librespot, and for the same reasons: the ML stack (openWakeWord, whisper.cpp, Piper) is heavy
native code that shouldn't live in the core venv, and a crash in the pipeline must not take
down playback or the UI. It runs as the **desktop session user** (it needs that user's
PipeWire mic + speaker) and acts purely as an **API client**: recognized commands call the
existing `POST /api/player/*` and `POST /api/timer`, and the pipeline POSTs its phase to
`/internal/voice/state` so the kiosk can show a listening overlay.

Timers live in the **Core Service**, not here — so they survive a voice restart, show on the
kiosk even when set by touch, and fire regardless of what created them. A fired timer rings
in the **browser** (Web Audio, no shipped asset) and stays in the list until dismissed.

## Prerequisites

- Phase 0 installed and the Core Service running.
- The audio HAT working end to end — **mic and speaker** (see [audio-hat.md](audio-hat.md)).
  Voice is dead without a working capture source; validate `pw-record` first.

## Install

```bash
sudo ./provisioning/phase5-voice.sh      # builds whisper.cpp, downloads models, installs the unit
sudo systemctl enable --now homecontrol-voice
journalctl -u homecontrol-voice -f
```

The script builds whisper.cpp from source (a few minutes on a Pi 5), fetches the `tiny.en`
model, installs Piper + an English voice, and pre-downloads the openWakeWord models. If a
model download URL has moved it prints a manual-fetch note — grab the file into
`/opt/homecontrol/voice/models` and re-run; the script is idempotent.

## Use

Say the wake word (**"hey jarvis"** by default), then a command:

| Say | Does |
|-----|------|
| "play" / "pause" / "stop" | play / pause |
| "next" / "skip" | next track |
| "previous" / "go back" | previous track |
| "turn it up" / "louder" | volume up a step |
| "turn it down" / "quieter" | volume down a step |
| "set volume to 40" | absolute volume |
| "mute" | volume 0 |
| "set a timer for 10 minutes" | countdown timer (rings + shows on kiosk) |
| "set an alarm for 1 hour 30 minutes" | same, longer |

The kiosk shows a listening overlay through the listen → think → speak phases; active timers
sit bottom-right and pulse/ring when they fire (tap ✕ to dismiss).

## Configuration (`/etc/homecontrol/unit.env`)

| Var | Default | Notes |
|-----|---------|-------|
| `HOMECONTROL_VOICE_WAKE_MODEL` | `hey_jarvis` | one or more (comma-separated) bundled names and/or `.onnx` paths; wakes on any |
| `HOMECONTROL_VOICE_WAKE_THRESHOLD` | `0.5` | raise if it triggers on noise, lower if it misses |
| `HOMECONTROL_VOICE_COMMAND_SECONDS` | `5` | how long it records after the wake word |
| `HOMECONTROL_VOICE_INPUT_DEVICE` | (empty) | PipeWire source; empty = system default (the HAT) |
| `HOMECONTROL_VOICE_OUTPUT_DEVICE` | (empty) | PipeWire sink for TTS; empty = default |
| `HOMECONTROL_VOICE_WHISPER_MODEL` | `…/ggml-tiny.en.bin` | swap for `base.en` for more accuracy, more CPU |

After editing: `sudo systemctl restart homecontrol-voice`.

**Multiple wake words.** Set a comma-separated list and the unit triggers on any of them:

```
HOMECONTROL_VOICE_WAKE_MODEL=hey_jarvis,alexa
```

Bundled openWakeWord names: `alexa`, `hey_jarvis`, `hey_mycroft`, `hey_rhasspy`. You can
also point at your own `.onnx` wake-word models by path. All listed models are loaded and
scored every frame, so adding more has a small CPU cost — keep it to a couple on a Pi 5.

## Troubleshooting

**Nothing happens on the wake word** — almost always the mic, in this order:

1. **Capture is silent (level 0).** The WM8960 mic path comes up muted/unrouted on the
   mainline overlay. Enable LINPUT1/RINPUT1 and persist — see the **Mic (input)** section of
   [audio-hat.md](audio-hat.md). Validate with the `parec`/level check there before blaming
   the model.
2. **Default source comes up empty.** Pin the mic explicitly:
   ```
   HOMECONTROL_VOICE_INPUT_DEVICE=alsa_input.platform-soc_107c000000_sound.stereo-fallback
   ```
   (the source name from `pactl list short sources`). The default-source capture path is
   flaky; the explicit name is deterministic.
3. **Audio's fine but it won't trigger** — lower `HOMECONTROL_VOICE_WAKE_THRESHOLD` (try 0.3).

To see live scores while you speak, run the parec + openWakeWord snippet from the bring-up
notes; `mic_level` moving but score flat = recognition/threshold, `mic_level` flat = capture.

**Wakes but misrecognizes** — `tiny.en` is fast but rough. Switch the model to `base.en`
(download it, point `HOMECONTROL_VOICE_WHISPER_MODEL` at it). Expect higher latency.

**No TTS reply** — Piper binary/voice path wrong, or the output device. The pipeline plays
via `paplay`; confirm `paplay` works as the desktop user and the voice paths in `unit.env`
exist.

**Timer doesn't ring on the kiosk** — the alarm uses Web Audio, which Chromium blocks without
a user gesture. The kiosk launches with `--autoplay-policy=no-user-gesture-required`; if you
changed the launch flags, restore it.
