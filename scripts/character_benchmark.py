#!/usr/bin/env python3
"""CLI: run the face-locked character benchmark and print the automated verdict.

    python scripts/character_benchmark.py --character james --engine runware

Never opens or displays generated images — they stay quarantined on disk.
Prints only the execution/report summary. A PASS_AUTOMATED result is never
final; it always requires human review of the quarantined files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.imagen.benchmark import run_character_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", required=True, help="Character name, e.g. james")
    parser.add_argument("--engine", default="runware", help="Engine slug (default: runware)")
    parser.add_argument("--seed-base", type=int, default=1000, help="First scene's seed")
    args = parser.parse_args()

    report = run_character_benchmark(
        args.character, engine_name=args.engine, seed_base=args.seed_base
    )

    print(f"character:        {report.character}")
    print(f"engine:           {report.engine}")
    print(f"locked ref sha256: {report.locked_reference_sha256 or '(unresolved)'}")
    print(f"run id:           {report.run_id}")
    print(f"quarantine dir:   {report.quarantine_dir}")
    print()
    for s in report.scenes:
        face = f"{s.face_similarity:.3f}" if s.face_similarity is not None else "-"
        err = f"  ({s.error})" if s.error else ""
        print(f"  [{s.result:14}] {s.scene:24} seed={s.seed:<8} face={face}{err}")
    print()
    print(f"automated_verdict:    {report.automated_verdict}")
    print(f"final_review_required: {report.final_review_required}")

    return 0 if report.automated_verdict != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
