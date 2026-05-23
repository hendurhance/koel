#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

from koel.api.main import app

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {out} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
