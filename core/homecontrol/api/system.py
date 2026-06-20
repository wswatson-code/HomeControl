"""Device-local system actions, triggered from the on-device kiosk UI.

These act on the unit's own systemd state (not playback), so they're kept off the public
`/api` OpenAPI contract (`include_in_schema=False`): the mobile app codegens from that
contract and shouldn't see controls that only make sense on the physical kiosk.

The one privileged action — stopping the kiosk service — shells out to `sudo systemctl`,
permitted by a tightly-scoped sudoers grant (`provisioning/sudoers.d/homecontrol-kiosk`)
that allows exactly this single command and nothing else.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/system", tags=["system"], include_in_schema=False)

# Absolute path so it matches the sudoers rule exactly (sudo authorizes by resolved path).
_SYSTEMCTL = "/usr/bin/systemctl"
_KIOSK_UNIT = "homecontrol-kiosk.service"


async def _stop_kiosk() -> tuple[int, str]:
    """Run the privileged stop. Factored out so tests stub it without a real systemd."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", _SYSTEMCTL, "stop", _KIOSK_UNIT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return proc.returncode or 0, out.decode(errors="replace").strip()


@router.post("/kiosk/stop")
async def stop_kiosk() -> dict:
    """Stop the kiosk service — drops the screen to the desktop.

    Effectively fire-and-forget from the UI: stopping the unit kills Chromium, so the
    browser usually never renders this response. An explicit `systemctl stop` is sticky —
    `Restart=always` will NOT respawn it until the next `start`/boot.
    """
    code, output = await _stop_kiosk()
    if code != 0:
        raise HTTPException(status_code=500, detail=f"kiosk stop failed: {output}")
    return {"ok": True}
