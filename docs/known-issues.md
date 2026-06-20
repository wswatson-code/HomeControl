# Known issues / backlog

Verified defects deferred for later, from the multi-agent review of the Phase 5 diff
(2026-06-20). Each was confirmed against the code by an adversarial verifier; severity is the
verifier's corrected value. Fix when convenient — neither blocks normal operation.

## #3 — Two sequential parec streams can clip the start of a command (low, voice)

`voice/homecontrol_voice/audio.py`

`wakeword.wait_for_wake()` holds an open `parec` (via `frame_stream`) for wake detection;
on a hit the generator closes that stream, then `record()` opens a **second** `parec` on the
same source. The two are serialized (the generator's `finally` runs `proc.wait()` before
`record()` starts — it is *not* simultaneous contention), but the PipeWire stream-setup
latency between them means the first ~100 ms after the wake word isn't captured. Users speak
the command immediately after the wake word, so the **start of the phrase can be clipped**,
degrading STT accuracy.

**Fix direction:** use one long-lived `parec` capture stream for both wake detection and
command recording — after a wake hit, keep reading command frames from the same stream
instead of tearing down and reopening. Confirm on hardware that the first word survives.

**Trigger to prioritise it:** if you notice the Pi mishearing the *beginning* of commands.

## #6 — `DESKTOP_USER` detected independently per script, never persisted (low, provisioning)

`provisioning/install.sh:68`, `phase2-spotify.sh:20`, `phase5-voice.sh:18`

Each script independently computes `DESKTOP_USER="${DESKTOP_USER:-$(getent passwd 1000 ...)}"`
and renders systemd units from it. Nothing persists the chosen user or cross-checks that a
later phase renders units for the same user the kiosk was installed for. So if an operator
overrides `DESKTOP_USER` on install but forgets it on a later phase (and the desktop user is
**not** uid 1000), librespot/voice get rendered for a different user than the kiosk — the
cross-user PipeWire "Connection refused" failure the unit comments warn about.

Narrow: on a stock Pi OS image the autologin user *is* uid 1000, so with no overrides all
three scripts agree. Each script also echoes the chosen user, so it's self-diagnosing.

**Fix direction:** persist the chosen user once (e.g. write `DESKTOP_USER` into
`/etc/homecontrol/unit.env` on first install) and have `phase2`/`phase5` read it back before
the uid-1000 fallback. (Note: the review's claim that `sudo` strips `sudo VAR=val cmd` is
wrong — that form *does* pass through; only `VAR=val sudo cmd` is dropped by `env_reset`.)
