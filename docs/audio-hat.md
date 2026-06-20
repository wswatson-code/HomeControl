# Audio HAT setup — ReSpeaker 2-Mic (WM8960) on Pi 5

The unit uses a ReSpeaker 2-Mic HAT (WM8960 codec over I2S) for speaker output and mic
input. Getting it working on a **Pi 5** has one hard requirement and a few persistence
gotchas. Read this before touching a new unit — it's the difference between 5 minutes and
an afternoon.

## The one rule: use the in-kernel overlay, NOT Seeed's driver

Seeed's out-of-tree `seeed-voicecard` driver **does not configure MCLK on the Pi 5's RP1
I2S**. The card enumerates, PipeWire shows a sink, the mixer looks perfect — and there is
zero sound, with the kernel logging on every playback attempt:

```
wm8960 1-001a: No MCLK configured
wm8960 ... ASoC error (-22): at snd_soc_dai_hw_params() on wm8960-hifi
```

No mixer setting can fix a codec with no master clock. The mainline `wm8960-soundcard`
overlay (same codec, maintained in-tree) configures MCLK correctly.

In `/boot/firmware/config.txt`:

```
# Remove any Seeed lines: dtoverlay=seeed-2mic-voicecard (and its i2s helpers)
dtoverlay=wm8960-soundcard
```

If the Seeed installer was ever run, also disable its mixer-restore service (it targets the
dead card instance and will fight you):

```bash
sudo systemctl disable --now seeed-voicecard
```

After reboot the card is `wm8960-soundcard` (`aplay -l`), driver `snd_soc_simple_card`, and
`dmesg | grep -i mclk` is clean.

## Mixer: the WM8960 boots silent

A fresh card instance comes up muted with the DAC unrouted. Set it once and persist:

```bash
amixer -c 2 sset 'Playback' 100% unmute
amixer -c 2 sset 'Headphone' 80% unmute
amixer -c 2 sset 'Left Output Mixer PCM' on      # route DAC -> output mixer (the usual culprit)
amixer -c 2 sset 'Right Output Mixer PCM' on
amixer -c 2 sset 'Mono Output Mixer Left' on     # OUT3 = capless headphone ground reference
amixer -c 2 sset 'Mono Output Mixer Right' on
sudo alsactl store 2
```

(`-c 2` assumes the wm8960 is card 2 — check `aplay -l`. The `Mono Output Mixer` controls
are what make the **headphone jack** produce sound; without them it's dead even at full
volume.) The system `alsa-restore` service reloads this saved state at boot.

## PipeWire: profile, sink name, default

The mainline overlay exposes proper analog profiles. Use the duplex one (output + mic) and
route output to the headphone jack:

```bash
sudo -u <desktop-user> XDG_RUNTIME_DIR=/run/user/<uid> \
  pactl set-card-profile <card-id> 'output:stereo-fallback+input:stereo-fallback'
sudo -u <desktop-user> XDG_RUNTIME_DIR=/run/user/<uid> \
  pactl set-sink-port alsa_output.platform-soc_107c000000_sound.stereo-fallback analog-output-headphones
```

The sink name is then
`alsa_output.platform-soc_107c000000_sound.stereo-fallback` (stable across reboots — it's
the hardware path). Set it for librespot in `/etc/homecontrol/unit.env`:

```
HOMECONTROL_LIBRESPOT_DEVICE=alsa_output.platform-soc_107c000000_sound.stereo-fallback
```

Make it the system default too (so desktop sounds and the Phase 5 voice mic use the HAT):

```bash
sudo -u <desktop-user> XDG_RUNTIME_DIR=/run/user/<uid> wpctl set-default <seeed-sink-id>
```

> `pactl`/`paplay` come from the `pulseaudio-utils` package — installed by `install.sh`.
> `wpctl` IDs renumber every boot; the sink **name** does not. Always set defaults against
> the card the `wpctl status` output shows as `Built-in Audio` (wm8960), not HDMI.

## Persistence — verify with a reboot

Three separate things must survive a power cycle; check each by rebooting and playing a
sound with no arguments:

```bash
sudo -u <desktop-user> XDG_RUNTIME_DIR=/run/user/<uid> paplay /usr/share/sounds/alsa/Front_Center.wav
```

| Survives? | Mechanism | If not |
|-----------|-----------|--------|
| Mixer un-mute | `alsactl store 2` → `alsa-restore.service` | re-store; confirm `alsa-restore` covers card 2 |
| Profile + port | WirePlumber state | add a WirePlumber rule pinning the profile |
| Default sink | WirePlumber `default-nodes` | HDMI's priority (5900) can win — add a default-device rule |

Sound on a bare `paplay` after reboot = all three held. librespot is pinned by name, so it
plays regardless of the default — but the default still matters for voice (Phase 5).

## Mic (input)

The duplex profile also exposes the mic source
`alsa_input.platform-soc_107c000000_sound.stereo-fallback`. Phase 5 (voice) consumes it; you
can validate it now.

**The mainline overlay brings the mic up muted/unrouted.** Unlike Seeed's driver, the
in-kernel `wm8960-soundcard` doesn't know the HAT's mic wiring, so the capture stream runs
but delivers pure silence (level 0) until you route the mics. On the ReSpeaker 2-Mic HAT the
mics sit on **LINPUT1 / RINPUT1**:

```bash
amixer -c 2 sset 'Capture' 75% cap
amixer -c 2 sset 'Left Input Mixer Boost' on
amixer -c 2 sset 'Right Input Mixer Boost' on
amixer -c 2 sset 'Left Boost Mixer LINPUT1' on
amixer -c 2 sset 'Right Boost Mixer RINPUT1' on
amixer -c 2 sset 'Left Input Boost Mixer LINPUT1' 3   # PGA boost (+29 dB)
amixer -c 2 sset 'Right Input Boost Mixer LINPUT1' 3
amixer -c 2 sset 'ADC PCM' 75%
sudo alsactl store 2                                   # persist, or it's silent after reboot
```

Verify capture has signal — record 3 s while talking and check the level (parec, not
pw-record: PortAudio's ALSA→pulse bridge times out on PipeWire, so the voice service and
these checks use the native pulse client):

```bash
SRC=alsa_input.platform-soc_107c000000_sound.stereo-fallback
timeout 3 parec --format=s16le --rate=16000 --channels=1 -d "$SRC" > /tmp/spoke.pcm
python3 -c "import numpy as np; a=np.fromfile('/tmp/spoke.pcm',dtype=np.int16); print('level',int(np.abs(a).mean()),'max',int(np.abs(a).max()))"
```

`level` in the hundreds+ = mics live. Still ~0 → the mics are on a different input pair;
repeat the `Boost Mixer` lines for `LINPUT2/RINPUT2`, then `LINPUT3/RINPUT3`.

> **`parec` gets zero bytes / blocks** even though the source is the default and RUNNING —
> capture via the *default* source can come up empty; pass an explicit `-d <source>` (above),
> and in Phase 5 pin `HOMECONTROL_VOICE_INPUT_DEVICE` to that source name rather than relying
> on the default.
