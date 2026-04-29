#!/usr/bin/env python3
"""Generate Kitty's read-only runtime context pack from canonical docs."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


SECTION_LIMIT = 3500


@dataclass(frozen=True)
class SourceChoice:
    label: str
    paths: tuple[str, ...]
    required: bool = False


SOURCES = (
    SourceChoice("Current Focus", ("CURRENT_FOCUS.md",), required=True),
    SourceChoice("Open Tasks", ("TASKS.md", "docs/TASKS.md")),
    SourceChoice("Session Summary", ("SESSION_SUMMARY.md", "docs/SESSION_LOG.md")),
    SourceChoice("Project Context", ("KITTY_CONTEXT.md", "docs/KITTY_CONTEXT.md")),
    SourceChoice("Recent Decisions", ("docs/DECISIONS.md",), required=True),
    SourceChoice("Parked Items Not To Build", ("docs/PARKED_FEATURES.md",), required=True),
    SourceChoice("Open Loops", ("docs/OPEN_LOOPS.md",)),
    SourceChoice("User Interaction Rules", ("src/space_kitty/SOUL.md", "docs/KITTY_CONTEXT.md")),
)


def read_first_existing(root: Path, choice: SourceChoice) -> tuple[str | None, str]:
    for relative in choice.paths:
        path = root / relative
        if path.exists() and path.is_file():
            return relative, path.read_text(encoding="utf-8", errors="replace")
    if choice.required:
        return None, f"[MISSING REQUIRED SOURCE: {choice.paths[0]}]"
    return None, "[missing optional source]"


def clip(text: str, limit: int = SECTION_LIMIT) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "\n\n[truncated]"


def extract_bullets(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    start = None
    heading_re = re.compile(rf"^#+\s+{re.escape(heading)}\s*$", re.IGNORECASE)
    for index, line in enumerate(lines):
        if heading_re.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return []
    bullets: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            break
        if stripped.startswith("- "):
            bullets.append(stripped)
    return bullets


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return "Review CURRENT_FOCUS.md and pick the next allowed task."


def build_context_pack(project: str | Path) -> str:
    root = Path(project).expanduser().resolve()
    sections: dict[str, tuple[str | None, str]] = {
        choice.label: read_first_existing(root, choice) for choice in SOURCES
    }
    current_focus = sections["Current Focus"][1]
    forbidden = extract_bullets(current_focus, "Forbidden Work")
    allowed = extract_bullets(current_focus, "Allowed Phase 1 work is limited to:")
    next_action = first_nonempty_line(sections["Open Tasks"][1])

    lines = [
        "# Kitty Runtime Context Pack",
        "",
        "Generated from canonical project docs. This file is read-only runtime context, not a source of authority.",
        "",
        "## Current Focus",
        f"Source: {sections['Current Focus'][0] or 'missing'}",
        "",
        clip(current_focus),
        "",
        "## Next Action",
        next_action,
        "",
        "## Allowed Work",
    ]
    lines.extend(allowed or ["- Follow CURRENT_FOCUS.md."])
    lines.extend(["", "## Forbidden Work"])
    lines.extend(forbidden or ["- Do not infer permission for unrelated work."])
    lines.extend(
        [
            "",
            "## Recent Decisions",
            f"Source: {sections['Recent Decisions'][0] or 'missing'}",
            "",
            clip(sections["Recent Decisions"][1]),
            "",
            "## Open Tasks",
            f"Source: {sections['Open Tasks'][0] or 'missing'}",
            "",
            clip(sections["Open Tasks"][1]),
            "",
            "## Parked Items Not To Build",
            f"Source: {sections['Parked Items Not To Build'][0] or 'missing'}",
            "",
            clip(sections["Parked Items Not To Build"][1]),
            "",
            "## Open Loops",
            f"Source: {sections['Open Loops'][0] or 'missing'}",
            "",
            clip(sections["Open Loops"][1]),
            "",
            "## Project Context",
            f"Source: {sections['Project Context'][0] or 'missing'}",
            "",
            clip(sections["Project Context"][1]),
            "",
            "## User Interaction Rules",
            f"Source: {sections['User Interaction Rules'][0] or 'missing'}",
            "",
            clip(sections["User Interaction Rules"][1]),
            "",
        ]
    )
    return "\n".join(lines)


def write_context_pack(project: str | Path, out: str | Path | None) -> Path:
    root = Path(project).expanduser().resolve()
    output = Path(out).expanduser() if out else root / ".cache" / "kitty_context_pack.md"
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_context_pack(root), encoding="utf-8")
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Kitty project root.")
    parser.add_argument(
        "--out",
        default=None,
        help="Output path. Defaults to PROJECT/.cache/kitty_context_pack.md.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print the generated context pack instead of writing it.",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print:
        print(build_context_pack(args.project))
        return 0
    output = write_context_pack(args.project, args.out)
    print(f"Wrote context pack: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
