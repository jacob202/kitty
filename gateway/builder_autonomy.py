"""Read-only autonomy projections for Builder runway and operator decisions.

This module never mutates the queue. It derives a bounded operating picture
from Builder's durable initiative/task evidence plus an optional packet
registry for interactive/held contracts that Builder itself cannot execute.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_brief import default_branch_name

LOW_WATER_DEFAULT = 6
REFILL_TARGET_DEFAULT = 12
_DONE_REGISTRY_STATES = frozenset({"done", "landed", "merged", "superseded", "closed"})


class PacketRegistryError(RuntimeError):
    """Raised when compiled packet-registry evidence cannot be trusted."""


def load_packet_registry(repo_root: Path) -> list[dict[str, Any]]:
    """Read compiled source slates only; malformed source evidence fails closed."""
    registry: list[dict[str, Any]] = []
    slate_dir = Path(repo_root) / "docs" / "packets" / "slates"
    for path in sorted(slate_dir.glob("*.source.json")):
        try:
            slate = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PacketRegistryError(f"cannot read packet registry {path.name}: {exc}") from exc
        if not isinstance(slate, dict):
            raise PacketRegistryError(f"packet registry {path.name} must contain an object")
        packets = slate.get("packets", [])
        if not isinstance(packets, list):
            raise PacketRegistryError(f"packet registry {path.name} packets must be a list")
        initiative_id = slate.get("initiative_id")
        for item in packets:
            if not isinstance(item, dict):
                raise PacketRegistryError(f"packet registry {path.name} contains a non-object packet")
            manifest = item.get("manifest") or {}
            packet_id = manifest.get("id") if isinstance(manifest, dict) else None
            if not isinstance(packet_id, str) or not packet_id:
                raise PacketRegistryError(f"packet registry {path.name} contains a packet without manifest.id")
            entry: dict[str, Any] = {
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "lane": item.get("lane") or "builder",
                "status": item.get("status") or "unresolved",
            }
            if item.get("hold_reason"):
                entry["hold_reason"] = item["hold_reason"]
            if item.get("superseded_by"):
                entry["superseded_by"] = item["superseded_by"]
            registry.append(entry)
    return registry


def _packet_key(initiative_id: str, packet_id: str) -> str:
    return f"{initiative_id}/{packet_id}"


def _new_buckets() -> dict[str, list[dict[str, Any]]]:
    return {
        "safe_backend_runnable": [],
        "interactive_frontend": [],
        "collision_held": [],
        "operator_blocked": [],
        "running": [],
        "pending_backend": [],
    }


def _registry_packet_id(item: dict[str, Any]) -> str | None:
    value = item.get("packet_id", item.get("id"))
    return str(value) if isinstance(value, str) and value.strip() else None


def _registry_done(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or "unresolved").lower()
    return bool(item.get("superseded_by")) or status in _DONE_REGISTRY_STATES


def _append(
    buckets: dict[str, list[dict[str, Any]]],
    bucket: str,
    *,
    initiative_id: str | None,
    packet_id: str,
    task_id: str | None = None,
    reason: str | None = None,
    source: str = "builder",
) -> None:
    entry: dict[str, Any] = {
        "initiative_id": initiative_id,
        "packet_id": packet_id,
        "task_id": task_id,
        "source": source,
    }
    if reason:
        entry["reason"] = reason
    buckets[bucket].append(entry)


def _classify_builder_status(
    initiative: dict[str, Any],
    status: dict[str, Any],
    buckets: dict[str, list[dict[str, Any]]],
    seen: set[str],
    *,
    db_path: Path | None,
    github_truth: dict[str, Any] | None,
) -> None:
    initiative_id = str(initiative["id"])
    evidence = status.get("evidence") or {}
    eligible = set(status.get("eligible") or []) | set(status.get("recovery_needed") or [])
    blocked = set(status.get("blocked") or []) | set(status.get("failed") or []) | set(status.get("exhausted") or [])
    in_progress = set(status.get("in_progress") or [])
    pending = set(status.get("pending") or [])
    done = set(status.get("done") or [])

    for packet_id, packet_evidence in evidence.items():
        packet_id = str(packet_id)
        seen.add(_packet_key(initiative_id, packet_id))
        if packet_id in done or packet_evidence.get("done"):
            continue
        task_id = packet_evidence.get("task_id")
        github_unavailable = (
            github_truth is not None and not bool(github_truth.get("available"))
        )
        needs_external_truth = (
            (
                packet_evidence.get("review_approved")
                and not packet_evidence.get("pr_opened")
            )
            or (
                packet_id in eligible
                and initiative.get("state") == bi.INITIATIVE_ACTIVE
            )
        )
        if github_unavailable and needs_external_truth:
            _append(
                buckets, "operator_blocked", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id, reason="github_truth_unavailable",
            )
            continue

        external_pr: dict[str, Any] | None = None
        if github_truth is not None and task_id:
            task = bq.get_task(str(task_id), db_path=db_path)
            if task is not None:
                branch = default_branch_name(task)
                candidate = (github_truth.get("by_head") or {}).get(branch)
                if isinstance(candidate, dict):
                    external_pr = candidate
        if external_pr is not None and external_pr.get("mergedAt"):
            continue
        if external_pr is not None and external_pr.get("state") == "OPEN":
            _append(
                buckets, "operator_blocked", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id, reason="github_pr_open",
            )
        elif packet_evidence.get("review_approved") and not packet_evidence.get("pr_opened"):
            _append(
                buckets, "operator_blocked", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id, reason="publication_ready",
            )
        elif packet_id in eligible and initiative.get("state") == bi.INITIATIVE_ACTIVE:
            _append(
                buckets, "safe_backend_runnable", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id,
            )
        elif packet_id in blocked or packet_evidence.get("exhausted"):
            _append(
                buckets, "operator_blocked", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id, reason="builder_blocked",
            )
        elif packet_id in in_progress:
            state = str(packet_evidence.get("current_state") or "")
            if state == "blocked":
                _append(
                    buckets, "operator_blocked", initiative_id=initiative_id,
                    packet_id=packet_id, task_id=task_id, reason="builder_blocked",
                )
            else:
                _append(
                    buckets, "running", initiative_id=initiative_id,
                    packet_id=packet_id, task_id=task_id,
                )
        elif packet_id in pending:
            _append(
                buckets, "pending_backend", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id, reason="dependency_wait",
            )
        elif initiative.get("state") == bi.INITIATIVE_PAUSED:
            _append(
                buckets, "collision_held", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id, reason="initiative_paused",
            )
        else:
            _append(
                buckets, "pending_backend", initiative_id=initiative_id,
                packet_id=packet_id, task_id=task_id, reason="not_currently_eligible",
            )


def _classify_registry(
    packet_registry: list[dict[str, Any]],
    buckets: dict[str, list[dict[str, Any]]],
    seen: set[str],
    *,
    initiative_prefix: str | None,
) -> None:
    for item in packet_registry:
        packet_id = _registry_packet_id(item)
        if packet_id is None or _registry_done(item):
            continue
        initiative_id = str(item.get("initiative_id") or "registry")
        if initiative_prefix and not initiative_id.startswith(initiative_prefix):
            continue
        key = _packet_key(initiative_id, packet_id)
        if key in seen:
            continue
        lane = str(item.get("lane") or "interactive").lower()
        hold_reason = item.get("hold_reason")
        if hold_reason or lane == "held":
            bucket = "collision_held"
            reason = str(hold_reason or "held")
        elif lane in {"interactive", "frontend", "ui"}:
            bucket = "interactive_frontend"
            reason = None
        elif lane in {"builder", "backend", "safe"}:
            bucket = "operator_blocked"
            reason = "unapplied_registry_contract"
        else:
            bucket = "operator_blocked"
            reason = f"unknown_lane:{lane}"
        _append(
            buckets,
            bucket,
            initiative_id=item.get("initiative_id"),
            packet_id=packet_id,
            reason=reason,
            source="registry",
        )
        seen.add(key)


def runway_snapshot(
    *,
    db_path: Path | None = None,
    packet_registry: list[dict[str, Any]] | None = None,
    low_water_threshold: int = LOW_WATER_DEFAULT,
    reconciliation: dict[str, Any] | None = None,
    github_truth: dict[str, Any] | None = None,
    initiative_prefix: str | None = None,
) -> dict[str, Any]:
    """Return mutually exclusive packet reservoirs without mutating Builder."""
    if low_water_threshold < 1:
        raise ValueError("low_water_threshold must be >= 1")
    buckets = _new_buckets()
    seen: set[str] = set()
    for initiative in bi.list_initiative_gates(db_path):
        if initiative.get("superseded_by"):
            continue
        initiative_id = str(initiative["id"])
        if initiative_prefix and not initiative_id.startswith(initiative_prefix):
            continue
        status = bi.initiative_status(initiative_id, db_path=db_path)
        _classify_builder_status(
            initiative, status, buckets, seen, db_path=db_path, github_truth=github_truth
        )
    _classify_registry(
        list(packet_registry or []), buckets, seen, initiative_prefix=initiative_prefix
    )

    counts = {name: len(items) for name, items in buckets.items()}
    actionable = counts["safe_backend_runnable"] + counts["interactive_frontend"]
    unresolved_total = sum(counts.values())
    caught_up = unresolved_total == 0
    return {
        "counts": counts,
        "buckets": buckets,
        "actionable": actionable,
        "unresolved_total": unresolved_total,
        "low_water_threshold": low_water_threshold,
        "low_water": (not caught_up and actionable < low_water_threshold),
        "caught_up": caught_up,
        "reconciliation": reconciliation or {},
    }


def usable_builder_runway(runway: dict[str, Any]) -> int:
    """Count durable backend work that can progress without operator intervention.

    Runnable and recoverable packets are already classified into
    ``safe_backend_runnable``. ``running`` also covers claimed/running/review
    pipeline states, while ``pending_backend`` is dependency-gated work inside
    an active non-superseded initiative. Operator-blocked, collision-held, and
    interactive work deliberately do not inflate unattended runway.
    """
    counts = runway.get("counts") or {}
    return sum(
        int(counts.get(name) or 0)
        for name in ("safe_backend_runnable", "running", "pending_backend")
    )


def refill_request(
    runway: dict[str, Any], *, target_candidates: int = REFILL_TARGET_DEFAULT
) -> dict[str, Any]:
    """Describe refill work when runway is low; never creates/applies packets."""
    if target_candidates < 1:
        raise ValueError("target_candidates must be >= 1")
    reconciliation = runway.get("reconciliation") or {}
    if reconciliation.get("github_available") is False:
        return {"needed": False, "reason": "truth_unavailable", "target_candidates": 0}
    if runway.get("caught_up"):
        return {"needed": False, "reason": "caught_up", "target_candidates": 0}
    if not runway.get("low_water"):
        return {"needed": False, "reason": "healthy", "target_candidates": 0}
    return {
        "needed": True,
        "reason": "low_water",
        "target_candidates": target_candidates,
        "actionable": int(runway.get("actionable") or 0),
        "required_candidate_fields": [
            "user_visible_outcome",
            "ownership",
            "dependencies_collision_risks",
            "acceptance_gate",
        ],
    }


def publication_inbox(
    *,
    db_path: Path | None = None,
    github_truth: dict[str, Any] | None = None,
    initiative_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """Reviewed, unpublished Builder packets requiring the existing operator gate."""
    if github_truth is not None and not bool(github_truth.get("available")):
        return []
    inbox: list[dict[str, Any]] = []
    for initiative in bi.list_initiative_gates(db_path):
        if initiative.get("superseded_by"):
            continue
        initiative_id = str(initiative["id"])
        if initiative_prefix and not initiative_id.startswith(initiative_prefix):
            continue
        status = bi.initiative_status(initiative_id, db_path=db_path)
        for packet_id, evidence in (status.get("evidence") or {}).items():
            if evidence.get("done") or evidence.get("pr_opened"):
                continue
            if not evidence.get("review_approved"):
                continue
            task_id = evidence.get("task_id")
            if github_truth is not None and task_id:
                task = bq.get_task(str(task_id), db_path=db_path)
                if task is not None:
                    branch = default_branch_name(task)
                    external_pr = (github_truth.get("by_head") or {}).get(branch)
                    if isinstance(external_pr, dict) and (
                        external_pr.get("state") == "OPEN" or external_pr.get("mergedAt")
                    ):
                        continue
            inbox.append({
                "initiative_id": initiative_id,
                "packet_id": str(packet_id),
                "task_id": str(evidence.get("task_id")),
                "review_verdict": evidence.get("review_verdict"),
                "current_state": evidence.get("current_state"),
            })
    return sorted(inbox, key=lambda item: (item["initiative_id"], item["packet_id"]))
