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

The loop is deliberately thin: it owns orchestration and budgets only. All
real work (worker execution, validation, review, publish, merge) is delegated
to the stage modules. It never force-pushes and never advances a task past
the state its workers (or, for merges, the CP-06 evidence gate) leave it in.
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
    """The crude, mechanical (validation command, exit code, review finding
    class) tuple two attempts must share to count as "the same failure".
    Deliberately not output-diffing or fuzzy matching — see CP-03 note.
    """
    validation_failure = attempt.get("validation_failure") or {}
    review_finding_class = attempt.get("review_finding_class")
    return (
        validation_failure.get("command"),
        validation_failure.get("exit_code"),
        tuple(review_finding_class) if review_finding_class else None,
    )


def _classify_exhaustion(loop_result: dict[str, Any]) -> dict[str, Any]:
    """Classify why a packet exhausted: routine retry-out, or a decision
    that needs Jacob. Returns at least ``stop_class`` and ``reason``; a
    scope/identity escalation also carries ``findings``.
    """
    escalation = loop_result.get("escalation")
    if escalation is not None:
        return {
            "stop_class": STOP_NEEDS_DECISION,
            "reason": "packet requires scope or identity judgment",
            "findings": escalation.get("findings", []),
        }

    attempts = loop_result.get("attempts", [])
    budget_consuming = [
        a for a in attempts if a.get("outcome") in ba._BUDGET_CONSUMING_OUTCOMES
    ]
    if len(budget_consuming) >= 2:
        signatures = {_failure_signature(a) for a in budget_consuming}
        if len(signatures) == 1:
            return {
                "stop_class": STOP_NEEDS_DECISION,
                "reason": "requirement may be ambiguous",
            }
    return {"stop_class": STOP_ROUTINE, "reason": "packet exhausted"}


def _decide(
    task_id: str, payload: dict[str, Any], db_path: Path | None
) -> None:
    """Log a durable packet decision. Fail-loud on a missing task log."""
    bq.append_event(task_id, EVENT_DECISION, payload, db_path=db_path)


def _packet_validation_commands(
    initiative_id: str, packet_id: str, db_path: Path | None
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
    """CP-06: merge behind the evidence gate, revalidate, revert on red.

    Never raises — a merge-path failure degrades to the pre-CP-06
    park-at-awaiting_review shape (``outcome: "merge_failed"``) rather than
    aborting the whole initiative run over an infrastructure hiccup.
    """
    validation_commands = _packet_validation_commands(
        initiative_id, packet_id, db_path
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
    else:  # skipped_tripwire
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
    repo_root: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Drive an initiative to completion, one eligible packet at a time.

    Returns a summary dict: ``outcome`` is one of ``idle`` (no eligible packet
    left), ``paused`` (budget exceeded or operator pause), or ``aborted`` (loop
    error that cannot be reconciled here). ``processed`` lists per-packet
    outcomes; ``reason`` explains any non-idle exit.
    """
    if max_initiative_attempts is not None and max_initiative_attempts < 0:
        raise ValueError("max_initiative_attempts must be non-negative")
    if max_runtime_seconds is not None and max_runtime_seconds <= 0:
        raise ValueError("max_runtime_seconds must be positive")
    if gate not in (GATE_AUTO, GATE_MANUAL):
        raise ValueError(f"gate must be {GATE_AUTO!r} or {GATE_MANUAL!r}, got {gate!r}")

    bi.init_db(db_path)
    # Restart reconciliation is part of the durable loop contract: stale
    # leases/runs must be resolved before another packet can be claimed.
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
                initiative_id, "initiative runtime budget exceeded", db_path=db_path
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
                        # "merged": task is now DONE; the next while-loop
                        # iteration's next_packet() picks up newly-eligible
                        # downstream packets in this same invocation.
                        # "skipped_tripwire" / "merge_failed": task stays at
                        # awaiting_review; next_packet() finds nothing more
                        # eligible under this packet and the loop exits idle
                        # — the same shape as pre-CP-06 park-and-wait.
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

        if loop_result["outcome"] != "succeeded":
            assert classification is not None  # set in the exhaustion branch above
            pause_reason = f"packet {packet_id} exhausted"
            if classification["stop_class"] == STOP_NEEDS_DECISION:
                pause_reason += f" [needs_decision: {classification['reason']}]"
            else:
                pause_reason += f": {loop_result.get('reason')}"
            bi.pause_initiative(
                initiative_id,
                pause_reason,
                db_path=db_path,
            )
            return {
                "outcome": "paused",
                "reason": f"packet {packet_id} exhausted",
                "stop_class": classification["stop_class"],
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        # Continue to the next eligible packet. Dependent packets remain
        # gated until merge reconciliation promotes this task to DONE.
