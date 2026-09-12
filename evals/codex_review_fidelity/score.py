#!/usr/bin/env python3
"""Score a candidate review model against Codex's frozen findings.

Deterministic and offline: it reads the frozen corpus plus a candidate
observations file and reports how much of Codex's review a candidate reproduced.
No model is called here, so a score can always be recomputed from the artifacts.

Matching is by location, because that is the only part a scorer can decide
mechanically. A candidate finding counts against a Codex finding when it names
the same file and lands on the line the finding was anchored to -- either inside
the Codex finding's diff hunk, or within ``--tolerance`` lines of its anchor.
Whether a matched candidate describes the *same defect* is a separate judgment
that belongs in a human or reviewer-model record, not here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_TOLERANCE = 10


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(path: str) -> str:
    return str(path or "").lstrip("./")


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _validate(corpus: dict[str, Any], observations: dict[str, Any]) -> None:
    if corpus.get("version") != 1:
        raise ValueError("unsupported corpus version")
    if observations.get("corpus_version") != corpus["version"]:
        raise ValueError("observation corpus version does not match")
    known = {str(unit["pr"]) for unit in corpus["review_units"]}
    unknown = set(observations["review_units"]) - known
    if unknown:
        raise ValueError(f"observations reference unknown review units: {sorted(unknown)}")


def _candidate_lines(finding: dict[str, Any], tolerance: int) -> tuple[int, int] | None:
    """Line window a candidate finding is allowed to occupy to count as located."""
    line = finding.get("line")
    if not isinstance(line, int):
        return None
    return (line - tolerance, line + tolerance)


def _matches(candidate: dict[str, Any], codex: dict[str, Any], tolerance: int) -> bool:
    if _normalize(candidate["path"]) != _normalize(codex["path"]):
        return False
    window = _candidate_lines(candidate, tolerance)
    if window is None:
        return False
    low, high = window
    hunk = codex.get("hunk") or {}
    start, span = hunk.get("new_start"), hunk.get("new_lines")
    anchor = codex.get("line")
    if isinstance(start, int) and isinstance(span, int) and span > 0:
        if start <= low <= start + span or start <= high <= start + span:
            return True
    return isinstance(anchor, int) and low <= anchor <= high


def score(corpus_path: Path, observations_path: Path, *, tolerance: int = DEFAULT_TOLERANCE) -> dict[str, Any]:
    corpus = _load(corpus_path)
    observations = _load(observations_path)
    _validate(corpus, observations)

    total = matched = 0
    by_severity: dict[str, dict[str, int]] = {}
    confirmed_total = confirmed_matched = 0
    candidates_total = candidates_matched = 0
    per_unit: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    chunk_errors: list[str] = []

    for unit in corpus["review_units"]:
        key = str(unit["pr"])
        observed = observations["review_units"].get(key)
        if observed is None:
            per_unit.append({"pr": unit["pr"], "status": "not_run", "codex_findings": len(unit["codex_findings"])})
            continue
        chunk_errors.extend(f"PR {unit['pr']} {err}" for err in observed.get("chunk_errors") or [])
        candidates = observed.get("findings") or []
        unit_hits = 0
        for finding in unit["codex_findings"]:
            total += 1
            severity = finding["severity"]
            bucket = by_severity.setdefault(severity, {"total": 0, "matched": 0})
            bucket["total"] += 1
            if finding.get("confirmed_real"):
                confirmed_total += 1
            hit = any(_matches(c, finding, tolerance) for c in candidates)
            if hit:
                matched += 1
                unit_hits += 1
                bucket["matched"] += 1
                if finding.get("confirmed_real"):
                    confirmed_matched += 1
            else:
                missed.append({"pr": unit["pr"], "path": finding["path"], "line": finding["line"], "severity": severity,
                               "title": finding["title"], "confirmed_real": bool(finding.get("confirmed_real"))})
        for candidate in candidates:
            candidates_total += 1
            if any(_matches(candidate, finding, tolerance) for finding in unit["codex_findings"]):
                candidates_matched += 1
        per_unit.append(
            {
                "pr": unit["pr"],
                "status": "run",
                "codex_findings": len(unit["codex_findings"]),
                "matched": unit_hits,
                "candidate_findings": len(candidates),
                "chunks": observed.get("chunks"),
                "elapsed_seconds": observed.get("elapsed_seconds"),
                "locations_replaced_with_real_findings": unit_hits >= len(unit["codex_findings"]),
            }
        )

    ran = [u for u in per_unit if u["status"] == "run"]
    return {
        "provenance": {
            "model": observations.get("provenance", {}).get("model"),
            "endpoint": observations.get("provenance", {}).get("endpoint"),
            "candidate_tolerance_lines": tolerance,
            "review_units_in_corpus": len(corpus["review_units"]),
            "review_units_run": len(ran),
            "review_units_not_run": len(per_unit) - len(ran),
            "chunk_errors": len(chunk_errors),
        },
        "recall": {
            "codex_findings": total,
            "location_matched": matched,
            "location_match_rate": _ratio(matched, total),
            "p1": dict(by_severity.get("P1", {"total": 0, "matched": 0}),
                       rate=_ratio(by_severity.get("P1", {}).get("matched", 0), by_severity.get("P1", {}).get("total", 0))),
            "p2": dict(by_severity.get("P2", {"total": 0, "matched": 0}),
                       rate=_ratio(by_severity.get("P2", {}).get("matched", 0), by_severity.get("P2", {}).get("total", 0))),
            "confirmed_real": {
                "total": confirmed_total,
                "matched": confirmed_matched,
                "rate": _ratio(confirmed_matched, confirmed_total),
            },
        },
        "precision": {
            "candidate_findings": candidates_total,
            "located_against_a_codex_finding": candidates_matched,
            "candidate_location_precision": _ratio(candidates_matched, candidates_total),
        },
        "per_unit": per_unit,
        "missed_findings": missed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE)
    parser.add_argument("--show-missed", type=int, default=0, help="print up to N missed findings")
    args = parser.parse_args()

    metrics = score(args.corpus, args.observations, tolerance=args.tolerance)
    if args.show_missed:
        metrics["missed_findings"] = metrics["missed_findings"][: args.show_missed]
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
