#!/usr/bin/env python3
"""One-time Spotify OAuth pairing — mint a long-lived refresh token.

The Core Service controls playback and reads metadata through the Spotify Web API,
which needs a user refresh token. Run this once per Spotify account (not per unit):

    python pair.py --client-id <id> --client-secret <secret>

It opens the consent page, catches the redirect on http://localhost:8000/callback,
exchanges the code, and prints the refresh token to paste into the unit's env file.

Stdlib only — no install required. Your Spotify app must list
http://localhost:8000/callback as a redirect URI.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://127.0.0.1:8000/callback"
SCOPES = " ".join(
    [
        # playback control + status (Phase 2)
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        # browsing the user's library from the kiosk (Phase: browse). Catalog search needs
        # no scope; these cover the user's own playlists + saved albums.
        "playlist-read-private",
        "playlist-read-collaborative",
        "user-library-read",
    ]
)
_AUTH = "https://accounts.spotify.com/authorize"
_TOKEN = "https://accounts.spotify.com/api/token"  # noqa: S105 — public OAuth endpoint

_code: str | None = None


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — stdlib handler name
        global _code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        msg = "Pairing complete — return to the terminal." if _code else "No code received."
        self.wfile.write(msg.encode())

    def log_message(self, *args):  # silence the default request logging
        pass


def _exchange(client_id: str, client_secret: str, code: str) -> dict:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    ).encode()
    req = urllib.request.Request(
        _TOKEN, data=data, headers={"Authorization": f"Basic {basic}"}
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310 — fixed https endpoint
        return json.load(resp)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--client-secret", required=True)
    args = ap.parse_args()

    auth_url = f"{_AUTH}?" + urllib.parse.urlencode(
        {
            "client_id": args.client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        }
    )
    print("Opening browser for Spotify consent...\nIf it doesn't open, visit:\n", auth_url)
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", 8000), _Handler)
    server.handle_request()  # blocks until the single callback arrives

    if not _code:
        raise SystemExit("no authorization code received")

    tokens = _exchange(args.client_id, args.client_secret, _code)
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise SystemExit(f"no refresh token in response: {tokens}")

    print("\n=== SUCCESS ===")
    print("Paste this into /etc/homecontrol/unit.env:\n")
    print(f"HOMECONTROL_SPOTIFY_REFRESH_TOKEN={refresh}")


if __name__ == "__main__":
    main()
