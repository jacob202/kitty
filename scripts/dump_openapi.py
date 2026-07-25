#!/usr/bin/env python3.12
"""Dump the gateway's OpenAPI schema to a file without booting a server.

The README's original loop curled a live gateway on :8000. That can't run in
CI and silently generates stale types if the running server is an old build.
Importing the app is deterministic and offline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "gateway/kitty-chat/src/lib/gen/openapi.json"


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from gateway.app import app

    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"{out}: {len(schema.get('paths', {}))} paths, "
          f"{len(schema.get('components', {}).get('schemas', {}))} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
