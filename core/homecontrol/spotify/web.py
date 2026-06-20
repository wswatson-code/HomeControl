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

from ..models import BrowseItem, Device, Track

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

    # --- browse / search (catalog plane) --------------------------------------

    async def _get_json(self, path: str, **params) -> dict:
        resp = await self._request("GET", path, params=params or None)
        if resp.status_code != 200:
            raise SpotifyError(f"GET {path} -> {resp.status_code} {resp.text}")
        return resp.json()

    async def search(
        self, query: str, types: str = "track,album,artist,playlist", limit: int = 20, offset: int = 0
    ) -> dict:
        data = await self._get_json("/search", q=query, type=types, limit=limit, offset=offset)
        out: dict = {"offset": offset, "limit": limit, "totals": {}}
        normalizers = {
            "tracks": _track_item,
            "albums": _album_item,
            "artists": _artist_item,
            "playlists": _playlist_item,
        }
        for key, fn in normalizers.items():
            if key in data:
                out[key] = [fn(x) for x in data[key]["items"] if x]
                out["totals"][key] = data[key].get("total", 0)
        return out

    async def my_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        data = await self._get_json("/me/playlists", limit=limit, offset=offset)
        items = [_playlist_item(p) for p in data.get("items", []) if p]
        return {"items": items, "total": data.get("total", 0), "offset": offset, "limit": limit}

    async def my_albums(self, limit: int = 50, offset: int = 0) -> dict:
        data = await self._get_json("/me/albums", limit=limit, offset=offset)
        items = [_album_item(it["album"]) for it in data.get("items", []) if it.get("album")]
        return {"items": items, "total": data.get("total", 0), "offset": offset, "limit": limit}

    async def playlist_tracks(self, playlist_id: str, limit: int = 100, offset: int = 0) -> dict:
        # market=from_token: required for track relinking/availability (its absence 400s).
        # Guard null items (Spotify includes them) and skip non-track entries (podcast
        # episodes have no track/artists) so one odd row can't 500 the whole playlist.
        data = await self._get_json(
            f"/playlists/{playlist_id}/tracks", market="from_token", limit=limit, offset=offset
        )
        tracks = [_to_track(it["track"]) for it in data.get("items", []) if it and it.get("track")]
        return {"tracks": tracks, "total": data.get("total", 0), "offset": offset, "limit": limit}

    async def album_tracks(self, album_id: str, limit: int = 50, offset: int = 0) -> dict:
        # Album-track items carry no album image; the UI shows the album art at the header.
        data = await self._get_json(f"/albums/{album_id}/tracks", market="from_token", limit=limit, offset=offset)
        tracks = [_to_track(t) for t in data.get("items", []) if t]
        return {"tracks": tracks, "total": data.get("total", 0), "offset": offset, "limit": limit}

    async def artist(self, artist_id: str) -> dict:
        top = await self._get_json(f"/artists/{artist_id}/top-tracks", market="from_token")
        albums = await self._get_json(f"/artists/{artist_id}/albums", include_groups="album,single", limit=50)
        return {
            "top_tracks": [_to_track(t) for t in top.get("tracks", []) if t],
            "albums": [_album_item(a) for a in albums.get("items", []) if a],
        }

    async def list_devices(self) -> list[Device]:
        data = await self._get_json("/me/player/devices")
        return [
            Device(
                id=d["id"],
                name=d.get("name", ""),
                type=d.get("type", ""),
                is_active=bool(d.get("is_active")),
                volume=d.get("volume_percent"),
            )
            for d in data.get("devices", [])
            if d.get("id")
        ]

    async def resolve_device_id(self, device_id: str | None) -> str | None:
        """Pick the device to play on: the requested one if it's currently available, else
        THIS unit's local librespot device (matched by advertised name). None means 'no
        specific device' — Spotify then uses the user's active device (last-ditch fallback).
        """
        try:
            devices = await self.list_devices()
        except SpotifyError:
            devices = []
        if device_id and any(d.id == device_id for d in devices):
            return device_id  # requested device is online — honor it
        for d in devices:  # fall back to the local librespot device by name
            if d.name == self._device_name:
                self._device_id = d.id
                return d.id
        return None

    async def play_context(
        self,
        *,
        device_id: str | None = None,
        context_uri: str | None = None,
        uris: list[str] | None = None,
        offset: int | None = None,
    ) -> None:
        target = await self.resolve_device_id(device_id)
        body: dict = {}
        if context_uri:
            body["context_uri"] = context_uri
        if uris:
            body["uris"] = uris
        if offset is not None:
            body["offset"] = {"position": offset}
        params = {"device_id": target} if target else {}
        resp = await self._request("PUT", "/me/player/play", params=params, json=body)
        if resp.status_code not in (200, 202, 204):
            raise SpotifyError(f"play -> {resp.status_code} {resp.text}")

    async def transfer(self, device_id: str, play: bool = True) -> None:
        resp = await self._request("PUT", "/me/player", json={"device_ids": [device_id], "play": play})
        if resp.status_code not in (200, 202, 204):
            raise SpotifyError(f"transfer -> {resp.status_code} {resp.text}")


def _first_image(images: list[dict]) -> str | None:
    return images[0]["url"] if images else None


def _to_track(t: dict) -> Track:
    album = t.get("album") or {}
    artists = t.get("artists") or []  # may be None/absent for episodes or malformed rows
    return Track(
        id=t.get("id") or "",
        title=t.get("name", ""),
        artist=", ".join(a["name"] for a in artists if isinstance(a, dict) and "name" in a),
        album=album.get("name", ""),
        artwork_url=_first_image(album.get("images", [])),
        duration_ms=t.get("duration_ms", 0),
    )


def _track_item(t: dict) -> BrowseItem:
    return BrowseItem(
        id=t.get("id", ""),
        uri=t.get("uri", ""),
        type="track",
        name=t.get("name", ""),
        subtitle=", ".join(a["name"] for a in t.get("artists", [])),
        image=_first_image(t.get("album", {}).get("images", [])),
    )


def _album_item(a: dict) -> BrowseItem:
    return BrowseItem(
        id=a.get("id", ""),
        uri=a.get("uri", ""),
        type="album",
        name=a.get("name", ""),
        subtitle=", ".join(x["name"] for x in a.get("artists", [])),
        image=_first_image(a.get("images", [])),
    )


def _artist_item(a: dict) -> BrowseItem:
    return BrowseItem(
        id=a.get("id", ""),
        uri=a.get("uri", ""),
        type="artist",
        name=a.get("name", ""),
        subtitle="Artist",
        image=_first_image(a.get("images", [])),
    )


def _playlist_item(p: dict) -> BrowseItem:
    return BrowseItem(
        id=p.get("id", ""),
        uri=p.get("uri", ""),
        type="playlist",
        name=p.get("name", ""),
        subtitle=(p.get("owner", {}) or {}).get("display_name", ""),
        image=_first_image(p.get("images", [])),
    )
