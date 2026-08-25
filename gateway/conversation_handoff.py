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

import re
from datetime import UTC, datetime
from typing import Any

from gateway import builder_initiative as bi
from mcp.builder import commands as _commands
from mcp.builder import context as _context
from mcp.builder import repo_tools
from mcp.builder.schemas import receipt

_WORD_RE = re.compile(r"[a-z0-9]+")
_DEFAULT_PACKET_ID = "packet-1"
_DEFAULT_ACCEPTANCE_CRITERIA = (
    "Implementation matches the approved objective and instructions.",
)


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
        root = repo_tools.repo_root()
        base_sha = bi.resolve_base_sha(root)
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
        manifest = compile_manifest(
            objective=objective,
            instructions=instructions,
            allowed_paths=allowed_paths,
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
        design = repo_tools.write_planning_artifact(
            kind="design",
            slug=slug,
            markdown=_design_markdown(manifest, objective=objective, instructions=instructions),
            expected_base_sha=base_sha,
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
    )
    prepared["objective"] = objective.strip()
    prepared["design"] = {"path": design["artifact_path"], "sha": design["commit_sha"]}
    prepared["plan"] = {"path": plan["artifact_path"], "sha": plan["commit_sha"]}
    return prepared


def approve(
    *,
    prepared_manifest: dict[str, Any],
    expected_manifest_sha: str,
    expected_base_sha: str,
    approval_nonce: str,
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
    return _commands.mission_approve(
        prepared_manifest,
        expected_manifest_sha=expected_manifest_sha,
        expected_base_sha=expected_base_sha,
        approval_nonce=approval_nonce,
    )


def resume(*, mission_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    """Recover durable job state for a reloaded conversation, no transcript required.

    A direct pass-through to the existing ``resume_context``: identical
    behavior whether the caller is an MCP client or Kitty's own chat UI, and
    Builder facts (including failure/blocker state) are never softened into
    a false chat-side success.
    """
    return _context.resume_context(mission_id=mission_id, task_id=task_id)
