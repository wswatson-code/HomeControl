"""HomeControl voice pipeline.

A separate service (not part of the Core Service) that listens on the unit's microphone,
detects a wake word, transcribes the command with whisper.cpp, maps it to an intent, and
acts — driving playback/timers through the Core Service's HTTP API and replying with Piper
TTS. Runs as the desktop session user so it can reach the PipeWire mic + speaker.
"""

__version__ = "0.1.0"
