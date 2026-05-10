"""Eval domain model — serializable types for Kitty's eval platform."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalCheck:
    name: str
    passed: bool
    reason: str = ""

    @classmethod
    def record(cls, name: str, passed: bool, reason: str = "") -> "EvalCheck":
        return cls(name=name, passed=passed, reason=reason)


@dataclass
class EvalScore:
    passed: int
    total: int

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    def meets_baseline(self, threshold: float) -> bool:
        return self.rate >= threshold


@dataclass
class EvalRun:
    run_id: str
    suite: str
    started_at: float

    @classmethod
    def start(cls, suite: str) -> "EvalRun":
        return cls(
            run_id=uuid.uuid4().hex[:8],
            suite=suite,
            started_at=time.time(),
        )


@dataclass
class EvalResult:
    run: EvalRun
    checks: list[EvalCheck]
    scores: dict[str, EvalScore]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run.run_id,
            "suite": self.run.suite,
            "started_at": self.run.started_at,
            "scores": {
                k: {"passed": v.passed, "total": v.total, "rate": v.rate}
                for k, v in self.scores.items()
            },
            "checks": [
                {"name": c.name, "passed": c.passed, "reason": c.reason}
                for c in self.checks
            ],
        }
