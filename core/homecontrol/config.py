"""Runtime configuration, env-driven.

Every setting is overridable via `HOMECONTROL_*` env vars (or a `.env` file), so the
same image runs in dev (mock provider, any OS) and on a real Pi unit (real backends).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOMECONTROL_", env_file=".env", extra="ignore")

    # HTTP server
    host: str = "0.0.0.0"
    port: int = 8080

    # Unit identity (overridden per device during provisioning)
    unit_id: str = "dev-unit"
    room: str = "Dev Room"

    # Which Spotify provider to use. "mock" needs no hardware/credentials and is the
    # Phase 1 default; "librespot" is the real Phase 2 backend.
    spotify_provider: str = "mock"

    # --- Phase 2: librespot + Spotify Web API (only used when provider == "librespot")
    #
    # OAuth: a one-time authorization-code pairing yields a long-lived refresh token,
    # stored here. The Core Service exchanges it for short-lived access tokens at runtime.
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_refresh_token: str = ""

    # The Connect device name librespot advertises (also how we find its device_id in
    # the Web API). Defaults to the room so each unit is distinct in the Spotify app.
    # (librespot's own process args — binary, audio backend, FIFO — live in the unit's
    # systemd service, since librespot runs as a separate service, not spawned here.)
    spotify_device_name: str = ""

    def resolved_device_name(self) -> str:
        return self.spotify_device_name or self.room


settings = Settings()
