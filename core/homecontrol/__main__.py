"""`python -m homecontrol` entrypoint."""

from __future__ import annotations

import uvicorn

from .config import settings


def main() -> None:
    uvicorn.run(
        "homecontrol.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
