"""Pure security scanner for proposed builder output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SecurityFinding:
    path: str
    line: int
    rule: str
    severity: str
    message: str
    excerpt: str


@dataclass(frozen=True)
class SecurityReport:
    findings: tuple[SecurityFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def count(self) -> int:
        return len(self.findings)

    def by_severity(self, severity: str) -> tuple[SecurityFinding, ...]:
        wanted = severity.lower()
        return tuple(f for f in self.findings if f.severity.lower() == wanted)


SECRET_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    \b
    (?P<name>
        [A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)[A-Z0-9_]*
    )
    \s*[:=]\s*
    (?P<quote>["'])
    (?P<value>[^"']{8,})
    (?P=quote)
    """
)
GENERIC_SK_RE = re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{18,}\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

DANGEROUS_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "subprocess_shell_true",
        "high",
        "subprocess call enables shell=True",
        re.compile(r"\bsubprocess\.[a-zA-Z_]+\([^#\n]*shell\s*=\s*True"),
    ),
    ("os_system", "high", "os.system executes shell commands", re.compile(r"\bos\.system\s*\(")),
    ("eval", "high", "eval executes dynamic code", re.compile(r"(?<![\w.])eval\s*\(")),
    ("exec", "high", "exec executes dynamic code", re.compile(r"(?<![\w.])exec\s*\(")),
    ("rm_rf", "medium", "recursive force delete command", re.compile(r"\brm\s+-[A-Za-z]*r[A-Za-z]*f|\brm\s+-[A-Za-z]*f[A-Za-z]*r")),
    ("chmod_777", "medium", "world-writable chmod", re.compile(r"\bchmod\s+777\b")),
    ("path_traversal", "medium", "path traversal string", re.compile(r"(^|['\"/\\])\.\.(/|\\)")),
)


PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "example",
    "example-key",
    "placeholder",
    "test",
    "test-key",
    "your-key-here",
    "your_api_key_here",
}


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in PLACEHOLDER_VALUES:
        return True
    if "..." in stripped:
        return True
    if lowered.startswith(("your-", "your_", "replace-", "replace_")):
        return True
    return False


def _finding(path: str, line: int, rule: str, severity: str, message: str, excerpt: str) -> SecurityFinding:
    return SecurityFinding(
        path=path,
        line=line,
        rule=rule,
        severity=severity,
        message=message,
        excerpt=excerpt.strip()[:160],
    )


def scan_text(path: str, content: str) -> list[SecurityFinding]:
    """Scan one text blob and return structured findings."""
    findings: list[SecurityFinding] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        if PRIVATE_KEY_RE.search(line):
            findings.append(
                _finding(path, line_number, "private_key", "critical", "private key block detected", line)
            )

        for match in SECRET_ASSIGNMENT_RE.finditer(line):
            value = match.group("value")
            if not _is_placeholder(value):
                findings.append(
                    _finding(
                        path,
                        line_number,
                        "hardcoded_secret",
                        "critical",
                        f"hardcoded secret assigned to {match.group('name')}",
                        line,
                    )
                )

        for match in GENERIC_SK_RE.finditer(line):
            token = match.group(0)
            if not _is_placeholder(token):
                findings.append(
                    _finding(path, line_number, "api_key_literal", "critical", "API key-like literal detected", line)
                )

        for rule, severity, message, pattern in DANGEROUS_PATTERNS:
            if pattern.search(line):
                findings.append(_finding(path, line_number, rule, severity, message, line))
    return _dedupe(findings)


def scan_files(files: dict[str, str]) -> SecurityReport:
    """Scan path-to-content mappings without touching the filesystem."""
    findings: list[SecurityFinding] = []
    for path, content in files.items():
        findings.extend(scan_text(path, content))
    return SecurityReport(tuple(_dedupe(findings)))


def _dedupe(findings: Iterable[SecurityFinding]) -> list[SecurityFinding]:
    seen: set[tuple[str, int, str, str]] = set()
    unique: list[SecurityFinding] = []
    for finding in findings:
        key = (finding.path, finding.line, finding.rule, finding.excerpt)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique
