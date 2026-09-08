"""Conversation -> approved KittyBuilder job handoff for Kitty's native chat.

Kitty's own chat surface has no tool executor of its own (see
``gateway/routes/completions.py``): nothing here runs code, and the
conversation is never the source of execution truth. What a conversation
*can* do is compile an actionable task into the exact Builder Mission/packet
representation KittyBuilder already understands, and hand it through the
same propose -> approve -> resume contract the KittyBuilder MCP bridge
(``mcp/builder``) already exposes to external clients.

This module owns no queue, no approval state machine, and no execution
loop. ``propose`` and ``resume`` are thin wrappers around
``mcp.builder.commands``/``mcp.builder.context``; ``approve`` adds exactly
one guard -- an explicit ``confirmed`` flag the caller must set only in
direct response to a human clicking Approve -- before delegating to the
same ``mission_approve`` an MCP client would call. Durable Builder state
(initiatives, tasks, attempts, execution, publication) is unchanged and
remains the single authority.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Iterator

from gateway import agent_coordination, llm_client, memory_mission
from gateway.builder_scope import normalize_allowed_paths
from mcp.builder import commands as _commands
from mcp.builder import context as _context
from mcp.builder import repo_tools
from mcp.builder.schemas import receipt

logger = logging.getLogger("kitty.conversation_handoff")

_WORD_RE = re.compile(r"[a-z0-9]+")
_DEFAULT_PACKET_ID = "packet-1"
_DEFAULT_ACCEPTANCE_CRITERIA = (
    "Implementation matches the approved objective and instructions.",
)
_MISSION_SUPERVISOR_ID = "kitty"


def _gateway_mission_id(builder_initiative_id: str) -> str:
    """Namespace Gateway Mission identity away from Builder initiative identity."""
    return f"gateway-conversation:{builder_initiative_id}"

def _resolve_unique_tracked_path_aliases(allowed_paths: list[str]) -> list[str]:
    """Resolve only unambiguous extensionless aliases to tracked repo files.

    Proposal models sometimes describe a familiar file by its stem (for
    example ``README``). Builder execution cannot safely guess later at the
    mutation boundary, so canonicalize only when exactly one tracked file in
    the same directory has that stem. New files and ambiguous aliases remain
    unchanged for normal scope validation.
    """
    try:
        root = repo_tools.repo_root()
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
    except Exception:
        return list(allowed_paths)

    tracked = [
        PurePosixPath(raw.decode("utf-8"))
        for raw in result.stdout.split(b"\0")
        if raw
    ]
    resolved: list[str] = []
    for path in allowed_paths:
        pure = PurePosixPath(path)
        if (root / path).exists() or pure.suffix:
            resolved.append(path)
            continue
        matches = [
            candidate
            for candidate in tracked
            if candidate.parent == pure.parent and candidate.stem == pure.name
        ]
        resolved.append(matches[0].as_posix() if len(matches) == 1 else path)
    return resolved


def _scope_maps_to_current_kx(allowed_paths: list[str]) -> bool:
    """Return whether every proposed mutation scope has current KX ownership.

    Minimal/legacy test repositories without a registry keep their existing
    behavior. A real Kitty checkout with KX must reject a doomed proposal
    before planning or queue state is created.
    """
    root = repo_tools.repo_root()
    registry_path = root / "coordination" / "resources.yaml"
    if not registry_path.exists():
        return True
    for path in allowed_paths:
        target = root / path
        if target.is_dir():
            resources = agent_coordination.resolve_scopes_to_resources(
                [path], registry_path=registry_path
            )
        else:
            resources = agent_coordination.resolve_paths_to_resources(
                [path], registry_path=registry_path
            )
        if not resources:
            return False
    return True


_PROPOSAL_MODEL = "kitty-small"
_PROPOSAL_SYSTEM_PROMPT = """
You are a strict JSON compiler for KittyBuilder proposals.

Convert the user's requested code/repository change into exactly one JSON object.
Return JSON only: no reasoning, prose, markdown, offer sentence, or code fence.

Required fields:
- "objective": one concrete sentence describing the finished result.
- "allowed_paths": a non-empty list of the narrowest repo-relative files or directories the task may modify.

Optional fields, only when useful:
- "title": short task title.
- "acceptance_criteria": list of concrete checkable outcomes (plain statements, not shell commands).

Do not emit shell commands. Do not execute anything. Do not claim work is queued, running, approved, or complete.
Never use broad scope such as "." or the repository root.
If the user names a file, preserve that repo-relative file in allowed_paths.
""".strip()


def _proposal_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        last_fence = stripped.rfind("```")
        if first_newline >= 0 and last_fence > first_newline:
            stripped = stripped[first_newline + 1:last_fence].strip()
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start:end + 1]
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("proposal compiler did not return a JSON object")
    return payload


class _ProposalUnusable(Exception):
    """A model response parsed but is not a usable Builder proposal."""

    def __init__(self, error_code: str, error: str) -> None:
        super().__init__(error)
        self.error_code = error_code
        self.error = error


def _build_task_from_raw(raw: Any, request: str) -> dict[str, Any]:
    """Turn one compiler JSON object into a bounded Builder task or raise.

    Model-supplied ``validation_commands`` are intentionally dropped: Builder
    runs validation with ``shell=True`` after a generic approval and the
    proposal card does not show them, so a prompt-injected or simply wrong
    command must never reach that path. Builder derives its own validation from
    the acceptance criteria instead.
    """
    if not isinstance(raw, dict):
        raise _ProposalUnusable(
            "proposal_invalid",
            "Kitty received an unusable proposal from the model. Try again, or make the requested outcome more concrete.",
        )
    objective = raw.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        raise _ProposalUnusable(
            "proposal_invalid",
            "Kitty could not produce a usable objective. Make the requested outcome more concrete, then try again.",
        )
    try:
        allowed_paths = _resolve_unique_tracked_path_aliases(
            normalize_allowed_paths(raw.get("allowed_paths"))
        )
    except ValueError as exc:
        raise _ProposalUnusable(
            "proposal_scope_invalid",
            "Kitty could not determine a safe file scope. Narrow the request to one concrete file or area, then try again.",
        ) from exc

    task: dict[str, Any] = {
        "objective": objective.strip(),
        "instructions": request.strip(),
        "allowed_paths": allowed_paths,
    }
    for key in ("title", "initiative_id"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            task[key] = value.strip()
    criteria = raw.get("acceptance_criteria")
    if criteria is not None:
        if not isinstance(criteria, list) or any(
            not isinstance(item, str) or not item.strip() for item in criteria
        ):
            raise _ProposalUnusable(
                "proposal_invalid", "Compiled proposal has invalid acceptance_criteria."
            )
        task["acceptance_criteria"] = [item.strip() for item in criteria]
    return task


def compile_request(request: str, *, allow_provider_fallback: bool = False) -> dict[str, Any]:
    """Compile plain language into a bounded Builder task without chat context.

    This intentionally bypasses the personal chat context assembler. It uses the
    existing LLM provider hub only for task shaping; no planning artifact, queue
    row, approval, or worker is created here.
    """
    if not isinstance(request, str) or not request.strip():
        return {
            "ok": False,
            "error_code": "request_required",
            "error": "Describe the result you want Builder to produce.",
        }

    messages = [
        {"role": "system", "content": _PROPOSAL_SYSTEM_PROMPT},
        {"role": "user", "content": request.strip()},
    ]

    if allow_provider_fallback:
        return _compile_via_saved_provider(messages, request)

    # Default: no-spend only. One bounded retry that also covers a structurally
    # invalid model response, not just a transport failure.
    provider_exhausted = False
    last_unusable: _ProposalUnusable | None = None
    for attempt in range(2):
        try:
            text = llm_client.call_llm(
                messages,
                model=_PROPOSAL_MODEL,
                max_tokens=900,
                temperature=0,
                timeout=30,
                response_format={"type": "json_object"},
                operation="builder.proposal.compile",
                metadata={
                    "route": "builder_proposal_compile",
                    "spend_policy": "zero_cost_only",
                    "attempt": attempt + 1,
                },
                zero_cost_only=True,
            )
        except llm_client.ProviderChainExhausted:
            provider_exhausted = True
            continue
        except Exception:
            logger.exception("proposal compile failed on the no-spend route")
            return {
                "ok": False,
                "error_code": "proposal_compile_failed",
                "error": "Kitty could not prepare the proposal right now. Try again in a moment.",
            }

        provider_exhausted = False
        try:
            task = _build_task_from_raw(_proposal_json(text), request)
        except (json.JSONDecodeError, ValueError, TypeError):
            last_unusable = _ProposalUnusable(
                "proposal_invalid",
                "Kitty received an unusable proposal from the model. Try again, or make the requested outcome more concrete.",
            )
            continue
        except _ProposalUnusable as exc:
            last_unusable = exc
            continue
        return {
            "ok": True,
            "task": task,
            "routing": {"mode": "no_spend", "saved_preference_changed": False},
        }

    if provider_exhausted:
        return {
            "ok": False,
            "error_code": "proposal_no_spend_unavailable",
            "error": (
                "Kitty could not prepare this proposal on a no-spend route right now. "
                "Your request is preserved; retry the no-spend route or explicitly use your saved provider route."
            ),
        }
    if last_unusable is not None:
        return {"ok": False, "error_code": last_unusable.error_code, "error": last_unusable.error}
    return {
        "ok": False,
        "error_code": "proposal_invalid",
        "error": "Kitty received an unusable proposal from the model. Try again, or make the requested outcome more concrete.",
    }


def _compile_via_saved_provider(messages: list[dict[str, Any]], request: str) -> dict[str, Any]:
    """One request-scoped retry pinned exactly to the saved provider route.

    This never cascades to LiteLLM or any other provider and never changes the
    saved preference. With no saved provider it is a no-op surfaced as an
    actionable message rather than a silent spend elsewhere.
    """
    try:
        selected = llm_client.selected_provider_name()
    except llm_client.ProviderChainExhausted:
        selected = None
    if selected is None:
        return {
            "ok": False,
            "error_code": "no_saved_provider",
            "error": "You have no saved provider route to try. Set a provider in Settings, or retry the no-spend route.",
        }
    try:
        text = llm_client.call_selected_provider(
            selected,
            messages,
            request_model=_PROPOSAL_MODEL,
            max_tokens=900,
            temperature=0,
            timeout=30,
            response_format={"type": "json_object"},
            operation="builder.proposal.compile",
            metadata={
                "route": "builder_proposal_compile",
                "spend_policy": "saved_provider",
                "request_scoped_provider_fallback": True,
            },
        )
    except llm_client.ProviderChainExhausted:
        return {
            "ok": False,
            "error_code": "proposal_compile_failed",
            "error": f"The saved provider route ({selected}) could not prepare this proposal right now.",
        }
    except Exception:
        logger.exception("proposal compile failed on the saved provider route")
        return {
            "ok": False,
            "error_code": "proposal_compile_failed",
            "error": "Kitty could not prepare the proposal right now. Try again in a moment.",
        }
    try:
        task = _build_task_from_raw(_proposal_json(text), request)
    except (json.JSONDecodeError, ValueError, TypeError):
        return {
            "ok": False,
            "error_code": "proposal_invalid",
            "error": "Kitty received an unusable proposal from the model. Try again, or make the requested outcome more concrete.",
        }
    except _ProposalUnusable as exc:
        return {"ok": False, "error_code": exc.error_code, "error": exc.error}
    return {
        "ok": True,
        "task": task,
        "routing": {"mode": "request_scoped_fallback", "saved_preference_changed": False},
    }


def _slugify(text: str, *, max_len: int = 40) -> str:
    words = _WORD_RE.findall(text.lower())
    slug = "-".join(words)[:max_len].strip("-")
    return slug or "task"


def compile_manifest(
    *,
    objective: str,
    instructions: str,
    allowed_paths: list[str],
    initiative_id: str | None = None,
    title: str | None = None,
    acceptance_criteria: list[str] | None = None,
    validation_commands: list[str] | None = None,
) -> dict[str, Any]:
    """Compile a conversation-derived task into a single-packet Builder manifest.

    Pure and side-effect free: this only shapes data into the manifest schema
    ``gateway.builder_initiative.validate_manifest`` already enforces. It does
    not touch the repository or Builder state.
    """
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("objective must be a non-empty string")
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("instructions must be a non-empty string")
    if not allowed_paths:
        raise ValueError("allowed_paths must name at least one path the job may touch")

    slug = _slugify(initiative_id or title or objective)
    resolved_id = initiative_id or f"conv-{slug}-{datetime.now(UTC):%Y%m%d%H%M%S}"
    resolved_title = (title or objective).strip()[:120]
    criteria = list(acceptance_criteria) if acceptance_criteria else list(
        _DEFAULT_ACCEPTANCE_CRITERIA
    )

    return {
        "manifest_version": 1,
        "initiative_id": resolved_id,
        "title": resolved_title,
        "description": instructions.strip(),
        "packets": [
            {
                "id": _DEFAULT_PACKET_ID,
                "title": resolved_title,
                "objective": objective.strip(),
                "depends_on": [],
                "acceptance_criteria": criteria,
                "allowed_paths": list(allowed_paths),
                "validation_commands": list(validation_commands) if validation_commands else [],
            }
        ],
    }


def _design_markdown(manifest: dict[str, Any], *, objective: str, instructions: str) -> str:
    return (
        f"# {manifest['title']}\n\n"
        "## Source\n\n"
        "Compiled from a Kitty conversation; not an independently authored "
        "design session.\n\n"
        f"## Objective\n\n{objective.strip()}\n\n"
        f"## Instructions\n\n{instructions.strip()}\n"
    )


def _plan_markdown(manifest: dict[str, Any], *, instructions: str) -> str:
    packet = manifest["packets"][0]
    criteria = "\n".join(f"- {item}" for item in packet["acceptance_criteria"])
    paths = "\n".join(f"- {item}" for item in packet["allowed_paths"])
    return (
        f"# {manifest['title']} — plan\n\n"
        f"## Approach\n\n{instructions.strip()}\n\n"
        f"## Acceptance criteria\n\n{criteria}\n\n"
        f"## Allowed paths\n\n{paths}\n"
    )


@contextmanager
def _planning_artifact_claim(
    *,
    slug: str,
    base_sha: str,
    task_id: str,
) -> Iterator[str | None]:
    """Own Builder's internal planning writes without widening user code scope."""
    root = repo_tools.repo_root()
    registry_path = root / "coordination" / "resources.yaml"
    if not registry_path.exists():
        # Minimal test repos and legacy deployments without KX do not need a
        # synthetic claim. Their own Git hooks remain authoritative.
        yield None
        return

    paths = [
        repo_tools.planning_artifact_path("design", slug),
        repo_tools.planning_artifact_path("plan", slug),
    ]
    resources = agent_coordination.resolve_paths_to_resources(
        paths, registry_path=registry_path
    )
    if len(resources) != 1:
        raise repo_tools.PlanningArtifactError(
            "planning artifacts must resolve to exactly one coordination resource"
        )

    session_id = f"kitty-builder-planning-{uuid.uuid4().hex}"
    db_path = agent_coordination.canonical_repo_root(root) / agent_coordination.DB_FILENAME
    acquired = agent_coordination.acquire(
        session_id=session_id,
        participant="KittyBuilder",
        role="OWN",
        resource_id=resources[0],
        lane="conversation-planning",
        task_id=task_id,
        branch=None,
        worktree=str(root),
        base_sha=base_sha,
        paths=paths,
        lease_seconds=5 * 60,
        db_path=db_path,
        registry_path=registry_path,
    )
    if acquired.get("status") != "ACQUIRED":
        holder = acquired.get("holder") or {}
        detail = holder.get("session_id") or "another active owner"
        raise repo_tools.PlanningArtifactError(
            f"planning artifacts are locked by {detail}"
        )

    try:
        yield session_id
    finally:
        agent_coordination.release(session_id, db_path=db_path)


def propose(
    *,
    objective: str,
    instructions: str,
    allowed_paths: list[str],
    initiative_id: str | None = None,
    title: str | None = None,
    acceptance_criteria: list[str] | None = None,
    validation_commands: list[str] | None = None,
) -> dict[str, Any]:
    """Compile a conversation task and prepare it as a bound Mission candidate.

    Creates no Builder queue work. The compiled task is written as an
    isolated SHA-bound design/plan pair -- the same lightweight
    planning-artifact mechanism ``save_design``/``save_plan`` already use --
    then handed to the existing ``mission_prepare``, so the returned receipt
    (including the approval nonce) is byte-for-byte the same contract an MCP
    client would see. There is exactly one approval mechanism system-wide.
    """
    try:
        repo_tools.repo_root()
        base_sha = repo_tools.repo_head()
    except Exception as exc:
        return receipt(
            "conversation_propose",
            ok=False,
            state="unavailable",
            error_code="repo_unavailable",
            error=f"{type(exc).__name__}: {exc}",
            next_action="Resolve the repository/base-SHA error before proposing work.",
        )

    try:
        resolved_allowed_paths = normalize_allowed_paths(allowed_paths)
        resolved_allowed_paths = _resolve_unique_tracked_path_aliases(
            resolved_allowed_paths
        )
        if not _scope_maps_to_current_kx(resolved_allowed_paths):
            raise ValueError("proposed mutation scope has no safe Builder ownership boundary")
    except ValueError:
        return receipt(
            "conversation_propose",
            ok=False,
            state="needs_decision",
            error_code="proposal_scope_invalid",
            error=(
                "Kitty could not determine a safe file scope for this proposal. "
                "Name one concrete file or area and try again."
            ),
            next_action="Revise the proposal to a concrete file or area Kitty can safely modify.",
        )

    try:
        manifest = compile_manifest(
            objective=objective,
            instructions=instructions,
            allowed_paths=resolved_allowed_paths,
            initiative_id=initiative_id,
            title=title,
            acceptance_criteria=acceptance_criteria,
            validation_commands=validation_commands,
        )
    except ValueError as exc:
        return receipt(
            "conversation_propose",
            ok=False,
            state="needs_decision",
            error_code="manifest_invalid",
            error=str(exc),
            next_action="Supply a valid objective, instructions, and at least one allowed path.",
        )

    slug = _slugify(manifest["initiative_id"])
    try:
        with _planning_artifact_claim(
            slug=slug, base_sha=base_sha, task_id=manifest["initiative_id"]
        ) as planning_session_id:
            design = repo_tools.write_planning_artifact(
                kind="design",
                slug=slug,
                markdown=_design_markdown(manifest, objective=objective, instructions=instructions),
                expected_base_sha=base_sha,
                agent_session_id=planning_session_id,
            )
            plan = repo_tools.write_planning_artifact(
                kind="plan",
                slug=slug,
                markdown=_plan_markdown(manifest, instructions=instructions),
                # A plan branches from the design commit itself, per
                # docs/KITTYBUILDER_MCP.md ("expected_base_sha is the commit the
                # plan branch starts from; in the normal workflow it is the
                # design commit itself").
                expected_base_sha=design["commit_sha"],
                expected_dependency_sha=design["commit_sha"],
                agent_session_id=planning_session_id,
            )
    except Exception as exc:
        return receipt(
            "conversation_propose",
            ok=False,
            state="needs_decision",
            error_code="planning_artifact_failed",
            error=f"{type(exc).__name__}: {exc}",
            next_action="Resolve the planning-artifact error and propose again.",
        )

    prepared = _commands.mission_prepare(
        manifest,
        design_path=design["artifact_path"],
        design_sha=design["commit_sha"],
        plan_path=plan["artifact_path"],
        plan_sha=plan["commit_sha"],
        expected_base_sha=base_sha,
        base_scope="checkout",
    )
    if not prepared.get("ok"):
        return prepared

    builder_initiative_id = str(prepared["mission_id"])
    gateway_mission_id = _gateway_mission_id(builder_initiative_id)
    packet = manifest["packets"][0]
    try:
        mission = memory_mission.ensure_mission(
            mission_id=gateway_mission_id,
            objective=objective.strip(),
            definition_of_done=list(packet["acceptance_criteria"]),
            supervisor_id=_MISSION_SUPERVISOR_ID,
            db_path=memory_mission.MISSION_DB_FILE,
        )
        mission = memory_mission.bind_builder_locator(
            gateway_mission_id,
            initiative_id=builder_initiative_id,
            db_path=memory_mission.MISSION_DB_FILE,
        )
        plan_ref = f"{plan['artifact_path']}@{plan['commit_sha']}"
        mission = memory_mission.set_plan(
            gateway_mission_id,
            plan_ref=plan_ref,
            plan_digest=str(prepared["manifest_sha256"]),
            plan_payload=prepared["prepared_manifest"],
            db_path=memory_mission.MISSION_DB_FILE,
        )
    except memory_mission.MissionError as exc:
        return receipt(
            "conversation_propose",
            ok=False,
            state="needs_decision",
            error_code="mission_binding_failed",
            error=str(exc),
            next_action="Resolve the Mission identity conflict before proposing this work again.",
        )

    prepared["objective"] = objective.strip()
    prepared["design"] = {"path": design["artifact_path"], "sha": design["commit_sha"]}
    prepared["plan"] = {
        "path": plan["artifact_path"],
        "sha": plan["commit_sha"],
        "digest": prepared["manifest_sha256"],
    }
    prepared["gateway_mission_id"] = gateway_mission_id
    prepared["gateway_mission_status"] = mission["status"]
    prepared["gateway_plan_digest"] = mission["plan"]["digest"]
    prepared["gateway_plan_review_state"] = mission["plan"]["review_state"]
    return prepared


def approve(
    *,
    prepared_manifest: dict[str, Any],
    expected_manifest_sha: str,
    expected_base_sha: str,
    approval_nonce: str,
    gateway_mission_id: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Create the durable Builder job -- only after explicit human confirmation.

    ``confirmed`` must be set by the caller (Kitty's chat UI) only in direct
    response to a human clicking Approve on the exact proposal ``propose()``
    returned. Model-narrated approval text is never proof; this delegates to
    the same nonce-bound, idempotent ``mission_approve`` an MCP client uses,
    so replaying an identical approval creates no duplicate job.
    """
    if not confirmed:
        return receipt(
            "conversation_approve",
            ok=False,
            state="needs_approval",
            error_code="approval_required",
            error="creating a Builder job requires explicit human confirmation",
            next_action="Show the exact prepared Mission and require an explicit Approve action.",
        )

    mission: dict[str, Any] | None = None
    if gateway_mission_id is not None:
        try:
            mission = memory_mission.get_mission(
                gateway_mission_id, db_path=memory_mission.MISSION_DB_FILE
            )
        except memory_mission.MissionError as exc:
            return receipt(
                "conversation_approve",
                ok=False,
                state="needs_decision",
                error_code="mission_not_found",
                error=str(exc),
                next_action="Recover the durable Mission before approving Builder execution.",
            )
        builder_initiative_id = prepared_manifest.get("initiative_id")
        locator = mission.get("builder_locator") or {}
        if locator.get("initiative_id") != builder_initiative_id:
            return receipt(
                "conversation_approve",
                ok=False,
                state="needs_decision",
                error_code="mission_builder_mismatch",
                error="Gateway Mission is bound to a different Builder initiative.",
                next_action="Re-open the current Mission proposal instead of approving a different Builder job.",
            )
        if mission["plan"]["digest"] != expected_manifest_sha:
            return receipt(
                "conversation_approve",
                ok=False,
                state="needs_decision",
                error_code="plan_digest_mismatch",
                error="The approved Mission plan does not match this Builder proposal version.",
                next_action="Review the current proposal version before approving execution.",
            )
        if mission["plan"]["review_state"] != "approved":
            return receipt(
                "conversation_approve",
                ok=False,
                state="plan_review",
                error_code="plan_review_required",
                error="Independent plan review is required before Builder execution can be approved.",
                next_action="Wait for an independent reviewer to approve this exact plan.",
                gateway_mission_id=gateway_mission_id,
            )
        if locator.get("task_id") is None and mission["status"] != "PLAN_REVIEW":
            return receipt(
                "conversation_approve",
                ok=False,
                state="needs_decision",
                error_code="mission_not_ready",
                error=f"Mission cannot start Builder execution from {mission['status']} state.",
                next_action="Recover the Mission state before approving execution.",
            )

    result = _commands.mission_approve(
        prepared_manifest,
        expected_manifest_sha=expected_manifest_sha,
        expected_base_sha=expected_base_sha,
        approval_nonce=approval_nonce,
        base_scope="checkout",
    )
    if not result.get("ok") or gateway_mission_id is None:
        return result

    tasks = result.get("tasks") or []
    task_id = tasks[0].get("task_id") if len(tasks) == 1 and isinstance(tasks[0], dict) else None
    if not isinstance(task_id, str) or not task_id:
        return receipt(
            "conversation_approve",
            ok=False,
            state="recovery_required",
            error_code="mission_binding_failed",
            error="Builder accepted the work but did not return the single durable task locator Mission expects.",
            next_action="Retry this exact approval to reconcile the existing Builder job; do not compile a new one.",
            gateway_mission_id=gateway_mission_id,
            builder_receipt=result,
        )

    try:
        mission = memory_mission.bind_builder_locator(
            gateway_mission_id,
            initiative_id=str(result["mission_id"]),
            task_id=task_id,
            db_path=memory_mission.MISSION_DB_FILE,
        )
        if mission["status"] == "PLAN_REVIEW":
            mission = memory_mission.begin_execution(
                gateway_mission_id, db_path=memory_mission.MISSION_DB_FILE
            )
    except memory_mission.MissionError as exc:
        return receipt(
            "conversation_approve",
            ok=False,
            state="recovery_required",
            error_code="mission_binding_failed",
            error=str(exc),
            next_action="Retry this exact approval to reconcile the existing Builder job; do not compile a new one.",
            gateway_mission_id=gateway_mission_id,
            builder_receipt=result,
        )

    result["gateway_mission_id"] = gateway_mission_id
    result["gateway_mission_status"] = mission["status"]
    return result


def resume(*, mission_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    """Recover durable job state for a reloaded conversation, no transcript required.

    A direct pass-through to the existing ``resume_context``: identical
    behavior whether the caller is an MCP client or Kitty's own chat UI, and
    Builder facts (including failure/blocker state) are never softened into
    a false chat-side success.
    """
    return _context.resume_context(mission_id=mission_id, task_id=task_id)
