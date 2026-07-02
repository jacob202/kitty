"""Proactive Nudge Engine — detect patterns and suggest actions without being asked.

Triggers:
- Repeated research: same topic 3x without action → nudge
- Dropped threads: topic mentioned then silence → check-in
- Milestones: first completed build, health streak → celebrate
- Time-based: calendar gap → suggest activity

Public API:
  check() -> list[dict]     Run all nudge checks, return active nudges
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


def check() -> list[dict]:
    """Run all nudge checks. Returns list of active nudges."""
    nudges = []
    nudges.extend(_check_repeated_research())
    nudges.extend(_check_dropped_threads())
    nudges.extend(_check_milestones())

    # Filter already dismissed
    dismissed = _load_dismissed()
    active = [n for n in nudges if n.get("id") not in dismissed]

    if active:
        logger.info("Nudge engine: %d active nudges", len(active))
        _emit_nudge_signals(active)

    return active


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
    try:
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
    except Exception:
        return []


def _check_dropped_threads() -> list[dict]:
    """Detect topics that were mentioned then dropped."""
    try:
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
    except Exception:
        return []


def _check_milestones() -> list[dict]:
    """Detect celebration-worthy milestones."""
    nudges = []

    # Check build count
    try:
        from gateway.builder import list_builds
        builds = list_builds(limit=50)
        completed = [b for b in builds if b.get("status") == "completed"]
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
        pass

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
        pass

    return nudges


# --- Persistence ---

def _load_dismissed() -> set:
    try:
        if NUDGE_STORE.exists():
            data = json.loads(NUDGE_STORE.read_text())
            return set(data.get("dismissed", []))
    except Exception:
        pass
    return set()


def _save_dismissed(dismissed: set) -> None:
    NUDGE_STORE.parent.mkdir(parents=True, exist_ok=True)
    NUDGE_STORE.write_text(json.dumps({"dismissed": list(dismissed), "updated": time.time()}, indent=2))
