"""Context receipt facade with a bounded Global Agent Room migration mode.

The historical checkpoint implementation remains in ``context_receipt_legacy``
while callers migrate from tracked ``.claude`` checkpoint continuity to the
Global Agent Room. Strict callers (doctor, CI, legacy session validation) keep
the exact previous behavior by default. Agent cold starts that have already
proven ``workspace_global`` available may opt out of legacy checkpoint authority
with ``--skip-legacy-continuity``.

This compatibility seam is temporary and is intentionally small so the legacy
implementation can be archived cleanly once scoped Agent Room retrieval is the
sole interactive-continuity path.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from gateway import context_receipt_legacy as _legacy

# Public compatibility exports used by doctor, Builder MCP, tests, and scripts.
ContextReceiptError = _legacy.ContextReceiptError
ContinuityCheck = _legacy.ContinuityCheck
GitHubLookup = _legacy.GitHubLookup
SCHEMA_VERSION = _legacy.SCHEMA_VERSION
DEFAULT_RECENT_COMMITS = _legacy.DEFAULT_RECENT_COMMITS
DEFAULT_MAX_CHECKPOINT_AGE = _legacy.DEFAULT_MAX_CHECKPOINT_AGE
EXPECTED_CANONICAL_CHECKOUT = _legacy.EXPECTED_CANONICAL_CHECKOUT
ROOT = _legacy.ROOT
STATE_PATH = _legacy.STATE_PATH
HANDOFF_PATH = _legacy.HANDOFF_PATH
ACTIVE_MISSION_PATH = _legacy.ACTIVE_MISSION_PATH

compact_context_receipt = _legacy.compact_context_receipt
run_continuity_checks = _legacy.run_continuity_checks

_LEGACY_CHECK_PREFIXES = ("state:", "handoff:", "checkpoint:")
_LEGACY_DERIVED_CHECKS = {"mission:active_state"}


def _is_legacy_continuity_check(check: ContinuityCheck) -> bool:
    """Return whether a check depends on STATE/HANDOFF compatibility data."""
    return check.name.startswith(_LEGACY_CHECK_PREFIXES) or check.name in _LEGACY_DERIVED_CHECKS


def _without_legacy_continuity(inspection: dict[str, Any]) -> dict[str, Any]:
    """Project strict continuity evidence without legacy checkpoint authority.

    The legacy inspector still runs during this transition so strict tooling is
    not forked into a second implementation. Its checkpoint-derived failures and
    fields are removed from the GAR-first projection, making them non-blocking
    once the caller has independently established Agent Room availability.
    """
    projected = dict(inspection)
    projected["checks"] = [
        check for check in inspection["checks"] if not _is_legacy_continuity_check(check)
    ]
    projected["state"] = None
    projected["handoff"] = None
    return projected


def inspect_continuity(
    repo_root: Path,
    *,
    expected_canonical: Path | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_MAX_CHECKPOINT_AGE,
    github_lookup: GitHubLookup | None = None,
    include_legacy_continuity: bool = True,
) -> dict[str, Any]:
    """Inspect repository continuity, optionally demoting legacy checkpoints.

    ``include_legacy_continuity=True`` is the compatibility default and delegates
    unchanged to the historical implementation. ``False`` is only for a caller
    that has already proven ``workspace_global`` available; checkpoint-derived
    state and failures then become non-authoritative and non-blocking.
    """
    inspection = _legacy.inspect_continuity(
        repo_root,
        expected_canonical=expected_canonical,
        now=now,
        max_age=max_age,
        github_lookup=github_lookup,
    )
    if include_legacy_continuity:
        return inspection
    return _without_legacy_continuity(inspection)


def _legacy_unknown(field: str) -> bool:
    return (
        field in {"continuity.state", "continuity.handoff"}
        or field.startswith("continuity.state:")
        or field.startswith("continuity.handoff:")
        or field.startswith("continuity.checkpoint:")
        or field == "continuity.mission:active_state"
    )


def _project_receipt_without_legacy(receipt: dict[str, Any]) -> dict[str, Any]:
    """Remove checkpoint authority and recompute receipt truth from remaining checks."""
    projected = dict(receipt)
    continuity = dict(receipt["continuity"])
    checks = [
        check
        for check in continuity["checks"]
        if not (
            str(check["name"]).startswith(_LEGACY_CHECK_PREFIXES)
            or str(check["name"]) in _LEGACY_DERIVED_CHECKS
        )
    ]
    failures = [check for check in checks if check["level"] == "FAIL"]
    warnings = [check for check in checks if check["level"] == "WARN"]
    continuity.update(
        {
            "summary": {
                "pass": sum(check["level"] == "PASS" for check in checks),
                "warn": len(warnings),
                "fail": len(failures),
            },
            "checks": checks,
            "state": None,
            "handoff": None,
        }
    )
    projected["continuity"] = continuity
    projected["ok"] = not failures
    projected["blockers"] = None
    projected["next_action"] = None
    projected["recommendations"] = None
    evidence = dict(receipt["evidence"])
    evidence["checkpoint_source"] = []
    projected["evidence"] = evidence
    projected["unknowns"] = [
        item for item in receipt["unknowns"] if not _legacy_unknown(str(item.get("field", "")))
    ]
    return projected


def build_context_receipt(
    repo_root: Path,
    *,
    expected_canonical: Path | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_MAX_CHECKPOINT_AGE,
    github_lookup: GitHubLookup | None = None,
    recent_commit_limit: int = DEFAULT_RECENT_COMMITS,
    include_builder: bool = True,
    include_legacy_continuity: bool = True,
) -> dict[str, Any]:
    """Build a receipt; GAR-first callers can make legacy continuity non-blocking."""
    receipt = _legacy.build_context_receipt(
        repo_root,
        expected_canonical=expected_canonical,
        now=now,
        max_age=max_age,
        github_lookup=github_lookup,
        recent_commit_limit=recent_commit_limit,
        include_builder=include_builder,
    )
    if include_legacy_continuity:
        return receipt
    return _project_receipt_without_legacy(receipt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="derive a deterministic Kitty context receipt")
    parser.add_argument(
        "--agent",
        action="store_true",
        required=True,
        help="emit deterministic JSON for an agent cold start",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="omit bulky checkpoint, worktree, and initiative detail",
    )
    parser.add_argument(
        "--skip-builder",
        action="store_true",
        help="do not inspect the Builder database for informational work",
    )
    parser.add_argument(
        "--skip-legacy-continuity",
        action="store_true",
        help=(
            "make .claude STATE/HANDOFF checks non-blocking after Global Agent Room "
            "availability has been independently established"
        ),
    )
    args = parser.parse_args(argv)
    if not args.agent:
        parser.error("--agent is required")
    try:
        receipt = build_context_receipt(
            ROOT,
            include_builder=not args.skip_builder,
            include_legacy_continuity=not args.skip_legacy_continuity,
        )
    except ContextReceiptError as exc:
        print(f"context receipt failed: {exc}", file=sys.stderr)
        return 1
    output = compact_context_receipt(receipt) if args.compact else receipt
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
