#!/usr/bin/env python3
"""Automates spec generation from classified intake records."""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

SPEC_TEMPLATE = """# Spec: {name}

## Goal
{goal}

## Scope
### Allowed Files
{allowed_files}

### Forbidden Files
{forbidden_files}

## Implementation Plan
1. [AUTOMATED] Implementation logic based on intake goals.
2. Ensure file boundaries are respected.
3. Validate changes with identified commands.

## Acceptance Criteria
- [AUTOMATED] Derived from intake goals and tests.

## Validation
{validation_commands}
"""

def parse_intake(path: Path) -> dict:
    content = path.read_text()
    
    def extract_section(title: str) -> str:
        pattern = rf"## {title}\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else "None specified."

    def extract_list(title: str) -> str:
        section = extract_section(title)
        items = re.findall(r"- (.*)", section)
        return "\n".join(f"- {i}" for i in items) if items else "- None."

    # Extract name from filename or title
    name_match = re.search(r"# (?:Intake|Builder Intake Result): (.*)", content)
    name = name_match.group(1).strip() if name_match else path.stem.replace('-', ' ').title()

    return {
        "name": name,
        "goal": extract_section("Goal") or extract_section("Interpretation"),
        "allowed_files": extract_list("Allowed Files") or extract_list("Affected files"),
        "forbidden_files": extract_list("Forbidden Files"),
        "validation_commands": extract_list("Validation Commands"),
    }

def generate_spec(intake_path: Path, output_dir: Path, dry_run: bool = False):
    data = parse_intake(intake_path)
    
    # Enforce safety: ensure no allowed files are in forbidden list
    allowed = set(re.findall(r"- (.*)", data["allowed_files"]))
    forbidden = set(re.findall(r"- (.*)", data["forbidden_files"]))
    leak = allowed.intersection(forbidden)
    if leak:
        print(f"[ERROR] Security Leak: Files {leak} found in both Allowed and Forbidden lists.")
        sys.exit(1)

    spec_content = SPEC_TEMPLATE.format(**data)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    slug = intake_path.stem.replace('intake-', '')
    out_path = output_dir / f"{timestamp}-{slug}.spec.md"

    if dry_run:
        print(f"--- DRY RUN: Proposed Spec ({out_path}) ---")
        print(spec_content)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(spec_content)
        print(f"Successfully generated spec: {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Automate spec generation from intake.")
    parser.add_argument("--intake", required=True, type=Path, help="Path to classified intake MD.")
    parser.add_argument("--out-dir", type=Path, default=Path("specs"), help="Output directory for specs.")
    parser.add_argument("--dry-run", action="store_true", help="Print spec without writing.")
    args = parser.parse_args()

    if not args.intake.exists():
        print(f"Intake file not found: {args.intake}")
        sys.exit(1)

    generate_spec(args.intake, args.out_dir, args.dry_run)

if __name__ == "__main__":
    main()
