"""Contracts for deterministic eval scoring."""
from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class EvalResult(BaseModel):
    name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    detail: str = ""


class EvalReport(BaseModel):
    results: list[EvalResult]

    @computed_field
    @property
    def total(self) -> int:
        return len(self.results)

    @computed_field
    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @computed_field
    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(result.score for result in self.results) / len(self.results), 2)
