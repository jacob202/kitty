"""CP-05 — bounded campaign report artifact.

Writes one markdown file per initiative to
``data/kittybuilder/reports/<initiative>-<ts>.md``: read-only, derived
entirely from Builder's own durable stores (queue DB rows, attempt
records, run manifests). Never reads ``.env`` or other runtime personal
data. Tails are capped and transcripts are pointed at by path, never
inlined, so the file stays safe to hand to a human without re-reading the
full attempt history.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.paths import KITTYBUILDER_DIR

REPORTS_DIR = KITTYBUILDER_DIR / "reports"

# Bounds — this is a report a human reads in one sitting, not a transcript.
VALIDATION_TAIL_CAP = 400
MAX_VALIDATION_COMMANDS_SHOWN = 10
MAX_CHANGED_PATHS_SHOWN = 30


def _attempt_dir(task_id: str, attempt_id: int, db_path: Path | None) -> Path:
    queue_db = Path(db_path) if db_path is not None else bq.BUILDER_QUEUE_DB
    return queue_db.parent / "attempts" / task_id / str(attempt_id)


def _latest_run_changed_paths(task_id: str, db_path: Path | None) -> list[str]:
    runs = bq.list_runs(task_id=task_id, db_path=db_path)
    if not runs:
        return []
    final_report = runs[-1].get("final_report") or {}
    return list(final_report.get("changed_paths") or [])


def _render_validation(attempt: dict[str, Any]) -> list[str]:
    validation = attempt.get("validation")
    if not validation:
        return ["  - validation: (not run)"]
    lines = [f"  - validation: **{validation.get('status', 'unknown')}**"]
    commands = validation.get("commands") or []
    truncated = len(commands) > MAX_VALIDATION_COMMANDS_SHOWN
    for cmd in commands[:MAX_VALIDATION_COMMANDS_SHOWN]:
        mark = "pass" if cmd.get("passed") else "FAIL"
        tail = (cmd.get("output_tail") or "")[-VALIDATION_TAIL_CAP:]
        lines.append(f"    - [{mark}] `{cmd.get('command')}` (exit {cmd.get('exit_code')})")
        if tail.strip():
            lines.append(f"      tail: `{tail.strip()[-VALIDATION_TAIL_CAP:]}`")
    if truncated:
        lines.append(f"    - ... {len(commands) - MAX_VALIDATION_COMMANDS_SHOWN} more command(s) not shown")
    return lines


def _render_packet(
    packet_id: str,
    evidence: dict[str, Any],
    stop_class_by_packet: dict[str, dict[str, Any]],
    db_path: Path | None,
) -> list[str]:
    task_id = evidence["task_id"]
    lines = [f"## {packet_id}", ""]
    lines.append(f"- state: `{evidence['current_state']}`")
    lines.append(
        f"- attempts: {evidence['attempts_used']}"
        + (
            f" / budget {evidence['attempt_budget']}"
            if evidence.get("attempt_budget") is not None
            else ""
        )
    )
    stop = stop_class_by_packet.get(packet_id)
    if stop:
        lines.append(f"- stop class: **{stop['stop_class']}** — {stop.get('reason', '-')}")

    attempts = ba.list_attempts(evidence["initiative_id"], packet_id, db_path=db_path)
    if attempts:
        last = attempts[-1]
        review = last.get("review")
        if review:
            lines.append(f"- latest review verdict: **{review.get('verdict')}** — {review.get('summary', '')}")
        lines.extend(_render_validation(last))
        manifest_path = _attempt_dir(task_id, last["id"], db_path) / "run-manifest.json"
        lines.append(f"- attempt manifest: `{manifest_path}` (pointer only, not inlined)")

    pr_links = bq.get_pr_links(task_id, db_path=db_path)
    if pr_links:
        for link in pr_links:
            lines.append(f"- PR: {link.get('pr_url', '-')} (head {link.get('head_sha', '-')[:12] if link.get('head_sha') else '-'})")

    changed = _latest_run_changed_paths(task_id, db_path)
    if changed:
        shown = changed[:MAX_CHANGED_PATHS_SHOWN]
        lines.append(f"- changed paths ({len(changed)}): " + ", ".join(f"`{p}`" for p in shown))
        if len(changed) > MAX_CHANGED_PATHS_SHOWN:
            lines.append(f"  ... {len(changed) - MAX_CHANGED_PATHS_SHOWN} more not shown")

    lines.append("")
    return lines


def _stop_class_by_packet(packets: list[dict[str, Any]], db_path: Path | None) -> dict[str, dict[str, Any]]:
    """Most recent stop_class decision per packet (CP-03 events, read-only)."""
    result: dict[str, dict[str, Any]] = {}
    for packet in packets:
        task_id = packet["task_id"]
        if bq.get_task(task_id, db_path=db_path) is None:
            continue
        for event in bq.list_events(task_id, db_path=db_path):
            payload = event.get("payload") or {}
            if event["type"] != "initiative_decision" or "stop_class" not in payload:
                continue
            result[packet["packet_id"]] = {
                "stop_class": payload["stop_class"],
                "reason": payload.get("stop_class_reason") or payload.get("reason"),
            }
    return result


def render_report(initiative_id: str, db_path: Path | None = None) -> str:
    """Build the report markdown for an initiative. Pure/read-only."""
    status = bi.initiative_status(initiative_id, db_path=db_path)
    packets = bi._read_packets_with_states(initiative_id, db_path=db_path)  # noqa: SLF001 — same module family, no public wrapper needed for a read-only rollup
    stop_classes = _stop_class_by_packet(packets, db_path)

    lines = [
        f"# Campaign report: {initiative_id}",
        "",
        f"- state: `{status['state']}`",
        f"- pause reason: {status.get('pause_reason') or '-'}",
        f"- packets: {status['total_packets']} "
        f"(done {len(status['done'])}, in-flight {len(status['in_progress'])}, "
        f"pending {len(status['pending'])}, exhausted {len(status['exhausted'])}, "
        f"failed {len(status['failed'])})",
    ]
    health = status.get("health") or {}
    if health:
        attempts = health.get("attempts_per_packet") or {}
        approval = health.get("first_pass_review_approval_rate")
        lines.append(
            f"- health: attempts avg={attempts.get('avg', '-')} max={attempts.get('max', '-')}, "
            f"first-pass approval={approval if approval is not None else '-'}, "
            f"stop classes: {health.get('stop_class_counts') or '-'}"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    for packet in packets:
        evidence = status["evidence"].get(packet["packet_id"], {})
        if not evidence:
            continue
        lines.extend(_render_packet(packet["packet_id"], evidence, stop_classes, db_path))

    return "\n".join(lines) + "\n"


def generate_report(
    initiative_id: str,
    *,
    db_path: Path | None = None,
    out_dir: Path | None = None,
    timestamp: str | None = None,
) -> Path:
    """Render and write the report file. Returns the written path.

    ``timestamp`` lets callers (tests) pin the filename; defaults to now.
    """
    if timestamp is None:
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    content = render_report(initiative_id, db_path=db_path)

    target_dir = out_dir if out_dir is not None else REPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{initiative_id}-{timestamp}.md"
    path.write_text(content, encoding="utf-8")
    return path
