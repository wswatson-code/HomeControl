"""HomeControl Core Service.

The orchestrator that wires together Spotify (librespot), multi-room sync (Snapcast),
the voice pipeline, the intercom (WebRTC), and Home Assistant — and exposes a single
versioned REST + WebSocket API consumed by the kiosk UI and the mobile app.
"""

__version__ = "0.1.0"
