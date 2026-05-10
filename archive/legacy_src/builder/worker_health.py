from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerHealth:
    name: str
    available: bool
    path: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "available": self.available,
            "path": self.path,
            "reason": self.reason,
        }


def check_worker_health(name: str) -> WorkerHealth:
    path = shutil.which(name)
    if not path:
        return WorkerHealth(name=name, available=False, reason="binary missing")
    return WorkerHealth(name=name, available=True, path=path, reason="binary found")

