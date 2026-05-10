from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def append_evidence(path: str | Path, **fields: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now().isoformat(timespec="seconds"), **fields}
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")

