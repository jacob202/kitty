#!/usr/bin/env python3
"""
Chat log consolidation pipeline - dry-run extraction.
Extracts structured data from raw chat exports without deleting anything.
"""
import argparse
import os, re, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

def _scan_logs(input_dir: str) -> List[Path]:
    """Scan for .json or .md chat logs."""
    p = Path(input_dir)
    if not p.exists():
        return []
    return sorted(list(p.rglob("*.json")) + list(p.rglob("*.md")))

def _extract_categories(content: str) -> Dict[str, List[str]]:
    """Extract categories from chat content."""
    cats = {
        "decisions": [],
        "parked_features": [],
        "active_tasks": [],
        "rejected_ideas": [],
        "corrections": [],
        "user_preferences": [],
        "project_facts": [],
        "file_references": [],
        "cleanup_candidates": [],
        "specialist_kb_candidates": [],
        "skill_candidates": [],
        "bugs_failures": [],
        "open_loops": [],
    }
    lines = content.splitlines()
    for line in lines:
        low = line.lower()
        if "decision" in low or "decided" in low:
            cats["decisions"].append(line.strip())
        if "park" in low or "later" in low:
            cats["parked_features"].append(line.strip())
        if "todo" in low or "task" in low:
            cats["active_tasks"].append(line.strip())
        if "reject" in low or "won't" in low or "wont" in low:
            cats["rejected_ideas"].append(line.strip())
        if "correction" in low or "fix" in low:
            cats["corrections"].append(line.strip())
        if "prefer" in low or "like" in low:
            cats["user_preferences"].append(line.strip())
        if "fact" in low or "note" in low:
            cats["project_facts"].append(line.strip())
        if "file" in low or ".py" in low or ".md" in low:
            cats["file_references"].append(line.strip())
        if "cleanup" in low or "junk" in low or "delete" in low:
            cats["cleanup_candidates"].append(line.strip())
        if "specialist" in low or "kb" in low:
            cats["specialist_kb_candidates"].append(line.strip())
        if "skill" in low:
            cats["skill_candidates"].append(line.strip())
        if "bug" in low or "fail" in low or "error" in low:
            cats["bugs_failures"].append(line.strip())
        if "open loop" in low or "todo" in low or "pending" in low:
            cats["open_loops"].append(line.strip())
    return cats

def dry_run(input_dir: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Dry-run extraction — does not write or delete.
    Returns dict with counts and sample extractions.
    """
    logs = _scan_logs(input_dir)
    result = {
        "logs_found": len(logs),
        "logs_processed": 0,
        "categories": {},
        "samples": {},
        "errors": [],
    }
    all_cats = {}
    for log_path in logs:
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
            cats = _extract_categories(content)
            for k, v in cats.items():
                if k not in all_cats:
                    all_cats[k] = []
                all_cats[k].extend(v)
            result["logs_processed"] += 1
        except Exception as e:
            result["errors"].append(f"{log_path.name}: {e}")
    result["categories"] = {k: len(v) for k, v in all_cats.items()}
    # Samples (first 3 of each)
    for k, v in all_cats.items():
        result["samples"][k] = v[:3] if v else []
    return result

def write_reviewed(result: Dict, output_path: str):
    """Write consolidation report (only after review)."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Chat Log Consolidation Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Logs processed: {result['logs_processed']}\n\n")
        for cat, count in result["categories"].items():
            f.write(f"## {cat}: {count} items\n")
            for sample in result["samples"].get(cat, []):
                f.write(f"- {sample}\n")
            f.write("\n")
        if result["errors"]:
            f.write("## Errors\n")
            for err in result["errors"]:
                f.write(f"- {err}\n")
    return str(p)

def _resolve_project_path(project: str, value: str) -> Path:
    """Resolve CLI paths relative to --project unless already absolute."""
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(project).resolve() / path

def _print_summary(result: Dict[str, Any], mode: str, input_dir: Path):
    """Print a stable summary for humans and smoke tests."""
    print(f"Chat log consolidation {mode}")
    print(f"Input: {input_dir}")
    print(f"Logs found: {result['logs_found']}")
    print(f"Logs processed: {result['logs_processed']}")
    print(f"Errors: {len(result['errors'])}")
    print("Category counts:")
    for category in sorted(result["categories"]):
        print(f"- {category}: {result['categories'][category]}")
    if result["errors"]:
        print("Error samples:")
        for error in result["errors"][:5]:
            print(f"- {error}")

def run(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract review candidates from Kitty chat logs without deleting raw logs."
    )
    parser.add_argument("--project", default=".", help="Kitty project root; relative paths resolve from here.")
    parser.add_argument("--input", required=True, help="Raw chat log directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print extraction summary without writing.")
    parser.add_argument("--write-reviewed", action="store_true", help="Write a reviewed consolidation report.")
    parser.add_argument("--output", help="Report output path. Required with --write-reviewed.")
    args = parser.parse_args(argv)

    if args.dry_run and args.write_reviewed:
        parser.error("--dry-run and --write-reviewed cannot be used together")
    if args.write_reviewed and not args.output:
        parser.error("--output is required with --write-reviewed")

    project = Path(args.project).resolve()
    input_dir = _resolve_project_path(str(project), args.input)
    result = dry_run(str(input_dir))

    if args.write_reviewed:
        output_path = _resolve_project_path(str(project), args.output)
        written = write_reviewed(result, str(output_path))
        _print_summary(result, "write-reviewed", input_dir)
        print(f"Wrote report: {written}")
        return 0

    _print_summary(result, "dry-run", input_dir)
    print("Wrote report: no")
    return 0

def main():
    raise SystemExit(run())

if __name__ == "__main__":
    main()
