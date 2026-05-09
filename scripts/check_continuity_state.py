#!/usr/bin/env python3
"""Continuity linter for Kitty control docs.

Checks:
- required control docs exist
- each has a parseable "Last updated: YYYY-MM-DD"
- dates are not in the future
- control docs are not stale beyond a configurable max age
- no escaped-newline corruption markers in top-level control docs
- canonical path statements remain aligned to /Users/jacobbrizinski/Projects/kitty
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ContinuityReport:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


REQUIRED_DOCS = (
    "CURRENT_FOCUS.md",
    "TASKS.md",
    "SESSION_SUMMARY.md",
    "docs/LAYER0_CONTROL_PLANE.md",
    "docs/README.md",
)

_LAST_UPDATED_RE = re.compile(r"^Last updated:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
_CANONICAL_PATH = "/Users/jacobbrizinski/Projects/kitty"
_STALE_PATH = "/Users/jacobbrizinski/Projects/kitty-system/kitty-app"


def parse_last_updated(text: str) -> date | None:
    m = _LAST_UPDATED_RE.search(text)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _head(text: str, max_lines: int = 220) -> str:
    lines = text.splitlines()
    return "\n".join(lines[:max_lines])


def build_report(
    root: str | Path,
    *,
    today: date | None = None,
    max_age_days: int = 14,
) -> ContinuityReport:
    root_path = Path(root).expanduser().resolve()
    now = today or datetime.now(timezone.utc).date()

    errors: list[str] = []
    warnings: list[str] = []

    doc_contents: dict[str, str] = {}

    for rel in REQUIRED_DOCS:
        path = root_path / rel
        if not path.exists():
            errors.append(f"Missing required control doc: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        doc_contents[rel] = text

        updated = parse_last_updated(text)
        if updated is None:
            errors.append(f"{rel}: missing or invalid 'Last updated: YYYY-MM-DD'")
            continue
        if updated > now:
            errors.append(f"{rel}: Last updated {updated} is in the future")
            continue
        age = (now - updated).days
        if age > max_age_days:
            warnings.append(f"{rel}: Last updated is stale ({age} days old)")

    # Corruption marker check for TASKS.md duplicate escaped-block regression.
    for rel in ("TASKS.md",):
        text = doc_contents.get(rel, "")
        if re.search(r"---\\n\\n##\s", text):
            errors.append(f"{rel}: found escaped newline duplicate-block marker (possible corruption)")

    # Canonical path checks in high-authority docs.
    for rel in ("docs/LAYER0_CONTROL_PLANE.md", "docs/README.md"):
        text = doc_contents.get(rel, "")
        if not text:
            continue
        if _CANONICAL_PATH not in text:
            errors.append(f"{rel}: canonical path {_CANONICAL_PATH} not found")

    # Stale-path active-claim guard: high-authority docs only.
    negative_tokens = ("stale", "retired", "historical", "removed", "reconciled", "closed", "not runnable")
    active_tokens = ("active", "canonical", "runnable", "authoritative")
    for rel in ("CURRENT_FOCUS.md", "docs/LAYER0_CONTROL_PLANE.md", "docs/README.md"):
        text = doc_contents.get(rel, "")
        if not text:
            continue
        head = _head(text)
        for raw in head.splitlines():
            line = raw.strip()
            if _STALE_PATH not in line:
                continue
            low = line.lower()
            if any(token in low for token in negative_tokens):
                continue
            if any(token in low for token in active_tokens):
                errors.append(f"{rel}: stale runtime path appears in active/canonical context")
            else:
                warnings.append(f"{rel}: stale runtime path mentioned (verify this is historical)")

    return ContinuityReport(errors=errors, warnings=warnings)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuity linter for Kitty control docs.")
    parser.add_argument("--project", default=".", help="Project root (defaults to cwd).")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=14,
        help="Warn when Last updated is older than this many days (default: 14).",
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Treat warnings as failures.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.project, max_age_days=args.max_age_days)

    print("Continuity linter")
    if report.errors:
        print("Errors:")
        for item in report.errors:
            print(f"  - {item}")
    else:
        print("Errors: none")

    if report.warnings:
        print("Warnings:")
        for item in report.warnings:
            print(f"  - {item}")
    else:
        print("Warnings: none")

    if report.errors:
        return 1
    if args.strict_warnings and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
