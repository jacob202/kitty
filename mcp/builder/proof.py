"""Evidence-only KPROOF runner over the governed KittyBuilder MCP bridge."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from gateway.builder_status_readonly import (
    get_attempt_validation_index_readonly,
    get_initiative_readonly,
)
from gateway.paths import BUILDER_QUEUE_DB

from .operator import OperatorConfig, doctor_report
from .probe import call_tool_json, open_session

RUNTIME_MARKER = "KITTY_KPROOF_RUNTIME=1 "
TERMINAL_STATES = frozenset({"done", "failed", "blocked", "cancelled"})
INCOMPLETE_STATES = frozenset({"paused", "blocked", "needs_decision", "cancelled"})
STARTABLE_STATES = frozenset({"queued", "pending"})
ACTIVE_STATES = frozenset({"claimed", "running", "active", "launched"})


class ProofEvidenceError(RuntimeError):
    """Raised when approved or durable evidence is malformed/ambiguous."""


@dataclass(frozen=True)
class ProofConfig:
    mission_id: str
    endpoint: str
    repo_root: Path
    timeout_seconds: int = 3600
    poll_seconds: float = 2.0
    publication_required: bool = False


def _builder_db_path() -> Path:
    return BUILDER_QUEUE_DB


def _repo_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    if result.returncode != 0:
        raise ProofEvidenceError(f"cannot resolve v2 code SHA: {result.stderr.strip()}")
    return result.stdout.strip()


def runtime_marker_identity(manifest: dict[str, Any], packet_id: str) -> tuple[str, str]:
    packets = manifest.get("packets") or []
    packet = next(
        (item for item in packets if isinstance(item, dict) and item.get("id") == packet_id),
        None,
    )
    if packet is None:
        raise ProofEvidenceError(f"approved manifest has no packet {packet_id!r}")
    commands = packet.get("validation_commands") or []
    if not isinstance(commands, list):
        raise ProofEvidenceError("approved validation_commands must be a list")
    markers = [
        command
        for command in commands
        if isinstance(command, str) and command.startswith(RUNTIME_MARKER)
    ]
    if len(markers) != 1:
        raise ProofEvidenceError(
            f"approved packet must contain exactly one {RUNTIME_MARKER.strip()!r} validation command"
        )
    command = markers[0]
    return command, hashlib.sha256(command.encode("utf-8")).hexdigest()


def _operator_config(config: ProofConfig) -> OperatorConfig:
    parsed = urlparse(config.endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.port is None:
        raise ProofEvidenceError(f"invalid MCP endpoint: {config.endpoint!r}")
    return OperatorConfig(
        root=config.repo_root,
        host=parsed.hostname,
        port=parsed.port,
        pid_file=config.repo_root / "logs" / ".run" / "mcp.pid",
        log_file=config.repo_root / "logs" / "mcp.log",
    )


def _select_status_packet(status: dict[str, Any]) -> dict[str, Any] | None:
    work = status.get("work")
    if not isinstance(work, dict):
        return None
    if work.get("task_id"):
        return work
    packets = work.get("packets") or []
    next_packet = work.get("next_packet")
    if next_packet:
        for packet in packets:
            if isinstance(packet, dict) and packet.get("packet_id") == next_packet:
                return packet
    for packet in packets:
        if isinstance(packet, dict) and packet.get("task_state") != "done":
            return packet
    return packets[-1] if packets and isinstance(packets[-1], dict) else None


def _publication_identity(publication: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(publication, dict):
        return None
    number = publication.get("pr_number", publication.get("number"))
    head = publication.get("head_sha")
    if number is None and head is None:
        return None
    return {"pr_number": number, "head_sha": head}


def _continuity_check(
    expected: dict[str, Any],
    recovered: dict[str, Any],
    *,
    manifest_sha: str | None,
    task_id: str,
    attempt_id: int,
    publication: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not recovered.get("ok"):
        errors.append("fresh resume_context is not usable")
    mission = recovered.get("mission") or {}
    if mission.get("id") != expected.get("mission", {}).get("id"):
        errors.append("mission id changed")
    if mission.get("manifest_sha256") != manifest_sha:
        errors.append("manifest identity changed")
    for key in ("design", "plan"):
        if recovered.get("artifacts", {}).get(key) != expected.get("artifacts", {}).get(key):
            errors.append(f"{key} artifact identity changed")
        if not recovered.get("artifacts", {}).get(key):
            errors.append(f"{key} artifact identity is missing")
    if recovered.get("repository", {}).get("base_sha") != expected.get("repository", {}).get("base_sha"):
        errors.append("base SHA changed")
    current = recovered.get("current_work") or {}
    if current.get("task_id") != task_id:
        errors.append("task identity changed")
    if current.get("attempt_id") != attempt_id:
        errors.append("attempt identity changed")
    expected_publication = _publication_identity(publication)
    if expected_publication:
        recovered_publication = _publication_identity(recovered.get("pr"))
        if recovered_publication != expected_publication:
            errors.append("publication identity changed")
    if recovered.get("blocker") != expected.get("blocker"):
        errors.append("blocker changed")
    if recovered.get("unknowns") != expected.get("unknowns"):
        errors.append("unknown evidence changed")
    next_action = recovered.get("next_action")
    if not isinstance(next_action, str) or not next_action.strip():
        errors.append("fresh context has no next action")
    return not errors, errors


def _receipt_target(receipt: dict[str, Any], root: Path) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(receipt.get("mission_id") or "proof"))[:80]
    timestamp = str(receipt["finished_at"]).replace("-", "").replace(":", "")
    timestamp = timestamp.split(".", 1)[0].replace("+0000", "Z").replace("+00", "Z")
    return root / "data" / "kittybuilder" / "mcp-proof" / f"{safe_id}-{timestamp}.json"


def write_proof_receipt(receipt: dict[str, Any], *, root: Path) -> Path:
    target = _receipt_target(receipt, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    data = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    temp.write_text(data, encoding="utf-8")
    os.replace(temp, target)
    return target


def _base_receipt(config: ProofConfig) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operation": "mcp_proof",
        "mission_id": config.mission_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "v2_head_sha": _repo_head(config.repo_root),
        "manifest_sha256": None,
        "artifacts": {"design": None, "plan": None},
        "task_id": None,
        "attempt_id": None,
        "validation": None,
        "review": None,
        "runtime_marker": None,
        "publication": None,
        "continuity": {"session_count": 0, "passed": False, "errors": []},
        "blocker": None,
        "unknowns": [],
        "verdict": "incomplete",
        "ok": False,
        "next_action": "Inspect the incomplete proof evidence.",
    }


def _finish(
    receipt: dict[str, Any],
    config: ProofConfig,
    *,
    verdict: str,
    next_action: str,
    blocker: str | None = None,
) -> dict[str, Any]:
    receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
    receipt["verdict"] = verdict
    receipt["ok"] = verdict == "pass"
    receipt["next_action"] = next_action
    if blocker is not None:
        receipt["blocker"] = blocker
    target = _receipt_target(receipt, config.repo_root)
    receipt["receipt_path"] = str(target)
    write_proof_receipt(receipt, root=config.repo_root)
    return receipt


def _result_failure_kind(result: dict[str, Any]) -> tuple[str | None, str | None]:
    attempt = result.get("attempt") or {}
    review = attempt.get("review") or {}
    verdict = review.get("verdict")
    if verdict in {"reject", "request_changes"}:
        return "fail", f"independent review verdict is {verdict}"
    return None, None


async def run_proof(config: ProofConfig) -> dict[str, Any]:
    receipt = _base_receipt(config)
    try:
        doctor = await doctor_report(
            _operator_config(config),
            publication_required=config.publication_required,
        )
    except Exception as exc:
        return _finish(
            receipt,
            config,
            verdict="incomplete",
            blocker=f"doctor unavailable: {type(exc).__name__}: {exc}",
            next_action="Run 'kitty mcp doctor --json' and resolve the first boundary failure.",
        )
    if not doctor.get("ok"):
        failure = doctor.get("first_failure") or {}
        return _finish(
            receipt,
            config,
            verdict="incomplete",
            blocker=failure.get("summary") or "MCP doctor has a blocking failure.",
            next_action=doctor.get("next_action") or "Resolve the MCP doctor failure.",
        )

    try:
        initiative = get_initiative_readonly(config.mission_id, db_path=_builder_db_path())
    except Exception as exc:
        return _finish(
            receipt,
            config,
            verdict="incomplete",
            blocker=f"approved Mission cannot be read: {type(exc).__name__}: {exc}",
            next_action="Confirm the Mission was explicitly approved into KittyBuilder.",
        )
    if initiative is None:
        return _finish(
            receipt,
            config,
            verdict="incomplete",
            blocker="Mission is not present in durable Builder state.",
            next_action="Prepare and explicitly approve the exact Mission before running proof.",
        )
    manifest = initiative.get("manifest") or {}
    manifest_sha = initiative.get("manifest_sha256")
    receipt["manifest_sha256"] = manifest_sha

    final_resume_1: dict[str, Any] | None = None
    result_payload: dict[str, Any] | None = None
    task_id: str | None = None
    packet_id: str | None = None
    attempt_id: int | None = None
    publication: dict[str, Any] | None = None

    async with open_session(config.endpoint) as session1:
        initial = await call_tool_json(
            session1, "resume_context", {"mission_id": config.mission_id}
        )
        if not initial.get("ok"):
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker=initial.get("error") or "resume_context requires attention.",
                next_action=initial.get("next_action") or "Resolve continuity attention before proof.",
            )
        if (initial.get("mission") or {}).get("id") != config.mission_id:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="MCP resume_context resolved a different Mission.",
                next_action="Resolve Mission identity before executing proof.",
            )
        if (initial.get("mission") or {}).get("manifest_sha256") != manifest_sha:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="MCP Mission digest does not match durable approved manifest.",
                next_action="Reconcile the approved Mission identity before execution.",
            )
        receipt["artifacts"] = initial.get("artifacts") or receipt["artifacts"]
        receipt["unknowns"] = list(initial.get("unknowns") or [])

        status = await call_tool_json(
            session1, "work_status", {"mission_id": config.mission_id}
        )
        if not status.get("ok"):
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker=status.get("error") or "Builder work status is unavailable.",
                next_action=status.get("next_action") or "Inspect Builder work status.",
            )
        packet = _select_status_packet(status)
        current = initial.get("current_work") or {}
        task_id = (packet or {}).get("task_id") or current.get("task_id")
        packet_id = (packet or {}).get("packet_id") or current.get("packet_id")
        state = (packet or {}).get("task_state") or status.get("state")
        receipt["task_id"] = task_id

        if state in INCOMPLETE_STATES:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker=f"Builder work is {state}.",
                next_action=(packet or {}).get("blocked_reason")
                or status.get("next_action")
                or "Resolve the Builder decision/blocker before rerunning proof.",
            )

        if state in STARTABLE_STATES:
            started = await call_tool_json(
                session1,
                "execution_start",
                {
                    "mission_id": config.mission_id,
                    "free": True,
                    "spend_authorized": False,
                },
            )
            if not started.get("ok"):
                return _finish(
                    receipt,
                    config,
                    verdict="incomplete",
                    blocker=started.get("error") or "Free Builder execution could not start.",
                    next_action=started.get("next_action") or "Resolve free execution readiness.",
                )
            state = started.get("state") or "running"

        deadline = time.monotonic() + max(0, config.timeout_seconds)
        while state not in TERMINAL_STATES:
            if state not in ACTIVE_STATES and state not in STARTABLE_STATES:
                return _finish(
                    receipt,
                    config,
                    verdict="incomplete",
                    blocker=f"Builder entered unsupported proof state {state!r}.",
                    next_action="Inspect work_status and resolve the Builder state.",
                )
            if time.monotonic() >= deadline:
                return _finish(
                    receipt,
                    config,
                    verdict="incomplete",
                    blocker="Proof timed out while Builder work was still active.",
                    next_action="Inspect work_status; rerun proof after Builder reaches a durable terminal state.",
                )
            await asyncio.sleep(max(0.0, config.poll_seconds))
            args = {"task_id": task_id} if task_id else {"mission_id": config.mission_id}
            status = await call_tool_json(session1, "work_status", args)
            if not status.get("ok"):
                return _finish(
                    receipt,
                    config,
                    verdict="incomplete",
                    blocker=status.get("error") or "Builder work status became unavailable.",
                    next_action="Restore Builder status visibility and rerun proof.",
                )
            packet = _select_status_packet(status)
            task_id = (packet or {}).get("task_id") or task_id
            packet_id = (packet or {}).get("packet_id") or packet_id
            state = (packet or {}).get("task_state") or status.get("state")
            receipt["task_id"] = task_id

        if state in {"blocked", "cancelled"}:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker=f"Builder work ended {state}.",
                next_action=(packet or {}).get("blocked_reason") or "Resolve the Builder blocker/decision before rerunning proof.",
            )

        result_args = {"task_id": task_id} if task_id else {"mission_id": config.mission_id}
        work_result = await call_tool_json(session1, "work_result", result_args)
        if not work_result.get("ok"):
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker=work_result.get("error") or "Builder result evidence is unavailable.",
                next_action=work_result.get("next_action") or "Inspect Builder result evidence.",
            )
        result_payload = work_result.get("result") or {}
        task_id = result_payload.get("task_id") or task_id
        packet_id = result_payload.get("packet_id") or packet_id
        receipt["task_id"] = task_id
        attempt = result_payload.get("attempt") or {}
        raw_attempt_id = attempt.get("id")
        attempt_id = int(raw_attempt_id) if isinstance(raw_attempt_id, int) else None
        receipt["attempt_id"] = attempt_id
        publication = result_payload.get("publication")

        try:
            _runtime_command, runtime_digest = runtime_marker_identity(manifest, str(packet_id))
        except ProofEvidenceError as exc:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker=str(exc),
                next_action="Prepare/approve a Mission with exactly one runtime-marked validation command.",
            )
        receipt["runtime_marker"] = {"command_sha256": runtime_digest, "passed": False}

        if attempt_id is None:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="Durable result has no attempt identity.",
                next_action="Wait for Builder to record an attempt and deterministic validation evidence.",
            )
        try:
            validation = get_attempt_validation_index_readonly(
                attempt_id, db_path=_builder_db_path()
            )
        except Exception as exc:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker=f"Validation evidence cannot be read safely: {type(exc).__name__}: {exc}",
                next_action="Restore read-only Builder validation evidence and rerun proof.",
            )
        receipt["validation"] = validation
        if not validation:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="Deterministic validation evidence is missing.",
                next_action="Let Builder run its approved deterministic validation commands.",
            )
        if validation.get("validation_status") == "failed":
            return _finish(
                receipt,
                config,
                verdict="fail",
                blocker="Deterministic Builder validation failed.",
                next_action="Let Builder repair the failed validation through its normal attempt loop.",
            )
        if validation.get("validation_status") != "passed":
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="Deterministic validation has not reached passed state.",
                next_action="Wait for Builder deterministic validation to complete.",
            )
        runtime_matches = [
            item
            for item in validation.get("commands") or []
            if item.get("command_sha256") == runtime_digest
        ]
        if len(runtime_matches) != 1:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="Runtime-marked command cannot be matched uniquely to durable validation evidence.",
                next_action="Re-run the exact approved validation contract through Builder.",
            )
        receipt["runtime_marker"]["passed"] = bool(runtime_matches[0].get("passed"))
        if not receipt["runtime_marker"]["passed"]:
            return _finish(
                receipt,
                config,
                verdict="fail",
                blocker="The runtime-marked product journey failed.",
                next_action="Let Builder repair the product behavior and rerun deterministic validation.",
            )

        review = attempt.get("review")
        receipt["review"] = review
        review_verdict = (review or {}).get("verdict")
        if review_verdict in {"reject", "request_changes"}:
            return _finish(
                receipt,
                config,
                verdict="fail",
                blocker=f"Independent review verdict is {review_verdict}.",
                next_action="Let Builder repair the review findings through its normal attempt loop.",
            )
        if review_verdict not in {"approve", "approved"}:
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="Required independent review evidence is missing.",
                next_action="Wait for Builder to record independent review evidence.",
            )
        if not result_payload.get("complete"):
            kind, reason = _result_failure_kind(result_payload)
            return _finish(
                receipt,
                config,
                verdict=kind or "incomplete",
                blocker=reason or "Builder result is not complete.",
                next_action="Let Builder reach durable completion before rerunning proof.",
            )

        if config.publication_required:
            pub_status = await call_tool_json(
                session1, "publication_status", {"task_id": task_id}
            )
            if not pub_status.get("ok"):
                return _finish(
                    receipt,
                    config,
                    verdict="incomplete",
                    blocker=pub_status.get("error") or "Publication evidence is unavailable.",
                    next_action="Resolve GitHub publication readiness; proof will not publish automatically.",
                )
            publication = pub_status.get("publication") or publication
            publication_identity = _publication_identity(publication)
            if not publication_identity or not publication_identity.get("pr_number"):
                return _finish(
                    receipt,
                    config,
                    verdict="incomplete",
                    blocker="Required PR publication evidence is missing.",
                    next_action="Explicitly authorize publication through the existing publication gate, then rerun proof.",
                )
        receipt["publication"] = _publication_identity(publication)

        final_resume_1 = await call_tool_json(
            session1, "resume_context", {"mission_id": config.mission_id}
        )
        if not final_resume_1.get("ok"):
            return _finish(
                receipt,
                config,
                verdict="incomplete",
                blocker="Final session-1 continuity receipt is not usable.",
                next_action=final_resume_1.get("next_action") or "Resolve continuity attention before fresh-session proof.",
            )

    receipt["continuity"]["session_count"] = 1
    async with open_session(config.endpoint) as session2:
        recovered = await call_tool_json(
            session2, "resume_context", {"mission_id": config.mission_id}
        )
    receipt["continuity"]["session_count"] = 2
    assert final_resume_1 is not None and task_id is not None and attempt_id is not None
    continuity_ok, continuity_errors = _continuity_check(
        final_resume_1,
        recovered,
        manifest_sha=manifest_sha,
        task_id=task_id,
        attempt_id=attempt_id,
        publication=publication,
    )
    receipt["continuity"]["passed"] = continuity_ok
    receipt["continuity"]["errors"] = continuity_errors
    receipt["unknowns"] = list(recovered.get("unknowns") or [])
    receipt["blocker"] = recovered.get("blocker")
    if not continuity_ok:
        return _finish(
            receipt,
            config,
            verdict="incomplete",
            blocker="Fresh-session continuity identities did not match durable truth.",
            next_action="Resolve the continuity mismatch and rerun proof from a new session.",
        )

    return _finish(
        receipt,
        config,
        verdict="pass",
        blocker=None,
        next_action=recovered.get("next_action") or "Review the verified KPROOF result.",
    )


async def proof_report(
    operator_config: OperatorConfig,
    *,
    mission_id: str,
    timeout_seconds: int = 3600,
    poll_seconds: float = 2.0,
    publication_required: bool = False,
) -> dict[str, Any]:
    return await run_proof(
        ProofConfig(
            mission_id=mission_id,
            endpoint=operator_config.endpoint,
            repo_root=operator_config.root,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            publication_required=publication_required,
        )
    )
