"""Mission wake/review adapter over existing Automation and free DSH seams."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from gateway import (
    artifact_store,
    automation_actions,
    automation_runs,
    builder_loop,
    builder_queue,
    builder_status_readonly,
    memory_mission,
)
from gateway import builder_initiative as bi
from mcp.builder import repo_tools

ACTION_NAME = "mission.review_pending"
_REVIEW_TIMEOUT_SECONDS = 240


def _parse_review_json(raw: str) -> Any:
    """Parse the reviewer verdict, tolerating a ```json fence some models add."""
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        last_fence = text.rfind("```")
        if first_newline >= 0 and last_fence > first_newline:
            text = text[first_newline + 1:last_fence].strip()
    return json.loads(text)


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
            receipt = reconcile_result_candidate(mission["mission_id"])
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
    if packet.get("task_state") != "done":
        return None
    attempt = next(
        (
            item for item in packet.get("attempt_history", [])
            if item.get("outcome") == "succeeded"
            and item.get("review_verdict") == "approve"
            and isinstance(item.get("result_artifact"), dict)
            and item["result_artifact"].get("state") == "ready"
        ),
        None,
    )
    if attempt is None:
        raise ResultCandidateUnavailable(
            "completed Builder task has no independently reviewed ready result artifact"
        )
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
    review_sha = _hex_digest(metadata.get("review_sha"), 40)
    diff_sha256 = _hex_digest(metadata.get("diff_sha256"), 64)
    if not all((content_hash, review_sha, diff_sha256)):
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
    return {
        "artifact_id": artifact_id,
        "content_hash": content_hash,
        "review_sha": review_sha,
        "diff_sha256": diff_sha256,
    }


def reconcile_result_candidate(mission_id: str) -> dict[str, Any]:
    """Bind finished reviewed Builder work as the exact Mission candidate, never acceptance."""
    mission = memory_mission.get_mission(mission_id, db_path=memory_mission.MISSION_DB_FILE)
    if mission["status"] in {"DONE", "STOPPED"}:
        return {"status": "not_pending", "mission_id": mission_id}
    try:
        candidate = _reviewed_builder_result(mission)
    except ResultCandidateUnavailable as exc:
        return {"status": "source_unavailable", "mission_id": mission_id, "error": str(exc)}
    if candidate is None:
        return {"status": "not_pending", "mission_id": mission_id}
    candidate_ref = f"artifact:{candidate['artifact_id']}"
    current = mission.get("candidate") or {}
    if current.get("ref") == candidate_ref and current.get("digest") == candidate["content_hash"]:
        return {"status": "already_bound", "mission_id": mission_id, "candidate": current}
    mission = memory_mission.record_candidate(
        mission_id,
        candidate_ref=candidate_ref,
        candidate_digest=candidate["content_hash"],
        db_path=memory_mission.MISSION_DB_FILE,
    )
    return {
        "status": "candidate_bound",
        "mission_id": mission_id,
        "candidate": mission["candidate"],
        "acceptance_state": mission["acceptance"]["state"],
    }


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
