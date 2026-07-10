"""KB-S5 — the ``initiative run`` driver loop.

Composes the existing KB stages into a single continuation loop:

    next eligible packet  ->  run_packet (KB-S3b: implement/validate/review/repair)
                          ->  publish_task (KB-S4b: operator-gated push + PR)

The loop runs until no packet is eligible, or a budget (per-initiative attempt
count or wall-clock runtime) is exhausted, or an operator pause is observed.
Each packet decision is written durably to the events table so a restart can
reconcile what already happened.

The loop is deliberately thin: it owns orchestration and budgets only. All
real work (worker execution, validation, review, publish) is delegated to the
stage modules. It never force-pushes, never merges, and never advances a task
past the state its workers leave it in.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from gateway import builder_initiative as bi
from gateway import builder_loop as bl
from gateway import builder_publish as bp
from gateway import builder_queue as bq

EVENT_DECISION = "initiative_decision"


def _decide(
    task_id: str, payload: dict[str, Any], db_path: Path | None
) -> None:
    """Log a durable packet decision. Fail-loud on a missing task log."""
    bq.append_event(task_id, EVENT_DECISION, payload, db_path=db_path)


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
            return {
                "outcome": "paused",
                "reason": "attempt budget exceeded",
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
            return {
                "outcome": "paused",
                "reason": "runtime budget exceeded",
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
                },
                db_path,
            )
            return {
                "outcome": "aborted",
                "reason": f"loop error on {packet_id}: {exc}",
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
                },
                db_path,
            )
            return {
                "outcome": "aborted",
                "reason": f"unexpected loop failure on {packet_id}: {exc}",
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        total_attempts += len(loop_result.get("attempts", []))

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
                except bp.PublishError as exc:
                    _decide(
                        task_id,
                        {
                            "initiative_id": initiative_id,
                            "packet_id": packet_id,
                            "decision": "publish_skipped",
                            "reason": str(exc),
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
                        "processed": processed,
                        "succeeded": succeeded,
                        "exhausted": exhausted,
                    }
        else:
            exhausted += 1
            _decide(
                task_id,
                {
                    "initiative_id": initiative_id,
                    "packet_id": packet_id,
                    "decision": "packet_exhausted",
                    "reason": loop_result.get("reason"),
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

        if loop_result["outcome"] != "succeeded":
            bi.pause_initiative(
                initiative_id,
                f"packet {packet_id} exhausted: {loop_result.get('reason')}",
                db_path=db_path,
            )
            return {
                "outcome": "paused",
                "reason": f"packet {packet_id} exhausted",
                "processed": processed,
                "succeeded": succeeded,
                "exhausted": exhausted,
            }

        # Continue to the next eligible packet. Dependent packets remain
        # gated until merge reconciliation promotes this task to DONE.
