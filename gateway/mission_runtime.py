"""Mission wake/review adapter over existing Automation and free DSH seams."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from gateway import (
    artifact_store,
    automation_actions,
    automation_runs,
    builder_loop,
    builder_queue,
    builder_status_readonly,
    doctor,
    memory_mission,
)
from gateway import builder_initiative as bi
from gateway.paths import DATA_DIR
from mcp.builder import repo_tools

ACTION_NAME = "mission.review_pending"
_REVIEW_TIMEOUT_SECONDS = 240
_LOCAL_ACCEPTANCE_REVIEWER_ID = "local:r3-running-product-operator"
_RESULT_CANDIDATE_ACTIVE_STATUSES = ("EXECUTING", "VERIFYING", "REPAIRING")
REQUIRED_RUNNING_STATES = ("desktop", "iphone_class", "happy", "degraded", "reload", "recovery")
logger = logging.getLogger("kitty.mission_runtime")


def _parse_review_json(raw: str) -> Any:
    """Parse one reviewer contract despite harmless model framing text.

    Free routes occasionally wrap an otherwise valid final JSON object in a
    sentence even when told not to. Accept one unambiguous object, but reject
    multiple JSON objects so contradictory verdicts can never be guessed at.
    """
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        last_fence = text.rfind("```")
        if first_newline >= 0 and last_fence > first_newline:
            text = text[first_newline + 1:last_fence].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as original:
        start = text.find("{")
        if start < 0:
            raise
        try:
            value, consumed = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            raise original
        prefix = text[:start].strip()
        suffix = text[start + consumed:].strip()
        if "{" in prefix or "}" in prefix or "{" in suffix or "}" in suffix:
            raise original
        return value


class PlanVerifierUnavailable(RuntimeError):
    """No trustworthy zero-cost independent plan verifier is available."""


class ResultCandidateUnavailable(RuntimeError):
    """The exact reviewed Builder result cannot be bound as a Mission candidate."""


def register_action() -> None:
    """Register Mission review through the existing Automation action registry."""
    automation_actions.register_action(
        ACTION_NAME,
        review_pending_action,
        policy=automation_actions.ActionPolicy(capability="mission.plan.review", tier="T0"),
    )


def _pending_missions() -> list[dict[str, Any]]:
    return [
        mission
        for mission in memory_mission.list_missions(db_path=memory_mission.MISSION_DB_FILE)
        if mission["status"] == "PLAN_REVIEW"
        and mission["plan"]["review_state"] == "unreviewed"
    ]


async def review_pending_action(payload: dict[str, Any]) -> automation_actions.ActionResult:
    """Review one requested or the oldest pending Mission without owning a scheduler."""
    requested = payload.get("mission_id")
    if requested is not None:
        if not isinstance(requested, str) or not requested.strip():
            raise ValueError("mission_id must be a non-empty string")
        candidates = [memory_mission.get_mission(requested, db_path=memory_mission.MISSION_DB_FILE)]
    else:
        candidates = list(reversed(_pending_missions()))

    reviewed: dict[str, Any] | None = None
    for mission in candidates:
        if mission["status"] != "PLAN_REVIEW" or mission["plan"]["review_state"] != "unreviewed":
            continue
        reviewed = await asyncio.to_thread(review_plan, mission["mission_id"])
        break

    if reviewed is None:
        raise automation_actions.ConditionFalse("no unreviewed Mission plan is pending")
    return automation_actions.ActionResult(
        status="completed", result_pointer=f"mission://{reviewed['mission_id']}"
    )


async def request_plan_review(mission_id: str) -> dict[str, Any]:
    """Dispatch one exact plan review through durable Automation authority.

    A live run for this Mission is reused rather than spawning another model
    invocation. Terminal outages are intentionally retriable: the next proposal
    replay or Gateway startup may create a fresh Automation run.
    """
    mission = memory_mission.get_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
    if mission["status"] != "PLAN_REVIEW" or mission["plan"]["review_state"] != "unreviewed":
        return {"status": "not_pending", "mission_id": mission_id}
    automation_id = f"mission-plan-review:{mission_id}"
    if automation_actions.get_definition(ACTION_NAME) is None:
        register_action()
    payload = {"mission_id": mission_id}
    run, created = automation_runs.claim_running_run(
        automation_id=automation_id,
        action=ACTION_NAME,
        trigger_kind="signal",
        trigger_ref=mission["plan"]["digest"],
        payload=payload,
    )
    if not created:
        return run
    return await automation_actions.run_action(
        ACTION_NAME,
        trigger_kind="signal",
        automation_id=automation_id,
        trigger_ref=mission["plan"]["digest"],
        payload=run.get("payload") or payload,
        run_id=run["id"],
    )


async def request_pending_reviews() -> list[dict[str, Any]]:
    """Restart recovery for plan review and finished Builder result binding."""
    automation_runs.reconcile_interrupted_runs()
    receipts: list[dict[str, Any]] = []
    missions = memory_mission.list_missions(db_path=memory_mission.MISSION_DB_FILE)
    for mission in reversed(missions):
        if mission["status"] == "PLAN_REVIEW" and mission["plan"]["review_state"] == "unreviewed":
            receipts.append(await request_plan_review(mission["mission_id"]))
            continue
        locator = mission.get("builder_locator") or {}
        if mission["status"] in {"EXECUTING", "VERIFYING", "REPAIRING"} and locator.get("task_id"):
            receipt = reconcile_result_candidate_background(mission["mission_id"])
            if receipt.get("status") != "not_pending":
                receipts.append(receipt)
    return receipts


def _hex_digest(value: Any, length: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if len(normalized) != length or any(ch not in "0123456789abcdef" for ch in normalized):
        return None
    return normalized


def _candidate_provenance_digest(candidate: dict[str, str]) -> str:
    """Bind acceptance to the exact artifact and reviewed source revision."""
    payload = {
        "artifact_id": candidate["artifact_id"],
        "content_hash": candidate["content_hash"],
        "base_sha": candidate["base_sha"],
        "review_sha": candidate["review_sha"],
        "diff_sha256": candidate["diff_sha256"],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reviewed_builder_result(mission: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve and re-hash the exact independently reviewed Builder result artifact."""
    locator = mission.get("builder_locator") or {}
    initiative_id = locator.get("initiative_id")
    task_id = locator.get("task_id")
    if not all(isinstance(value, str) and value for value in (initiative_id, task_id)):
        raise ResultCandidateUnavailable("Mission has no complete Builder task binding")
    try:
        snapshot = builder_status_readonly.build_status_snapshot_readonly(
            db_path=builder_queue.BUILDER_QUEUE_DB
        )
    except Exception as exc:
        raise ResultCandidateUnavailable(f"Builder result store is unavailable: {exc}") from exc
    initiative = next(
        (item for item in snapshot.get("initiatives", []) if item.get("initiative_id") == initiative_id),
        None,
    )
    packet = next(
        (item for item in (initiative or {}).get("packets", []) if item.get("task_id") == task_id),
        None,
    )
    if packet is None:
        raise ResultCandidateUnavailable("bound Builder task is unavailable")
    task_state = packet.get("task_state")
    result_lifecycle_states = {
        builder_queue.BLOCKED,
        builder_queue.PR_OPENED,
        builder_queue.AWAITING_REVIEW,
        builder_queue.DONE,
    }
    if task_state not in result_lifecycle_states:
        return None

    # The reusable result must belong to the current attempt. A prior approved
    # artifact is stale once a newer repair/retry attempt exists, even if the
    # task happens to be blocked again.
    history = packet.get("attempt_history", [])
    attempt = history[0] if isinstance(history, list) and history else None
    reviewed_ready = (
        isinstance(attempt, dict)
        and attempt.get("outcome") == "succeeded"
        and attempt.get("review_verdict") == "approve"
        and isinstance(attempt.get("result_artifact"), dict)
        and attempt["result_artifact"].get("state") == "ready"
    )
    if not reviewed_ready:
        if task_state == builder_queue.DONE:
            raise ResultCandidateUnavailable(
                "completed Builder task has no independently reviewed ready result artifact"
            )
        return None
    artifact_id = attempt["result_artifact"].get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise ResultCandidateUnavailable("Builder result artifact identity is unavailable")
    try:
        artifact = artifact_store.get_artifact(artifact_id)
    except Exception as exc:
        raise ResultCandidateUnavailable(f"Builder result artifact is unavailable: {exc}") from exc
    if artifact is None or artifact.get("state") != "ready" or artifact.get("kind") != "builder_result":
        raise ResultCandidateUnavailable("Builder result artifact is not ready")
    metadata = artifact.get("metadata")
    if not isinstance(metadata, dict):
        raise ResultCandidateUnavailable("Builder result artifact metadata is malformed")
    for key, expected in {
        "initiative_id": initiative_id,
        "task_id": task_id,
        "attempt_id": attempt.get("id"),
    }.items():
        if metadata.get(key) != expected:
            raise ResultCandidateUnavailable(
                f"Builder result artifact {key} does not match the reviewed attempt"
            )
    content_hash = _hex_digest(artifact.get("content_hash"), 64)
    base_sha = _hex_digest(metadata.get("base_sha"), 40)
    review_sha = _hex_digest(metadata.get("review_sha"), 40)
    diff_sha256 = _hex_digest(metadata.get("diff_sha256"), 64)
    if (
        content_hash is None
        or base_sha is None
        or review_sha is None
        or diff_sha256 is None
    ):
        raise ResultCandidateUnavailable("Builder result artifact is missing review provenance")
    path = Path(str(artifact.get("storage_uri") or ""))
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ResultCandidateUnavailable(f"Builder result artifact cannot be read: {exc}") from exc
    if hashlib.sha256(content).hexdigest() != content_hash or len(content) != artifact.get("size_bytes"):
        raise ResultCandidateUnavailable("Builder result artifact no longer matches its registered digest")
    if metadata.get("result_patch_sha256") != content_hash or metadata.get("result_patch_size_bytes") != len(content):
        raise ResultCandidateUnavailable("Builder result artifact manifest does not match its content")
    candidate: dict[str, str] = {
        "artifact_id": artifact_id,
        "content_hash": content_hash,
        "base_sha": base_sha,
        "review_sha": review_sha,
        "diff_sha256": diff_sha256,
    }
    return {**candidate, "candidate_digest": _candidate_provenance_digest(candidate)}


def reconcile_result_candidate(mission_id: str) -> dict[str, Any]:
    """Bind finished reviewed Builder work as the exact Mission candidate, never acceptance."""
    mission = memory_mission.get_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
    if mission["status"] not in _RESULT_CANDIDATE_ACTIVE_STATUSES:
        return {"status": "not_pending", "mission_id": mission_id}
    candidate = _reviewed_builder_result(mission)
    if candidate is None:
        return {"status": "not_pending", "mission_id": mission_id}
    candidate_ref = f"artifact:{candidate['artifact_id']}"
    candidate_digest = candidate.get("candidate_digest") or candidate["content_hash"]
    current = mission.get("candidate") or {}
    if current.get("ref") == candidate_ref and current.get("digest") == candidate_digest:
        return {"status": "already_bound", "mission_id": mission_id, "candidate": current}
    try:
        mission = memory_mission.record_candidate(
            mission_id,
            candidate_ref=candidate_ref,
            candidate_digest=candidate_digest,
            expected_statuses=_RESULT_CANDIDATE_ACTIVE_STATUSES,
            db_path=memory_mission.MISSION_DB_FILE,
        )
    except memory_mission.MissionError:
        latest = memory_mission.get_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
        if latest["status"] not in _RESULT_CANDIDATE_ACTIVE_STATUSES:
            return {"status": "not_pending", "mission_id": mission_id}
        raise
    return {
        "status": "candidate_bound",
        "mission_id": mission_id,
        "candidate": mission["candidate"],
        "acceptance_state": mission["acceptance"]["state"],
    }


def reconcile_result_candidate_background(mission_id: str) -> dict[str, Any]:
    """Reconcile from a background task without losing the reason it failed.

    A background task's return value and exception both go nowhere. The caller
    has already been answered, so the only honest place to leave the cause is on
    the Mission itself, where the next status read can say it out loud.
    """
    try:
        return reconcile_result_candidate(mission_id)
    except ResultCandidateUnavailable as exc:
        logger.error("Mission %s result reconciliation unavailable: %s", mission_id, exc)
        try:
            memory_mission.record_candidate_unavailable(
                mission_id, reason=str(exc), db_path=memory_mission.MISSION_DB_FILE
            )
        except memory_mission.MissionError:
            logger.exception("Mission %s could not record its reconciliation failure", mission_id)
        return {"status": "source_unavailable", "mission_id": mission_id, "error": str(exc)}


def _validated_running_product_evidence(evidence: dict[str, Any], *, verdict: str) -> dict[str, Any]:
    if not isinstance(evidence, dict) or not evidence:
        raise memory_mission.MissionError("running-product acceptance evidence must be a non-empty object")
    steps = evidence.get("steps")
    if not isinstance(steps, list) or not steps or not all(isinstance(step, str) and step.strip() for step in steps):
        raise memory_mission.MissionError("running-product evidence requires non-empty steps")
    normalized = dict(evidence)
    for key in REQUIRED_RUNNING_STATES:
        state = evidence.get(key)
        if not isinstance(state, dict):
            raise memory_mission.MissionError(f"running-product evidence requires {key} state")
        status_value = state.get("state")
        evidence_ref = state.get("evidence")
        if status_value not in {"passed", "failed", "unverified"}:
            raise memory_mission.MissionError(f"running-product evidence has invalid {key} state")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            raise memory_mission.MissionError(f"running-product evidence requires {key} evidence")
    unmet_gates = evidence.get("unmet_gates")
    if not isinstance(unmet_gates, list) or not all(isinstance(item, str) and item.strip() for item in unmet_gates):
        raise memory_mission.MissionError("running-product evidence requires an unmet_gates list")
    if verdict == "accepted":
        if unmet_gates:
            raise memory_mission.MissionError("accepted running-product evidence cannot contain unmet gates")
        failed = [
            key for key in REQUIRED_RUNNING_STATES
            if evidence[key]["state"] != "passed"
        ]
        if failed:
            raise memory_mission.MissionError(
                "accepted running-product evidence has unpassed states: " + ", ".join(failed)
            )
    return normalized


def _runtime_port(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise ResultCandidateUnavailable(f"invalid {name}: {raw!r}") from exc
    if not 1 <= port <= 65535:
        raise ResultCandidateUnavailable(f"invalid {name}: {port}")
    return port


def _gateway_runtime_manifest(*, port: int) -> dict[str, Any]:
    secret = os.environ.get("GATEWAY_SECRET", "").strip()
    if not secret:
        raise ResultCandidateUnavailable("GATEWAY_SECRET is unavailable for runtime identity probe")
    try:
        response = httpx.get(
            f"http://127.0.0.1:{port}/runtime/manifest",
            headers={"Authorization": f"Bearer {secret}"},
            timeout=3.0,
        )
    except httpx.HTTPError as exc:
        raise ResultCandidateUnavailable(f"Gateway runtime manifest probe failed: {exc}") from exc
    if response.status_code != 200:
        raise ResultCandidateUnavailable(
            f"Gateway runtime manifest probe returned HTTP {response.status_code}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ResultCandidateUnavailable("Gateway runtime manifest returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ResultCandidateUnavailable("Gateway runtime manifest is malformed")
    return payload


def _running_product_runtime_identity(expected_review_sha: str) -> dict[str, Any]:
    """Prove the actual Gateway/UI listeners are serving the reviewed candidate."""
    gateway_port = _runtime_port("GATEWAY_PORT", 8000)
    ui_port = _runtime_port("UI_PORT", 4000)

    process = doctor._gateway_process_info(port=gateway_port)
    if process.get("state") != "running":
        raise ResultCandidateUnavailable(
            "Gateway runtime identity is unavailable: "
            + str(process.get("error") or process.get("state"))
        )

    manifest = _gateway_runtime_manifest(port=gateway_port)
    context = manifest.get("context")
    if not isinstance(context, dict):
        raise ResultCandidateUnavailable("Gateway runtime context is malformed")
    repository = context.get("repository")
    if not isinstance(repository, dict) or repository.get("state") != "available":
        raise ResultCandidateUnavailable("Gateway runtime repository identity is unavailable")
    repo_value = repository.get("value")
    if not isinstance(repo_value, dict):
        raise ResultCandidateUnavailable("Gateway runtime repository identity is malformed")
    runtime_root_raw = repo_value.get("root")
    running_sha = repo_value.get("commit")
    if not isinstance(runtime_root_raw, str) or not runtime_root_raw.strip():
        raise ResultCandidateUnavailable("Gateway runtime root is unavailable")
    runtime_root = Path(runtime_root_raw).resolve()
    if running_sha != expected_review_sha:
        raise ResultCandidateUnavailable(
            f"Gateway is serving {running_sha!r}, expected reviewed SHA {expected_review_sha}"
        )
    if repo_value.get("dirty") is not False:
        raise ResultCandidateUnavailable("Gateway runtime checkout is not clean")

    cwd_raw = process.get("cwd")
    if not isinstance(cwd_raw, str) or not cwd_raw.strip():
        raise ResultCandidateUnavailable("Gateway listener cwd is unavailable")
    cwd = Path(cwd_raw).resolve()
    if cwd != runtime_root and runtime_root not in cwd.parents:
        raise ResultCandidateUnavailable("Gateway listener cwd does not belong to runtime checkout")

    storage = manifest.get("storage")
    if not isinstance(storage, dict):
        raise ResultCandidateUnavailable("Gateway runtime storage identity is malformed")
    data_root_fact = storage.get("data_root")
    if not isinstance(data_root_fact, dict) or data_root_fact.get("state") != "available":
        raise ResultCandidateUnavailable("Gateway runtime data-root identity is unavailable")
    runtime_data_root_raw = data_root_fact.get("value")
    if not isinstance(runtime_data_root_raw, str) or not runtime_data_root_raw.strip():
        raise ResultCandidateUnavailable("Gateway runtime data-root identity is malformed")
    runtime_data_root = Path(runtime_data_root_raw).resolve()
    expected_data_root = DATA_DIR.resolve()
    if runtime_data_root != expected_data_root:
        raise ResultCandidateUnavailable(
            f"Gateway data root {runtime_data_root} does not match operator data root {expected_data_root}"
        )

    ui = doctor._ui_runtime_provenance(port=ui_port)
    if ui.get("state") != "checkout-current":
        raise ResultCandidateUnavailable(
            "UI runtime identity is unavailable or stale: " + str(ui.get("state"))
        )
    if ui.get("build_source") != expected_review_sha or ui.get("source_sha") != expected_review_sha:
        raise ResultCandidateUnavailable("UI is not serving the reviewed candidate SHA")
    if ui.get("source_state") != "clean":
        raise ResultCandidateUnavailable("UI runtime checkout is not clean")
    ui_root_raw = ui.get("runtime_root")
    if not isinstance(ui_root_raw, str) or Path(ui_root_raw).resolve() != runtime_root:
        raise ResultCandidateUnavailable("Gateway and UI are not serving the same runtime checkout")

    return {
        "gateway": {
            "pid": process.get("pid"),
            "cwd": str(cwd),
            "root": str(runtime_root),
            "commit": running_sha,
            "manifest_revision": manifest.get("revision"),
        },
        "ui": {
            "pid": ui.get("runtime_pid"),
            "root": str(runtime_root),
            "build_id": ui.get("build_id"),
            "commit": ui.get("build_source"),
        },
        "data_root": str(runtime_data_root),
    }


def acceptance_readiness(mission: dict[str, Any]) -> dict[str, Any]:
    """Can this Mission be accepted right now, and if not, exactly what is missing.

    Asserts nothing and changes nothing — it runs the same provenance and runtime
    identity checks acceptance runs, and reports the first one that fails. That
    keeps the operator's "why not" answer and the acceptance gate itself from
    drifting apart.
    """
    candidate = mission.get("candidate") or {}
    report: dict[str, Any] = {
        "mission_id": mission["mission_id"],
        "objective": mission["objective"],
        "status": mission["status"],
        "candidate_ref": candidate.get("ref"),
        "candidate_digest": candidate.get("digest"),
        "ready": False,
        "blocker": None,
        "review_sha": None,
    }
    if not candidate.get("ref") or not candidate.get("digest"):
        report["blocker"] = (
            candidate.get("error") or "no reviewed Builder result is bound to this job yet"
        )
        return report
    try:
        reviewed = _reviewed_builder_result(mission)
    except ResultCandidateUnavailable as exc:
        report["blocker"] = str(exc)
        return report
    if reviewed is None:
        report["blocker"] = "the Builder task bound to this job has not finished"
        return report
    report["review_sha"] = reviewed["review_sha"]
    reviewed_ref = f"artifact:{reviewed['artifact_id']}"
    reviewed_digest = reviewed.get("candidate_digest") or reviewed["content_hash"]
    if (
        reviewed_ref != candidate.get("ref")
        or reviewed_digest != candidate.get("digest")
    ):
        report["blocker"] = "the bound candidate does not match the reviewed Builder result"
        return report
    try:
        _running_product_runtime_identity(reviewed["review_sha"])
    except ResultCandidateUnavailable as exc:
        report["blocker"] = str(exc)
        return report
    report["ready"] = True
    return report


def record_running_product_acceptance(
    mission_id: str,
    *,
    candidate_ref: str,
    candidate_digest: str,
    verdict: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Trusted local-operator boundary for exact running-product acceptance.

    This is deliberately not exposed as normal Gateway HTTP authority. Reviewer
    identity, runtime checkout identity, data-root identity, and artifact
    provenance are derived here rather than accepted from a product client.
    """
    if verdict not in {"accepted", "rejected"}:
        raise memory_mission.MissionError("acceptance verdict must be accepted or rejected")
    mission = memory_mission.get_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
    current = mission.get("candidate") or {}
    if current.get("ref") != candidate_ref or current.get("digest") != candidate_digest:
        raise memory_mission.MissionError("stale candidate reference or digest")
    reviewed = _reviewed_builder_result(mission)
    if reviewed is None:
        raise ResultCandidateUnavailable("bound Builder result is not complete")
    reviewed_ref = f"artifact:{reviewed['artifact_id']}"
    reviewed_digest = reviewed.get("candidate_digest") or reviewed["content_hash"]
    if reviewed_ref != candidate_ref or reviewed_digest != candidate_digest:
        raise memory_mission.MissionError("acceptance candidate does not match reviewed Builder provenance")
    validated = _validated_running_product_evidence(evidence, verdict=verdict)
    runtime_identity = _running_product_runtime_identity(reviewed["review_sha"])
    validated.update(
        {
            "candidate_ref": candidate_ref,
            "candidate_digest": candidate_digest,
            "running_sha": runtime_identity["gateway"]["commit"],
            "data_root": runtime_identity["data_root"],
            "runtime_identity": runtime_identity,
            "artifact_provenance": {
                "artifact_id": reviewed["artifact_id"],
                "content_hash": reviewed["content_hash"],
                "base_sha": reviewed["base_sha"],
                "review_sha": reviewed["review_sha"],
                "diff_sha256": reviewed["diff_sha256"],
            },
        }
    )
    return memory_mission.record_acceptance(
        mission_id,
        reviewer_id=_LOCAL_ACCEPTANCE_REVIEWER_ID,
        candidate_digest=candidate_digest,
        verdict=verdict,
        evidence=validated,
        db_path=memory_mission.MISSION_DB_FILE,
    )


def review_plan(mission_id: str) -> dict[str, Any]:
    """Run one independent verifier and bind its verdict to the exact plan digest."""
    mission = memory_mission.get_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
    if mission["status"] != "PLAN_REVIEW" or mission["plan"]["review_state"] != "unreviewed":
        return mission

    try:
        result = run_plan_verifier(mission)
    except PlanVerifierUnavailable as exc:
        raise automation_actions.SourceUnavailable(str(exc)) from exc

    verdict = result.get("verdict")
    if verdict not in {"approve", "reject"}:
        raise PlanVerifierUnavailable("plan verifier returned no valid verdict")
    reviewer_id = result.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise PlanVerifierUnavailable("plan verifier returned no reviewer identity")
    evidence = {
        "plan_ref": mission["plan"]["ref"],
        "plan_digest": mission["plan"]["digest"],
        "provider": result.get("provider"),
        "model": result.get("model"),
        "review_head": result.get("review_head"),
        "review_origin_main": result.get("review_origin_main"),
        "route_probes": result.get("route_probes") or [],
        "summary": result.get("summary"),
        "findings": result.get("findings") or [],
    }
    return memory_mission.record_plan_review(
        mission_id,
        reviewer_id=reviewer_id,
        plan_digest=mission["plan"]["digest"],
        verdict="approved" if verdict == "approve" else "rejected",
        evidence=evidence,
        db_path=memory_mission.MISSION_DB_FILE,
    )


def _plan_review_prompt(mission: dict[str, Any]) -> str:
    payload = mission["plan"].get("payload") or {}
    plan_ref = str(mission["plan"].get("ref") or "")
    plan_path = plan_ref.split("@", 1)[0] if "@" in plan_ref else plan_ref
    design_path = str((payload.get("design_path") or payload.get("design") or "")).strip()
    return f"""You are the independent Plan Verifier for one Kitty Mission. Stay strictly read-only.

Mission objective: {mission['objective']}
Definition of done: {json.dumps(mission['definition_of_done'], ensure_ascii=False)}
Exact plan reference: {mission['plan']['ref']}
Exact plan digest: {mission['plan']['digest']}
Accountable supervisor: {mission['supervisor']['id']}
Exact prepared Builder manifest:
{json.dumps(payload, ensure_ascii=False, sort_keys=True)}

Your working directory is already checked out to the exact plan commit. Read the plan and design files DIRECTLY from the filesystem with your file-read tool — do not rely on shell/git, and treat a lack of shell access as expected, not a blocker:
- plan file: {plan_path or '(see plan reference above)'}
- design file: {design_path or '(named in the manifest, if present)'}
Also read START_HERE.md and only the authority/code needed to judge this plan. Do not trust the planner's claims merely because they appear in the plan. Do not modify files, stage, commit, push, merge, change credentials, or execute the implementation.

Evaluate: outcome match, current-state accuracy, technical soundness, scope, recoverability, economics, and whether the packet's validation_commands would actually prove the definition of done. Reject only if the evidence is stale, contradictory, unsafe, over-broad, genuinely unverifiable from the files provided, or would duplicate an existing authority — not merely because you could not run a shell command.

Your FINAL RESPONSE must be exactly one JSON object and no Markdown/prose around it:
{{"contract_version":1,"verdict":"approve" or "reject","summary":"...","findings":[{{"severity":"major" or "minor","note":"..."}}]}}
"""


def run_plan_verifier(mission: dict[str, Any]) -> dict[str, Any]:
    """Ask Builder to execute one independent read-only review of this exact plan."""
    if mission["supervisor"]["id"].startswith("dsh:"):
        raise PlanVerifierUnavailable(
            "plan verifier is not independent of the Mission supervisor"
        )
    plan_payload = mission.get("plan", {}).get("payload")
    if not isinstance(plan_payload, dict):
        raise PlanVerifierUnavailable("exact prepared plan payload is unavailable")
    if bi.manifest_sha256(plan_payload) != mission["plan"]["digest"]:
        raise PlanVerifierUnavailable(
            "prepared plan payload does not match the Mission digest"
        )

    root = repo_tools.repo_root().resolve()
    # The plan/design artifacts live on a planning ref, not the working tree, so
    # hand the reviewer the exact plan commit to check out — otherwise it can
    # only reach them through git plumbing it may not think to use.
    plan_ref = str(mission["plan"].get("ref") or "")
    review_checkout_sha = plan_ref.rsplit("@", 1)[1] if "@" in plan_ref else None
    try:
        receipt = builder_loop.run_independent_readonly_review(
            _plan_review_prompt(mission),
            root=root,
            timeout=_REVIEW_TIMEOUT_SECONDS,
            review_checkout_sha=review_checkout_sha,
        )
    except builder_loop.LoopError as exc:
        raise PlanVerifierUnavailable(str(exc)) from exc

    raw = receipt.get("output") if isinstance(receipt, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        raise PlanVerifierUnavailable("independent plan reviewer returned no result")
    try:
        result = _parse_review_json(raw)
    except json.JSONDecodeError as exc:
        raise PlanVerifierUnavailable(
            "independent plan reviewer returned invalid JSON"
        ) from exc
    if not isinstance(result, dict) or result.get("contract_version") != 1:
        raise PlanVerifierUnavailable(
            "independent plan reviewer returned an invalid contract"
        )
    if result.get("verdict") not in {"approve", "reject"}:
        raise PlanVerifierUnavailable(
            "independent plan reviewer returned an invalid verdict"
        )
    provider = receipt.get("provider")
    model = receipt.get("model")
    review_head = receipt.get("review_head")
    if not all(isinstance(value, str) and value for value in (provider, model, review_head)):
        raise PlanVerifierUnavailable("Builder reviewer receipt is missing provenance")
    result = dict(result)
    result.update(
        reviewer_id=f"dsh:{model}",
        provider=provider,
        model=model,
        review_head=review_head,
        review_origin_main=receipt.get("review_origin_main"),
        route_probes=list(receipt.get("probes") or []),
    )
    return result
