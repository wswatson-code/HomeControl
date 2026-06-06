"""Spotify Web API client — metadata + control plane for the librespot device.

librespot is the *playback* engine (a Connect receiver). It does not expose a rich
control API, so we drive it the way the Spotify app does: through the Web API's player
endpoints, targeting librespot's `device_id`. Track metadata (title/artist/art) also
comes from here, since `--onevent` only gives us a bare track id.

Auth: a one-time authorization-code pairing produces a refresh token (in config); this
client exchanges it for short-lived access tokens and refreshes them as they expire.

Premium-only, and a known Spotify quirk: the target device must be *active* before
some control calls succeed — `ensure_active()` transfers playback to it first.
"""

from __future__ import annotations

import base64
import time

import httpx

from ..models import Track

_API = "https://api.spotify.com/v1"
_TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105 — public OAuth endpoint
_REFRESH_SKEW_S = 60  # refresh a little before actual expiry


class SpotifyError(RuntimeError):
    pass


class SpotifyWebClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, device_name: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._device_name = device_name
        self._http = httpx.AsyncClient(timeout=10.0)
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._device_id: str | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- auth ------------------------------------------------------------------

    async def _token(self) -> str:
        if self._access_token and time.monotonic() < self._expires_at - _REFRESH_SKEW_S:
            return self._access_token
        basic = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
        resp = await self._http.post(
            _TOKEN_URL,
            headers={"Authorization": f"Basic {basic}"},
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
        )
        if resp.status_code != 200:
            raise SpotifyError(f"token refresh failed: {resp.status_code} {resp.text}")
        body = resp.json()
        self._access_token = body["access_token"]
        self._expires_at = time.monotonic() + body.get("expires_in", 3600)
        return self._access_token

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._token()}"}

    async def _request(self, method: str, path: str, **kw) -> httpx.Response:
        resp = await self._http.request(method, f"{_API}{path}", headers=await self._headers(), **kw)
        if resp.status_code == 401:  # token revoked mid-flight — force one refresh + retry
            self._access_token = None
            resp = await self._http.request(method, f"{_API}{path}", headers=await self._headers(), **kw)
        return resp

    # --- device targeting ------------------------------------------------------

    async def device_id(self, *, refresh: bool = False) -> str | None:
        """Resolve our librespot device's id by its advertised name (cached)."""
        if self._device_id and not refresh:
            return self._device_id
        resp = await self._request("GET", "/me/player/devices")
        if resp.status_code != 200:
            return None
        for dev in resp.json().get("devices", []):
            if dev.get("name") == self._device_name:
                self._device_id = dev["id"]
                return self._device_id
        return None

    async def ensure_active(self) -> None:
        """Transfer playback to our device so subsequent control calls land on it."""
        did = await self.device_id(refresh=True)
        if did:
            await self._request("PUT", "/me/player", json={"device_ids": [did], "play": False})

    def _device_q(self) -> dict:
        return {"device_id": self._device_id} if self._device_id else {}

    # --- metadata --------------------------------------------------------------

    async def get_track(self, track_id: str) -> Track | None:
        tid = track_id.rsplit(":", 1)[-1]  # accept "spotify:track:ID" or bare ID
        resp = await self._request("GET", f"/tracks/{tid}")
        if resp.status_code != 200:
            return None
        t = resp.json()
        return Track(
            id=tid,
            title=t.get("name", ""),
            artist=", ".join(a["name"] for a in t.get("artists", [])),
            album=t.get("album", {}).get("name", ""),
            artwork_url=_first_image(t.get("album", {}).get("images", [])),
            duration_ms=t.get("duration_ms", 0),
        )

    async def get_playback(self) -> dict | None:
        """Raw GET /me/player — used to reconcile drift. None when nothing is active."""
        resp = await self._request("GET", "/me/player")
        if resp.status_code == 204 or resp.status_code != 200:
            return None
        return resp.json()

    # --- control ---------------------------------------------------------------

    async def play(self) -> None:
        await self._request("PUT", "/me/player/play", params=self._device_q())

    async def pause(self) -> None:
        await self._request("PUT", "/me/player/pause", params=self._device_q())

    async def next(self) -> None:
        await self._request("POST", "/me/player/next", params=self._device_q())

    async def previous(self) -> None:
        await self._request("POST", "/me/player/previous", params=self._device_q())

    async def seek(self, position_ms: int) -> None:
        await self._request("PUT", "/me/player/seek", params={"position_ms": position_ms, **self._device_q()})

    async def set_volume(self, volume_percent: int) -> None:
        await self._request("PUT", "/me/player/volume", params={"volume_percent": volume_percent, **self._device_q()})


def _first_image(images: list[dict]) -> str | None:
    return images[0]["url"] if images else None
