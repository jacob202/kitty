#!/usr/bin/env python3
"""Deterministic intake classifier for controlled Kitty builder work."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


CLASS_DESTINATIONS = {
    "ready": "ready_specs",
    "needs_verification": "clarifications",
    "park": "parked",
    "split": "clarifications",
    "reject": "logs",
}

DEFAULT_PROTECTED_FILES = {
    "src/",
    "tests/",
    "scripts/",
    "data/",
    "garage-ui/",
    "src/static/",
    "src/templates/",
    "web.py",
    "src/services/context_service.py",
    "src/core/specialists/registry.py",
    "src/core/orchestrator.py",
    "src/space_kitty/SOUL.md",
    "KITTY_CONTEXT.md",
    "CURRENT_FOCUS.md",
    "data/kitty.db",
}

PARKED_TERMS = {
    "qlora",
    "mcp",
    "wake word",
    "wake-word",
    "idle nudger",
    "nudging",
    "proactive",
    "screen understanding",
    "kelly bodywork",
    "fascial",
    "tensegrity",
    "budget dashboard",
    "model digest",
}

VAGUE_TERMS = {
    "clean up",
    "cleanup",
    "make it better",
    "fix everything",
    "optimize everything",
    "improve the repo",
    "organize everything",
}

FEATURE_TERMS = {
    "/stuck",
    "stuck command",
    "memory",
    "ui",
    "mcp",
    "qlora",
    "brief",
    "task",
    "done handler",
    "specialist",
    "voice",
}


@dataclass
class IntakeResult:
    raw_request: str
    interpretation: str
    classification: str
    current_phase: str
    missing_context: str
    recommended_action: str
    affected_files: list[str]
    forbidden_files: list[str]
    decision_updates_needed: list[str]
    parking_lot_updates_needed: list[str]
    next_smallest_action: str
    output_path: Path | None = None

    @property
    def destination(self) -> str:
        return CLASS_DESTINATIONS[self.classification]

    def to_dict(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            "destination": self.destination,
            "text": self.raw_request,
            "current_phase": self.current_phase,
            "missing_context": self.missing_context,
            "recommended_action": self.recommended_action,
            "affected_files": self.affected_files,
            "forbidden_files": self.forbidden_files,
            "next_smallest_action": self.next_smallest_action,
        }

    def to_markdown(self) -> str:
        allowed_files = self.affected_files if self.classification == "ready" else []
        return "\n".join(
            [
                "# Builder Intake Result",
                "## Raw user request",
                self.raw_request,
                "## Interpretation",
                self.interpretation,
                "## Classification",
                self.classification,
                "## Current phase check",
                f"Current phase: {self.current_phase}",
                "## Missing context",
                self.missing_context or "None.",
                "## Recommended action",
                self.recommended_action,
                "## Affected files",
                _bullet_list(self.affected_files),
                "## Allowed files",
                _bullet_list(allowed_files),
                "## Forbidden files",
                _bullet_list(self.forbidden_files),
                "## Acceptance tests",
                "- Define before builder execution.",
                "## Smoke test",
                "Command:",
                "- Define before builder execution.",
                "Expected:",
                "- Define before builder execution.",
                "## Validation commands",
                "- Define exact commands before builder execution.",
                "## Rollback plan",
                "- Revert only files changed by the accepted spec.",
                "## Decision updates needed",
                _bullet_list(self.decision_updates_needed),
                "## Parking lot updates needed",
                _bullet_list(self.parking_lot_updates_needed),
                "## Next smallest action",
                self.next_smallest_action,
                "## Completion report required",
                "- files read",
                "- files changed",
                "- commands run",
                "- tests passed/failed",
                "- gates passed/failed",
                "- docs updated",
                "- known risks",
                "- next smallest action",
                "",
            ]
        )


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None."
    return "\n".join(f"- {item}" for item in items)


def read_focus(project: Path) -> str:
    path = project / "CURRENT_FOCUS.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def current_phase_from_focus(focus: str) -> str:
    match = re.search(r"Active phase:\s*\n?(.+)", focus, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"Phase\s+\d+[^\n]*", focus, flags=re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return "Unknown."


def forbidden_work_from_focus(focus: str) -> list[str]:
    if not focus:
        return []
    sections = []
    for heading in ("Forbidden work", "Stop Conditions"):
        match = re.search(
            rf"{heading}.*?(?:\n\n|\n(?=#)|\Z)(.*?)(?:\n## |\Z)",
            focus,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            sections.append(match.group(0))
    if not sections:
        return []
    items: list[str] = []
    for section in sections:
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped.startswith("-"):
                continue
            item = stripped.strip("- ").strip().strip("`").lower()
            if item:
                items.append(item)
    return items


def protected_files(project: Path) -> set[str]:
    protected = set(DEFAULT_PROTECTED_FILES)
    path = project / "docs" / "FILE_GOVERNANCE.md"
    if not path.exists():
        return protected
    text = path.read_text(encoding="utf-8", errors="replace")
    protected.update(re.findall(r"`([^`]+)`", text))
    return {_normalize_protected_path(item) for item in protected if item.strip()}


def _normalize_protected_path(path: str) -> str:
    path = path.strip().strip("`")
    if path in {"src", "tests", "scripts", "data", "garage-ui"}:
        return f"{path}/"
    return path


def mentioned_protected_files(project: Path, text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for rel in sorted(protected_files(project)):
        protected = rel.lower()
        if protected.endswith("/"):
            bare = protected.rstrip("/")
            if re.search(rf"(?<![\w./-]){re.escape(bare)}/", lowered):
                hits.append(rel)
            elif re.search(rf"\b(edit|modify|touch|change|refactor|delete|move)\s+{re.escape(bare)}\b", lowered):
                hits.append(rel)
        elif protected in lowered:
            hits.append(rel)
    return hits


def affected_files_for(text: str) -> list[str]:
    lowered = text.lower()
    files: list[str] = []
    if "stuck" in lowered:
        files.extend(["src/api/commands.py", "src/core/stuck.py", "tests/test_stuck_command.py"])
    if "brief" in lowered:
        files.extend(["src/core/morning_brief.py", "src/api/brief.py", "tests/test_morning_brief.py"])
    if "intake" in lowered:
        files.extend(["scripts/builder_intake.py", "kittyintake", "tests/test_builder_intake.py"])
    if "memory" in lowered:
        files.extend(["src/memory/", "data/kitty.db"])
    if _term_present(lowered, "ui") and not re.search(r"do not (modify|touch|change|edit) ui", lowered):
        files.append("UI files")
    return list(dict.fromkeys(files))


def _term_present(lowered_text: str, term: str) -> bool:
    if term.startswith("/"):
        return term in lowered_text
    return re.search(rf"\b{re.escape(term)}\b", lowered_text) is not None


def looks_multi_feature(text: str) -> bool:
    lowered = text.lower()
    normalized = re.sub(r"do not (modify|touch|change|edit) ui", "", lowered)
    hits = [term for term in FEATURE_TERMS if _term_present(normalized, term)]
    return len(set(hits)) >= 3 or (
        bool(re.search(r"\b(and|plus|also)\b", lowered)) and len(set(hits)) >= 2
    )


def classify_request(project: str | Path, text: str) -> IntakeResult:
    project_path = Path(project).expanduser().resolve()
    raw = text.strip()
    lowered = raw.lower()
    focus = read_focus(project_path)
    phase = current_phase_from_focus(focus)
    protected_hits = mentioned_protected_files(project_path, raw)
    focus_hits = mentioned_focus_stop_conditions(focus, raw)
    protected_hits = list(dict.fromkeys([*protected_hits, *focus_hits]))
    affected = affected_files_for(raw)

    classification = "ready"
    missing_context = ""
    recommended = "Create one bounded spec, then run kittybuilder only after review."
    parking_updates: list[str] = []
    decision_updates: list[str] = []

    if protected_hits:
        classification = "reject"
        recommended = "Reject this request because it targets protected files without an explicit approved spec."
    elif any(item and item in lowered for item in forbidden_work_from_focus(focus)):
        classification = "park"
        recommended = "Park this request because it conflicts with current focus forbidden work."
        parking_updates.append(raw)
    elif looks_multi_feature(raw):
        classification = "split"
        missing_context = "Request contains multiple feature slices. Each needs one spec."
        recommended = "Split into one spec per feature before any builder execution."
    elif any(term in lowered for term in PARKED_TERMS):
        classification = "park"
        recommended = "Add this to PARKED_FEATURES.md with enough context to revive later."
        parking_updates.append(raw)
    elif any(term in lowered for term in VAGUE_TERMS):
        classification = "needs_verification"
        missing_context = "Needs a specific target, allowed files, forbidden files, and validation command."
        recommended = "Ask for or derive the next smallest concrete spec before writing code."

    if not raw:
        classification = "needs_verification"
        missing_context = "No request text supplied."
        recommended = "Provide a concrete request before intake can classify it."
    elif classification == "ready" and "stuck" in lowered:
        recommended = "Create one bounded /stuck spec, then run kittybuilder only after review."

    next_action = {
        "ready": "Draft a spec in specs/ and run validation before builder execution.",
        "needs_verification": "Clarify the missing target and validation command.",
        "park": "Write a rich parked-feature entry and do not build it now.",
        "split": "Split into separate intake records or specs.",
        "reject": "Do not proceed without an explicit governance decision.",
    }[classification]

    return IntakeResult(
        raw_request=raw,
        interpretation="Bounded build request." if classification == "ready" else "Request needs control routing.",
        classification=classification,
        current_phase=phase,
        missing_context=missing_context,
        recommended_action=recommended,
        affected_files=affected,
        forbidden_files=protected_hits,
        decision_updates_needed=decision_updates,
        parking_lot_updates_needed=parking_updates,
        next_smallest_action=next_action,
    )


def mentioned_focus_stop_conditions(focus: str, text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for item in forbidden_work_from_focus(focus):
        normalized = _normalize_protected_path(item)
        candidate = normalized.lower()
        if candidate.endswith("/"):
            bare = candidate.rstrip("/")
            if f"{bare}/" in lowered:
                hits.append(normalized)
        elif (
            "/" in candidate
            or "." in candidate
            or candidate in {"ui files", "ui"}
        ) and candidate in lowered:
            hits.append(normalized)
    return hits


def classify(project: str | Path, text: str) -> dict[str, object]:
    return classify_request(project, text).to_dict()


def output_dir_for(project: Path, classification: str) -> Path:
    return project / "intake" / CLASS_DESTINATIONS[classification]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "intake"


def run_intake(project: str | Path, text: str, write: bool = False) -> IntakeResult:
    project_path = Path(project).expanduser().resolve()
    if not project_path.exists() or not project_path.is_dir():
        raise SystemExit(f"Project path does not exist or is not a directory: {project_path}")
    result = classify_request(project_path, text)
    out_dir = output_dir_for(project_path, result.classification)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proposed = out_dir / f"{stamp}-{slugify(text)}.md"

    print(f"Classification: {result.classification}")
    print(f"Recommended action: {result.recommended_action}")
    print(f"Next smallest action: {result.next_smallest_action}")
    print(f"Proposed output path: {proposed}")

    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        proposed.write_text(result.to_markdown(), encoding="utf-8")
        result.output_path = proposed
        print(f"Wrote: {proposed}")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify raw Kitty builder requests.")
    parser.add_argument("--project", required=True, type=Path, help="Path to the Kitty app checkout.")
    parser.add_argument("--text", required=True, help="Raw request text to classify.")
    parser.add_argument("--write", action="store_true", help="Write the intake result to the project intake folder.")
    parser.add_argument("--dry-run", action="store_true", help="Print only. This is the default.")
    return parser


def run(argv: Iterable[str] | None = None) -> dict[str, object]:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.write and args.dry_run:
        parser.error("--write and --dry-run cannot be combined")
    result = run_intake(args.project, args.text, write=args.write)
    data = result.to_dict()
    data["mode"] = "write" if args.write else "dry-run"
    if result.output_path:
        data["written"] = str(result.output_path)
    return data


def main(argv: Iterable[str] | None = None) -> int:
    run(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
