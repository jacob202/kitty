"""KB-S5 — the ``initiative run`` driver loop.

Composes the existing KB stages into a single continuation loop:

    next eligible packet  ->  run_packet (KB-S3b: implement/validate/review/repair)
                          ->  publish_task (KB-S4b: operator-gated push + PR)
                          ->  merge_and_verify (CP-06: evidence-gated auto-merge,
                              gate="auto" only; ADR 0018)

The loop runs until no packet is eligible, or a budget (per-initiative attempt
count or wall-clock runtime) is exhausted, or an operator pause is observed.
Each packet decision is written durably to the events table so a restart can
reconcile what already happened.

The loop is deliberately thin: it owns orchestration, budgets, and the
outcome-level effectiveness stop. All real work (worker execution, validation,
review, publish, merge) is delegated to the stage modules. It never force-pushes
and never advances a task past the state its workers (or, for merges, the CP-06
evidence gate) leave it in.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_publish as bp
from gateway import builder_queue as bq
from gateway import operating_policy as op

EVENT_DECISION = "initiative_decision"

# CP-06 gate modes for ``initiative run``. "auto" (default) merges behind
# the evidence gate (validation green + reviewer approve + scope clean,
# already true by the time a packet reaches "succeeded") with auto-revert
# on post-merge red. "manual" restores the pre-CP-06 park-at-awaiting_review
# behavior for campaigns Jacob wants to eyeball by hand.
GATE_AUTO = "auto"
GATE_MANUAL = "manual"

# CP-03 stop classification. See docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md
# §1.3/§4.4: budget/exhaustion/timeouts with differing failure signatures are
# ``routine`` (retry or hand off, no judgment needed); scope/identity
# escalation and same-signature exhaustion are ``needs_decision`` (ask
# Jacob). On any doubt this classifier is biased toward ``needs_decision`` —
# that's the correct failure direction, per the plan doc.
STOP_ROUTINE = "routine"
STOP_NEEDS_DECISION = "needs_decision"


def _failure_signature(attempt: dict[str, Any]) -> tuple[Any, Any, Any]:
    """The crude, mechanical failure signature used for repeat detection."""
    validation_failure = attempt.get("validation_failure") or {}
    review_finding_class = attempt.get("review_finding_class")
    return (
        validation_failure.get("command"),
        validation_failure.get("exit_code"),
        tuple(review_finding_class) if review_finding_class else None,
    )


def _classify_exhaustion(loop_result: dict[str, Any]) -> dict[str, Any]:
    """Classify packet exhaustion as routine or requiring Jacob's decision."""
    escalation = loop_result.get("escalation")
    if escalation is not None:
        return {
            "stop_class": STOP_NEEDS_DECISION,
            "reason": "packet requires scope or identity judgment",
            "findings": escalation.get("findings", []),
        }

    attempts = loop_result.get("attempts", [])
    budget_consuming = [
        attempt
        for attempt in attempts
        if attempt.get("outcome") in ba._BUDGET_CONSUMING_OUTCOMES
    ]
    if len(budget_consuming) >= 2:
        signatures = {_failure_signature(attempt) for attempt in budget_consuming}
        if len(signatures) == 1:
            return {
                "stop_class": STOP_NEEDS_DECISION,
                "reason": "requirement may be ambiguous",
            }
    return {"stop_class": STOP_ROUTINE, "reason": "packet exhausted"}


def _cancellation_provenance(loop_result: dict[str, Any]) -> dict[str, Any]:
    """Keep the worker-run evidence that caused a packet cancellation."""
    attempts = loop_result.get("attempts")
    latest = attempts[-1] if isinstance(attempts, list) and attempts else None
    provenance: dict[str, Any] = {"source": "worker_run"}
    if not isinstance(latest, dict):
        return provenance
    for key in ("attempt_id", "run_id"):
        if latest.get(key) is not None:
            provenance[key] = latest[key]
    return provenance


def _decide(
    task_id: str,
    payload: dict[str, Any],
    db_path: Path | None,
) -> None:
    """Log a durable packet decision. Fail-loud on a missing task log."""
    bq.append_event(task_id, EVENT_DECISION, payload, db_path=db_path)


def _effectiveness_metrics(
    *,
    campaign_started: float,
    packet_started: float,
    processed_packets: int,
    accepted_packets: int,
) -> dict[str, float | int | None]:
    """Measurements the initiative loop owns without guessing.

    Builder does not yet have trustworthy cumulative token, metadata-time,
    reset, blocker, projection, or simple-baseline measurements. They remain
    ``None``. After the policy observation window that missing telemetry is a
    pause condition, not permission to continue indefinitely.
    """
    now = time.monotonic()
    return {
        "elapsed_seconds": max(now - campaign_started, 0.0),
        "processed_packets": processed_packets,
        "accepted_packets": accepted_packets,
        "current_packet_elapsed_seconds": max(now - packet_started, 0.0),
        "consecutive_no_substantive_diff": None,
        "setup_metadata_seconds": None,
        "supervisor_tokens": None,
        "worker_tokens": None,
        "reset_recovery_events": None,
        "repeated_systemic_blocker_count": None,
        "projected_completion_seconds": None,
        "simple_baseline_seconds": None,
    }


def _effectiveness_pause(
    initiative_id: str,
    packet_id: str,
    task_id: str,
    *,
    campaign_started: float,
    packet_started: float,
    processed_packets: int,
    accepted_packets: int,
    db_path: Path | None,
) -> dict[str, Any] | None:
    """Pause a campaign that is durable but not economically trustworthy."""
    metrics = _effectiveness_metrics(
        campaign_started=campaign_started,
        packet_started=packet_started,
        processed_packets=processed_packets,
        accepted_packets=accepted_packets,
    )
    decision = op.evaluate_builder_campaign(metrics)
    if decision.status not in {"pause", "insufficient_evidence"}:
        return None

    reasons = list(decision.reasons)
    if not reasons:
        reasons = [
            "Builder lacks the core measurements required to judge campaign effectiveness"
        ]
    reason = "Builder effectiveness guard: " + "; ".join(reasons)
    bi.pause_initiative(initiative_id, reason, db_path=db_path)
    _decide(
        task_id,
        {
            "initiative_id": initiative_id,
            "packet_id": packet_id,
            "decision": "effectiveness_paused",
            "reason": reason,
            "stop_class": STOP_ROUTINE,
            "effectiveness": decision.to_dict(),
            "metrics": metrics,
        },
        db_path,
    )
    return {
        "outcome": "paused",
        "reason": reason,
        "stop_class": STOP_ROUTINE,
        "effectiveness": decision.to_dict(),
    }


def _packet_validation_commands(
    initiative_id: str,
    packet_id: str,
    db_path: Path | None,
) -> list[str]:
    conn = bq.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT validation_commands_json FROM initiative_packets
            WHERE initiative_id = ? AND packet_id = ?
            """,
            (initiative_id, packet_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None or not row["validation_commands_json"]:
        return []
    return json.loads(row["validation_commands_json"])


def _attempt_auto_merge(
    initiative_id: str,
    packet_id: str,
    task_id: str,
    *,
    repo_root: Path | None,
    db_path: Path | None,
) -> dict[str, Any]:
    """CP-06: merge behind the evidence gate, revalidate, revert on red."""
    validation_commands = _packet_validation_commands(
        initiative_id,
        packet_id,
        db_path,
    )
    try:
        result = bp.merge_and_verify(
            task_id,
            validation_commands=validation_commands,
            repo_root=repo_root,
            db_path=db_path,
        )
    except bp.MergeError as exc:
        _decide(
            task_id,
            {
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "decision": "merge_failed",
                "reason": str(exc),
                "stop_class": STOP_ROUTINE,
            },
            db_path,
        )
        return {"outcome": "merge_failed", "reason": str(exc)}

    if result["outcome"] == "merged":
        _decide(
            task_id,
            {
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "decision": "auto_merged",
                "pr_number": result.get("pr_number"),
                "merge_commit_sha": result.get("merge_commit_sha"),
                "stop_class": STOP_ROUTINE,
            },
            db_path,
        )
    elif result["outcome"] == "reverted":
        _decide(
            task_id,
            {
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "decision": "auto_merge_reverted",
                "reason": "post-merge validation failed on main",
                "revalidation": result.get("revalidation"),
                "revert": result.get("revert"),
                "stop_class": STOP_NEEDS_DECISION,
                "stop_class_reason": "post-merge validation failed on main",
            },
            db_path,
        )
    else:
        _decide(
            task_id,
            {
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "decision": "auto_merge_skipped_tripwire",
                "reason": (
                    f"{bp.TRIPWIRE_THRESHOLD}+ reverts in the last "
                    f"{bp.TRIPWIRE_WINDOW} auto-merges — parking at "
                    "awaiting_review until enough clean merges clear it"
                ),
                "stop_class": STOP_ROUTINE,
            },
            db_path,
        )
    return result


def run_initiative(
    initiative_id: str,
    *,
    worker_command: list[str],
    review_command: list[str] | None = None,
    worker: str = "builder-loop",
    model: str | None = None,
    provider: str | None = None,
    timeout_seconds: int = 3600,
    validation_timeout_seconds: int = 900,
    review_timeout_seconds: int = 900,
    publish: bool = False,
    gate: str = GATE_AUTO,
    max_initiative_attempts: int | None = None,
    max_runtime_seconds: int | None = None,
    effectiveness_guard: bool = True,
    repo_root: Path | None = None,
    db_path: Path | None = None,
    governor_db: Path | None = None,
) -> dict[str, Any]:
    """Drive an initiative to completion, one eligible packet at a time.

    ``effectiveness_guard`` is default-on. It evaluates the campaign after each
    durable packet outcome and pauses on wall-time, packet-time, throughput, or
    missing post-observation telemetry. Disabling it is an explicit operator
    action intended for bounded diagnostics, not normal campaigns.
    """
    if max_initiative_attempts is not None and max_initiative_attempts < 0:
        raise ValueError("max_initiative_attempts must be non-negative")
    if max_runtime_seconds is not None and max_runtime_seconds <= 0:
        raise ValueError("max_runtime_seconds must be positive")
    if gate not in (GATE_AUTO, GATE_MANUAL):
        raise ValueError(
            f"gate must be {GATE_AUTO!r} or {GATE_MANUAL!r}, got {gate!r}"
        )

    bi.init_db(db_path)
    bq.recover_expired_leases(db_path=db_path)
    bq.recover_interrupted_runs(db_path=db_path)
    started = time.monotonic()
    total_attempts = 0
    processed: list[dict[str, Any]] = []
    succeeded = 0
    exhausted = 0

    while True:
        if bi.get_initiative_state(initiative_id, db_path=db_path) == bi.INITIATIVE_PAUSED:
            return {
                "outcome": "paused",
                "reason": "initiative paused before loop step",
                "stop_class": STOP_ROUTINE,
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        packet = bi.next_packet(initiative_id, db_path=db_path)
        if packet is None:
            return {
                "outcome": "idle",
                "reason": "no eligible packet",
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        if (
            max_initiative_attempts is not None
            and total_attempts >= max_initiative_attempts
        ):
            bi.pause_initiative(
                initiative_id,
                "initiative attempt budget exceeded",
                db_path=db_path,
            )
            _decide(
                packet["task_id"],
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet["packet_id"],
                    "decision": "run_paused",
                    "reason": "attempt budget exceeded",
                    "stop_class": STOP_ROUTINE,
                },
                db_path,
            )
            return {
                "outcome": "paused",
                "reason": "attempt budget exceeded",
                "stop_class": STOP_ROUTINE,
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        packet_id = packet["packet_id"]
        task_id = packet["task_id"]

        if (
            max_runtime_seconds is not None
            and (time.monotonic() - started) > max_runtime_seconds
        ):
            bi.pause_initiative(
                initiative_id,
                "initiative runtime budget exceeded",
                db_path=db_path,
            )
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "run_paused",
                    "reason": "runtime budget exceeded",
                    "stop_class": STOP_ROUTINE,
                },
                db_path,
            )
            return {
                "outcome": "paused",
                "reason": "runtime budget exceeded",
                "stop_class": STOP_ROUTINE,
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        packet_started = time.monotonic()
        try:
            loop_result = bl.run_packet(
                initiative_id,
                packet_id,
                worker_command=worker_command,
                review_command=review_command,
                worker=worker,
                model=model,
                provider=provider,
                timeout_seconds=timeout_seconds,
                validation_timeout_seconds=validation_timeout_seconds,
                review_timeout_seconds=review_timeout_seconds,
                repo_root=repo_root,
                db_path=db_path,
                governor_db=governor_db,
            )
        except bl.LoopError as exc:
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "aborted",
                    "reason": str(exc),
                    "stop_class": STOP_ROUTINE,
                },
                db_path,
            )
            return {
                "outcome": "aborted",
                "reason": f"loop error on {packet_id}: {exc}",
                "stop_class": STOP_ROUTINE,
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }
        except Exception as exc:
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "aborted",
                    "reason": f"unexpected loop failure: {exc}",
                    "stop_class": STOP_ROUTINE,
                },
                db_path,
            )
            return {
                "outcome": "aborted",
                "reason": f"unexpected loop failure on {packet_id}: {exc}",
                "stop_class": STOP_ROUTINE,
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        total_attempts += len(loop_result.get("attempts", []))
        classification: dict[str, Any] | None = None

        if loop_result["outcome"] == "succeeded":
            succeeded += 1
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "packet_succeeded",
                },
                db_path,
            )
            if publish:
                try:
                    pub = bp.publish_task(
                        task_id,
                        repo_root=repo_root,
                        db_path=db_path,
                    )
                    _decide(
                        task_id,
                        {
                            "initiative_id": initiative_id,
                            "packet_id": packet_id,
                            "decision": "published",
                            "pr": pub.get("pr"),
                        },
                        db_path,
                    )
                    if gate == GATE_AUTO:
                        merge_result = _attempt_auto_merge(
                            initiative_id,
                            packet_id,
                            task_id,
                            repo_root=repo_root,
                            db_path=db_path,
                        )
                        if merge_result["outcome"] == "reverted":
                            processed.append(
                                {
                                    "packet_id": packet_id,
                                    "task_id": task_id,
                                    "outcome": loop_result["outcome"],
                                }
                            )
                            bi.pause_initiative(
                                initiative_id,
                                f"auto-merge reverted for {task_id}: "
                                "post-merge validation failed on main",
                                db_path=db_path,
                            )
                            return {
                                "outcome": "paused",
                                "reason": f"auto-merge reverted for {task_id}",
                                "stop_class": STOP_NEEDS_DECISION,
                                "processed": processed,
                                "succeeded": succeeded,
                                "exhausted": exhausted,
                            }
                except bp.PublishError as exc:
                    _decide(
                        task_id,
                        {
                            "initiative_id": initiative_id,
                            "packet_id": packet_id,
                            "decision": "publish_skipped",
                            "reason": str(exc),
                            "stop_class": STOP_ROUTINE,
                        },
                        db_path,
                    )
                    processed.append(
                        {
                            "packet_id": packet_id,
                            "task_id": task_id,
                            "outcome": loop_result["outcome"],
                        }
                    )
                    bi.pause_initiative(
                        initiative_id,
                        f"publish failed for {task_id}: {exc}",
                        db_path=db_path,
                    )
                    return {
                        "outcome": "paused",
                        "reason": f"publish failed for {task_id}: {exc}",
                        "stop_class": STOP_ROUTINE,
                        "processed": processed,
                        "succeeded": succeeded,
                        "exhausted": exhausted,
                    }
        elif loop_result["outcome"] == bl.LOOP_PROVIDER_EXHAUSTED:
            processed.append(
                {
                    "packet_id": packet_id,
                    "task_id": task_id,
                    "outcome": loop_result["outcome"],
                }
            )
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "provider_exhausted",
                    "reason": loop_result.get("reason"),
                    "stop_class": STOP_ROUTINE,
                },
                db_path,
            )
            bi.pause_initiative(
                initiative_id,
                f"provider exhaustion on {packet_id}; resumable when providers recover",
                db_path=db_path,
            )
            return {
                "outcome": "paused",
                "reason": f"provider exhaustion on {packet_id}",
                "stop_class": STOP_ROUTINE,
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }
        elif loop_result["outcome"] == bl.LOOP_CANCELLED:
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "packet_cancelled",
                    "reason": loop_result.get("reason"),
                    "stop_class": STOP_ROUTINE,
                    "provenance": _cancellation_provenance(loop_result),
                },
                db_path,
            )
        else:
            exhausted += 1
            classification = _classify_exhaustion(loop_result)
            decision_payload: dict[str, Any] = {
                "initiative_id": initiative_id,
                "packet_id": packet_id,
                "decision": "packet_exhausted",
                "reason": loop_result.get("reason"),
                "stop_class": classification["stop_class"],
                "stop_class_reason": classification["reason"],
            }
            if "findings" in classification:
                decision_payload["findings"] = classification["findings"]
            _decide(task_id, decision_payload, db_path)

        processed.append(
            {
                "packet_id": packet_id,
                "task_id": task_id,
                "outcome": loop_result["outcome"],
            }
        )

        if effectiveness_guard:
            pause = _effectiveness_pause(
                initiative_id,
                packet_id,
                task_id,
                campaign_started=started,
                packet_started=packet_started,
                processed_packets=len(processed),
                accepted_packets=succeeded,
                db_path=db_path,
            )
            if pause is not None:
                return {
                    **pause,
                    "processed": processed,
                    "succeeded": succeeded,
                    "exhausted": exhausted,
                }

        if loop_result["outcome"] == bl.LOOP_CANCELLED:
            continue

        if loop_result["outcome"] != "succeeded":
            assert classification is not None
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "continued_after_packet_failure",
                    "reason": loop_result.get("reason"),
                    "stop_class": classification["stop_class"],
                    "stop_class_reason": classification["reason"],
                },
                db_path,
            )
            continue

        # Continue to the next eligible packet. Dependent packets remain gated
        # until merge reconciliation promotes this task to DONE.
