"""Proactive Nudge Engine — detect patterns and suggest actions without being asked.

Triggers:
- Repeated research: same topic 3x without action → nudge
- Dropped threads: topic mentioned then silence → check-in
- Milestones: first completed build, health streak → celebrate
- Time-based: calendar gap → suggest activity

Public API:
  check() -> list[dict]                Run all nudge checks, return active nudges
  check_with_status() -> dict          Run checks with per-source failure reporting
  dismiss(nudge_id) -> bool
  get_pending() -> list[dict]
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import Counter

from gateway.paths import DATA_DIR, LOG_FILE

logger = logging.getLogger("kitty.nudge")

NUDGE_STORE = DATA_DIR / "nudge_state.json"


class _PartialFailure(Exception):
    """Raised by a detector when some sub-checks succeed and others fail.

    Carries the nudges from successful sub-checks so callers can return
    partial results while reporting degraded status.
    """

    def __init__(self, nudges: list[dict], failed_parts: list[str]) -> None:
        self.nudges = nudges
        self.failed_parts = failed_parts
        super().__init__(f"partial failure: {', '.join(failed_parts)}")


def _run_detector(name: str, detector_fn) -> tuple[list[dict], dict]:
    """Run a single nudge detector and capture its status.

    Returns (nudges, status_dict) where status_dict has at minimum a
    ``"status"`` key that is one of ``"healthy"``, ``"degraded"``, or
    ``"failed"``.
    """
    try:
        nudges = detector_fn()
        return nudges, {"status": "healthy"}
    except _PartialFailure as exc:
        # Partial success: return nudges from successful sub-checks.
        logger.warning("%s check partially failed: %s", name, exc)
        return exc.nudges, {"status": "degraded", "error": str(exc)[:200]}
    except Exception as exc:
        logger.exception("%s check failed", name)
        return [], {"status": "failed", "error": str(exc)[:200]}


def check_with_status() -> dict:
    """Run all nudge checks with per-source status reporting.

    Returns dict with keys:

    * ``nudges`` – list of active nudges (same format as :func:`check`)
    * ``sources`` – dict mapping detector name to status info
    """
    sources: dict = {}
    all_nudges: list[dict] = []

    detectors = [
        ("repeated_research", _check_repeated_research),
        ("dropped_threads", _check_dropped_threads),
        ("milestones", _check_milestones),
    ]

    for name, fn in detectors:
        nudges, status = _run_detector(name, fn)
        sources[name] = status
        all_nudges.extend(nudges)

    # Filter already dismissed
    dismissed = _load_dismissed()
    active = [n for n in all_nudges if n.get("id") not in dismissed]

    if active:
        logger.info("Nudge engine: %d active nudges", len(active))
        _emit_nudge_signals(active)

    return {"nudges": active, "sources": sources}


def check() -> list[dict]:
    """Run all nudge checks. Returns list of active nudges."""
    return check_with_status()["nudges"]


def _emit_nudge_signals(nudges: list[dict]) -> None:
    """Write each active nudge to the signal store so downstream consumers see it."""
    try:
        from gateway.signal_store import emit

        for nudge in nudges:
            emit(
                source="nudge",
                kind=nudge.get("type", "nudge"),
                payload={
                    "nudge_id": nudge.get("id"),
                    "message": nudge.get("message"),
                    "priority": nudge.get("priority"),
                },
                dedupe_key=nudge.get("id"),
            )
    except Exception:
        logger.exception("Failed to emit nudge signals")


def dismiss(nudge_id: str) -> bool:
    """Dismiss a nudge so it won't show again."""
    dismissed = _load_dismissed()
    dismissed.add(nudge_id)
    _save_dismissed(dismissed)
    return True


def get_pending() -> list[dict]:
    """Get currently pending (non-dismissed) nudges."""
    return check()


# --- Triggers ---

def _check_repeated_research() -> list[dict]:
    """Detect topics researched 3+ times with no action."""
    if not LOG_FILE.exists():
        return []

    cutoff = time.time() - 14 * 86400  # last 2 weeks
    topics: Counter = Counter()
    with LOG_FILE.open("r") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("timestamp", 0) < cutoff:
                    continue
                if entry.get("domain_classified") in ("research", "code", "repair"):
                    topic = entry.get("user_request", "")[:80].lower()
                    topics[topic] += 1
            except json.JSONDecodeError:
                continue

    nudges = []
    for topic, count in topics.most_common(10):
        if count >= 3:
            nudge_id = hashlib.md5(f"repeat_{topic}".encode()).hexdigest()[:12]
            nudges.append({
                "id": nudge_id,
                "type": "repeated_research",
                "message": f"You've researched '{topic[:60]}' {count} times. Want me to take action on this?",
                "priority": "medium",
            })
    return nudges[:3]


def _check_dropped_threads() -> list[dict]:
    """Detect topics that were mentioned then dropped."""
    if not LOG_FILE.exists():
        return []

    now = time.time()
    threads: dict[str, dict] = {}

    with LOG_FILE.open("r") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                ts = entry.get("timestamp", 0)
                text = entry.get("user_request", "")[:100]
                if ts > now - 14 * 86400:
                    key = text.lower()[:60]
                    if key not in threads or threads[key]["ts"] < ts:
                        threads[key] = {"ts": ts, "text": text}
            except json.JSONDecodeError:
                continue

    nudges = []
    for key, data in threads.items():
        days_since = (now - data["ts"]) / 86400
        if 3 <= days_since <= 14:
            nudge_id = hashlib.md5(f"drop_{key}".encode()).hexdigest()[:12]
            nudges.append({
                "id": nudge_id,
                "type": "dropped_thread",
                "message": f"You mentioned '{data['text'][:60]}' {int(days_since)} days ago — still thinking about it?",
                "priority": "low",
            })
    return nudges[:3]


def _check_milestones() -> list[dict]:
    """Detect celebration-worthy milestones."""
    nudges = []
    failed_parts: list[str] = []

    # Check completed durable Builder initiatives.
    try:
        from gateway.builder_initiative import list_initiatives

        initiatives = list_initiatives()
        completed = [
            item
            for item in initiatives
            if (item.get("health_summary") or {}).get("state") == "completed"
        ]
        if len(completed) == 1:
            nudges.append({
                "id": "milestone_first_build",
                "type": "milestone",
                "message": "First build completed! That's a milestone worth noting.",
                "priority": "high",
            })
        elif len(completed) == 10:
            nudges.append({
                "id": "milestone_10_builds",
                "type": "milestone",
                "message": "You've completed 10 builds now — that's a real streak.",
                "priority": "high",
            })
    except Exception:
        logger.exception("build milestone check failed")
        failed_parts.append("builder_initiatives")

    # Check memory count
    try:
        from gateway.memory import list_memories
        memories = list_memories(limit=0)
        count = len(memories) if isinstance(memories, list) else 0
        if count >= 100:
            nudges.append({
                "id": "milestone_100_memories",
                "type": "milestone",
                "message": f"Kitty now has {count} memories about you. She's getting to know you.",
                "priority": "medium",
            })
    except Exception:
        logger.exception("memory milestone check failed")
        failed_parts.append("memory")

    if failed_parts:
        raise _PartialFailure(nudges, failed_parts)

    return nudges


# --- Persistence ---

def _load_dismissed() -> set:
    try:
        if NUDGE_STORE.exists():
            data = json.loads(NUDGE_STORE.read_text())
            return set(data.get("dismissed", []))
    except Exception:
        logger.warning("_load_dismissed: failed to read or parse %s", NUDGE_STORE)
    return set()


def _save_dismissed(dismissed: set) -> None:
    NUDGE_STORE.parent.mkdir(parents=True, exist_ok=True)
    NUDGE_STORE.write_text(json.dumps({"dismissed": list(dismissed), "updated": time.time()}, indent=2))
