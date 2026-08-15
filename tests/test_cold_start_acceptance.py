"""Cold-model acceptance using only repository authorities and a context receipt."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gateway.context_receipt import build_context_receipt

ROOT = Path(__file__).resolve().parents[1]


def _canonical_worktree() -> Path:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    first = next(
        line.removeprefix("worktree ")
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    )
    return Path(first).resolve()


def _section_body(document: str, heading: str) -> str:
    """Prose under ``heading``, stopping at the next heading of any level."""
    _, separator, rest = document.partition(f"{heading}\n")
    if not separator:
        return ""
    body: list[str] = []
    for line in rest.splitlines():
        if line.startswith("#"):
            break
        body.append(line)
    return "\n".join(body).strip()


def test_clean_reader_can_resolve_all_cold_start_questions() -> None:
    """No chat or inherited model memory is used by this acceptance contract."""
    receipt = build_context_receipt(ROOT, expected_canonical=_canonical_worktree())
    failed = [
        check
        for check in receipt["continuity"]["checks"]
        if check["level"] == "FAIL"
    ]
    assert receipt["ok"] is True, failed

    authorities = receipt["documentation"]["authorities"]
    reading_order = receipt["documentation"]["reading_order"]
    required_sources = {
        "product_purpose": "docs/NORTH_STAR.md",
        "architecture": "docs/ARCHITECTURE.md",
        "decisions": "docs/DECISIONS.md",
        "roadmap": "docs/ROADMAP.md",
        "live_status": "docs/PROJECT_STATUS.md",
        "active_mission": "docs/ACTIVE_MISSION.md",
        "session_checkpoint": ".claude/STATE.md",
    }
    assert {key: authorities[key] for key in required_sources} == required_sources
    assert all(path in reading_order for path in required_sources.values())

    documents = {
        concern: (ROOT / path).read_text(encoding="utf-8")
        for concern, path in required_sources.items()
    }
    boundary = (ROOT / "docs/adr/0017-kitty-mission-builder-control-plane.md").read_text(
        encoding="utf-8"
    )

    # 1. What is Kitty?
    assert "Kitty is how Jacob gets help" in documents["product_purpose"]
    assert "Kitty is the principal product agent" in documents["architecture"]
    # 2–3. What is KittyBuilder and what is the boundary?
    assert "KittyBuilder is the execution organization" in documents["architecture"]
    assert "approved Mission and authored packets → KittyBuilder" in boundary
    assert "Builder does not invent the roadmap" in boundary
    # 4. What is shipped?
    assert "What's shipped" in documents["live_status"] or "Shipped" in documents["live_status"]
    assert "Builder investigation" in documents["live_status"]
    # 5. What is active?
    # Asserting the mission's title would break on every legitimate mission
    # change. The cold-start question is "is a mission declared and readable",
    # so check the document's shape and let the receipt below prove liveness.
    assert documents["active_mission"].startswith("# Active Mission — ")
    # A heading alone is not an answer: both sections were once added empty to
    # satisfy this check, which left a cold reader with no objective to read.
    assert _section_body(documents["active_mission"], "## Objective")
    assert _section_body(documents["active_mission"], "## Acceptance Contract")
    assert receipt["continuity"]["active_mission"]["status"] == "running"
    # 6. What is next?
    assert isinstance(receipt["next_action"], str) and receipt["next_action"]
    # 7. What is stale or uncertain?
    assert receipt["unknowns"]
    assert "git.origin_main.remote_freshness" in {
        item["field"] for item in receipt["unknowns"]
    }
    # 8. What file is authoritative?
    assert receipt["documentation"]["authority_map"] == "docs/AUTHORITY_MAP.md"
