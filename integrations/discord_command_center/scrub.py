from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence

_SECRET_NAME = re.compile(r"(?:TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
_TOKEN_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}\b"),
)
_SECRET_ASSIGNMENT = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL)[A-Za-z0-9_]*)"
    r"(\s*=\s*)([^\s'\";]+)",
    re.IGNORECASE,
)
_AUTHORIZATION_BEARER = re.compile(
    r"\b(Authorization:)\s*Bearer\s+[^\s,;]+",
    re.IGNORECASE,
)


class SecretScrubber:
    def __init__(self, secret_values: Sequence[str] = ()) -> None:
        self.secret_values = tuple(
            sorted({value for value in secret_values if len(value) >= 8}, key=len, reverse=True)
        )

    @classmethod
    def from_environment(cls, source: Mapping[str, str] | None = None) -> "SecretScrubber":
        source = source or os.environ
        values = [
            value
            for name, value in source.items()
            if value and _SECRET_NAME.search(name) and len(value) >= 8
        ]
        return cls(values)

    def scrub(self, text: str) -> str:
        scrubbed = text
        for value in self.secret_values:
            scrubbed = scrubbed.replace(value, "[REDACTED]")
        scrubbed = _SECRET_ASSIGNMENT.sub(
            lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", scrubbed
        )
        scrubbed = _AUTHORIZATION_BEARER.sub(r"\1 [REDACTED]", scrubbed)
        for pattern in _TOKEN_PATTERNS:
            scrubbed = pattern.sub("[REDACTED]", scrubbed)
        return scrubbed
