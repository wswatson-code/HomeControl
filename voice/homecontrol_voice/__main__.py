"""`python -m homecontrol_voice` — run the voice pipeline."""

from __future__ import annotations

import asyncio
import logging

from .config import VoiceConfig
from .pipeline import Pipeline


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = VoiceConfig()
    try:
        asyncio.run(Pipeline(cfg).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
