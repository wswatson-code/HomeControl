"""Dump the Core Service OpenAPI schema to api/openapi.json.

The exported schema is the contract the kiosk web app and Flutter app generate clients
from. Run after any change to the API models/routes:  python scripts/export_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from homecontrol.app import create_app

OUT = Path(__file__).resolve().parents[2] / "api" / "openapi.json"


def main() -> None:
    schema = create_app().openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
