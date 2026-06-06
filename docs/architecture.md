# HomeControl — Architecture

High-level structure of the system and the reasoning behind the major choices. For how
the current code is organized, see [`design.md`](design.md).

## Goals & constraints

A fixed-function appliance, one per room, that:

- plays Spotify with touch + voice control,
- synchronizes audio across rooms (multi-room),
- works as a hands-free voice intercom between units,
- controls smart-home devices (lights / thermostat / cameras),
- is configurable and controllable from iOS/Android.

Constraints that shape everything: a **Raspberry Pi 5 (8GB)** per unit, an **800×480**
touchscreen, **LAN-first** (no cloud dependency for core function), and Spotify
**Premium** (a librespot requirement).

The guiding principle is **integration over invention**: proven open components do the
hard parts; our code orchestrates them, presents the UI, and defines the inter-unit
protocol.

## Per-unit architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Chromium (kiosk)  ──HTTP/WebSocket──►  Core Service (Python)  │
│  Svelte web app                         FastAPI + asyncio     │
└──────────────────────────────────────────────────────────────┘
        Core Service orchestrates the following local services:
  ┌───────────────┬──────────────┬───────────────┬─────────────┐
  │ librespot     │ Snapcast     │ Voice pipeline│ Intercom    │
  │ (Spotify      │ server/client│ wakeword→STT  │ WebRTC peer │
  │  Connect rcv) │ (sync audio) │ →NLU→Piper TTS│ (AEC/NS)    │
  └───────┬───────┴──────┬───────┴───────┬───────┴──────┬──────┘
          └──────────────┴── PipeWire (mix + duck) ──────┘
        Inter-unit: Zeroconf/mDNS discovery + WebSocket mesh

  Smart home:  Core Service ──REST/WebSocket──► Home Assistant (separate host)
  Mobile:      Flutter app  ──mDNS discover──► Core Service REST/WebSocket (LAN)
```

The **Core Service** is the only stateful brain on a unit and the single source of truth
for its state. Everything else is either a UI onto the Core Service (kiosk, mobile) or a
specialized subsystem it supervises (librespot, Snapcast, voice, intercom). UI clients
never talk to a subsystem directly — they go through the Core Service API.

### Subsystems (and their phase)

| Subsystem | Component | Role | Phase |
|-----------|-----------|------|------:|
| Spotify playback | **librespot** | Spotify Connect receiver; audio source | 2 ✅ |
| Spotify metadata + control | **Spotify Web API** | track info, transport control of the device | 2 ✅ |
| Multi-room sync | **Snapcast** | sample-synchronized playback across units | 3 |
| Discovery | **Zeroconf/mDNS (Avahi)** | units & phones find each other by room name | 4 |
| Inter-unit messaging | **WebSocket mesh** | state sync, group commands, intercom signaling | 4 |
| Wake word | **openWakeWord** | low-power local trigger | 5 |
| Speech-to-text | **Vosk** (commands) / **whisper.cpp** (free-form) | local transcription | 5 |
| NLU fallback | **Claude API** | intent parsing for free-form requests | 5 |
| Text-to-speech | **Piper** | spoken responses | 5 |
| Intercom | **aiortc / WebRTC** | hands-free voice with built-in AEC/NS | 6 |
| Smart home | **Home Assistant** (separate host) | lights, climate, cameras behind one API | 6.5 |
| Audio mixing | **PipeWire** | mixes music + TTS + intercom; ducking | 0/5 |

## Audio pipeline

A single output sink is shared by music, TTS, and intercom, so mixing and ducking are
central. **PipeWire** (default on Pi OS Bookworm) is the mixer.

```
 librespot ──┐                              (Phase 2: pulseaudio backend → direct out)
             │  Phase 3+: raw PCM → FIFO
             ▼
        snapserver (group leader) ──network──► snapclient on each unit
                                                     │
 Piper TTS ──────────────────────────────────────►  ├─► PipeWire sink ─► speaker
 Intercom (WebRTC) ─────────────────────────────►   │      (ducking: music down
                                                     ┘       while TTS/intercom play)
```

In Phase 2 librespot writes straight to PipeWire (the `pulseaudio` backend) so a single
unit makes sound. From Phase 3 its output becomes a FIFO that Snapcast reads, so the same
stream can be played in sample-sync on every unit in a group. The group **leader** runs
`snapserver`; every unit (including the leader) runs `snapclient`.

## System (multi-unit) topology

Units are peers. There is no central server; **Home Assistant** is the only always-on
external dependency, and only for smart-home features.

```
   ┌─────────┐   mDNS discovery + WebSocket mesh    ┌─────────┐
   │ Kitchen │◄────────────────────────────────────►│ Bedroom │
   │  unit   │                                       │  unit   │
   └────┬────┘                                       └────┬────┘
        │            ┌─────────┐                          │
        └───────────►│ Office  │◄─────────────────────────┘
                     │  unit   │
                     └─────────┘
   Phones (Flutter) join the mesh's edge as LAN clients of any unit.
   Home Assistant runs on its own host; each unit is an HA API client.
```

- **Discovery (Phase 4):** each Core Service advertises a `_homecontrol._tcp` mDNS
  service with its room name; units and phones resolve peers without configuration.
- **Mesh (Phase 4):** a lightweight WebSocket mesh between Core Services carries shared
  state, multi-room group membership, and intercom call signaling. MQTT is the fallback
  if the mesh becomes unwieldy.
- **Groups (Phase 3):** a multi-room group is a set of units with one elected leader
  hosting `snapserver`; members run `snapclient` pointed at it.

## Key decisions & rationale

- **Python + FastAPI/asyncio for the Core Service.** The voice stack (openWakeWord,
  vosk, piper) and `aiortc`, `zeroconf` are first-class in Python; asyncio fits an
  event-driven orchestrator coordinating many I/O subsystems.
- **Web kiosk UI (Svelte + Chromium), not native.** Fastest iteration for a fixed
  800×480 layout; one process serves API + UI; the same API backs the mobile app.
- **librespot for Spotify.** The only practical way to be a Spotify Connect receiver on
  a Pi. Premium-only. We control it via the Web API (as the Spotify app does) rather than
  a bespoke protocol, and read fast state from its `--onevent` hooks.
- **Snapcast for multi-room.** The de-facto open solution for sample-synchronized
  whole-home audio on Linux; integrates with librespot via a FIFO source.
- **Home Assistant for smart home, as a client.** Google's Assistant SDK device control
  is deprecated and the Nest SDM API covers only Nest devices (and is cloud-only). HA
  already speaks Nest, lights, climate, and cameras behind one REST/WebSocket API, so we
  integrate once instead of per-vendor. HA runs on a **separate host** to avoid resource
  contention with voice/audio/UI on a unit.
- **Hybrid voice.** Local wake word + local command grammar for the common, latency-
  sensitive cases; cloud NLU (Claude) only for the free-form long tail. Privacy and
  offline-resilience by default.
- **WebRTC for intercom.** Built-in acoustic echo cancellation, noise suppression, and
  jitter buffering — essential for *hands-free* intercom while music plays.
- **Flutter for mobile.** One codebase for iOS + Android; the app is a thin LAN client
  of the Core Service API (control + config only), so no backend logic is duplicated.

## The API contract

The Core Service's REST + WebSocket API is a **versioned, documented contract** consumed
by both the kiosk and the Flutter app. It is exported to `api/openapi.json` and CI fails
if the committed schema drifts from the code, so the two clients never diverge. Internal
endpoints (e.g. the librespot event hook) are excluded from the schema.

## Cross-cutting concerns

- **Resilience.** Every subsystem runs under systemd with `Restart=always`; the Core
  Service supervises logical health and the UI auto-reconnects its WebSocket. A subsystem
  crash degrades one capability, not the appliance.
- **Security.** LAN-first; no inbound internet. Internal endpoints are localhost-only.
  Mobile clients will pair with a per-unit token (Phase 6.7). Remote (off-LAN) access is
  deferred and, when added, goes through a VPN (Tailscale/WireGuard) before any relay.
- **Privacy.** Voice is processed locally by default; only free-form fallback leaves the
  unit. No always-on cloud microphone.

## Known hard problems

1. **Hands-free intercom + simultaneous music = echo/feedback.** Mitigated by a mic array
   with hardware AEC, WebRTC AEC/NS, and ducking music on the receiving unit. This is the
   single biggest technical risk and gets a real test bench early.
2. **librespot stability.** 2025 builds saw HTTP 500 / NonPlayable regressions; pin a
   known-good version and supervise it.
3. **Wake-word false triggers** opening an intercom channel. Two-stage phrasing,
   confirmation chime, hard mute.
4. **Audio routing contention** between music, TTS, and intercom — owned by PipeWire.
5. **Spotify multi-room is a ToS grey area** (capturing librespot output into Snapcast is
   the standard raspotify+snapcast pattern, but noted).
