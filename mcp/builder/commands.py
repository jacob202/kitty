"""Governed KittyBuilder mutation adapters for MCP clients.

Every operation delegates to an existing Builder authority. This module owns no
queue/run state and exposes no arbitrary shell or Git command surface.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
import subprocess
from typing import Any

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_commands import command_publish

from . import repo_tools
from .context import work_status
from .schemas import MCP_ARTIFACT_MARKER, receipt

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_LIVE_TASK_STATES = frozenset({"claimed", "running", "pr_opened", "awaiting_review"})


def _validate_id(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"{label} must match {_ID_RE.pattern!r}")
    return value


def _artifact_path_ok(path: str, *, kind: str) -> bool:
    prefix = (
        "docs/superpowers/specs/" if kind == "design" else "docs/superpowers/plans/"
    )
    return isinstance(path, str) and path.startswith(prefix) and path.endswith(".md")


def _commit_is_ancestor(ancestor: str, descendant: str) -> bool:
    """Return Git ancestry using a fixed argv-only command."""
    if not _SHA_RE.fullmatch(ancestor) or not _SHA_RE.fullmatch(descendant):
        raise ValueError("planning lineage requires full 40-character commit SHAs")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo_tools.repo_root(),
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = (result.stderr or result.stdout or "no output").strip()[:500]
    raise RuntimeError(
        f"git merge-base --is-ancestor exited {result.returncode}: {detail}"
    )


def _artifact_refs_from_manifest(manifest: dict[str, Any]) -> dict[str, str] | None:
    description = manifest.get("description")
    if not isinstance(description, str) or MCP_ARTIFACT_MARKER not in description:
        return None
    payload = description.split(MCP_ARTIFACT_MARKER, 1)[1].strip()
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    return {str(key): str(value) for key, value in decoded.items() if value is not None}


def _approval_nonce(*, manifest_sha: str, base_sha: str, refs: dict[str, str]) -> str:
    payload = json.dumps(
        {
            "schema": 1,
            "manifest_sha256": manifest_sha,
            "base_sha": base_sha,
            "design_path": refs.get("design_path"),
            "design_sha": refs.get("design_sha"),
            "plan_path": refs.get("plan_path"),
            "plan_sha": refs.get("plan_sha"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verify_bound_artifacts(refs: dict[str, str], *, base_sha: str) -> None:
    design_path = refs.get("design_path", "")
    design_sha = refs.get("design_sha", "")
    plan_path = refs.get("plan_path", "")
    plan_sha = refs.get("plan_sha", "")
    recorded_base = refs.get("base_sha")

    if recorded_base != base_sha:
        raise ValueError(
            f"planning lineage base mismatch: manifest records {recorded_base!r}, expected {base_sha}"
        )
    if not _artifact_path_ok(design_path, kind="design"):
        raise ValueError("design_path must be under docs/superpowers/specs/ and end in .md")
    if not _artifact_path_ok(plan_path, kind="plan"):
        raise ValueError("plan_path must be under docs/superpowers/plans/ and end in .md")
    if not _SHA_RE.fullmatch(design_sha) or not _SHA_RE.fullmatch(plan_sha):
        raise ValueError("design_sha and plan_sha must be full 40-character commit SHAs")

    # Prove the exact files exist at the exact commits before checking ancestry.
    repo_tools.read_tracked_file(design_path, ref=design_sha, start_line=1, end_line=1)
    repo_tools.read_tracked_file(plan_path, ref=plan_sha, start_line=1, end_line=1)
    if not _commit_is_ancestor(base_sha, design_sha):
        raise ValueError("planning lineage invalid: design commit does not descend from code base")
    if not _commit_is_ancestor(design_sha, plan_sha):
        raise ValueError("planning lineage invalid: plan commit does not descend from design commit")


def _bind_artifacts(
    manifest: dict[str, Any],
    *,
    design_path: str,
    design_sha: str,
    plan_path: str,
    plan_sha: str,
    base_sha: str,
) -> dict[str, Any]:
    refs = {
        "design_path": design_path,
        "design_sha": design_sha,
        "plan_path": plan_path,
        "plan_sha": plan_sha,
        "base_sha": base_sha,
    }
    _verify_bound_artifacts(refs, base_sha=base_sha)

    prepared = copy.deepcopy(manifest)
    description = prepared.get("description")
    base_description = description if isinstance(description, str) else ""
    if MCP_ARTIFACT_MARKER in base_description:
        base_description = base_description.split(MCP_ARTIFACT_MARKER, 1)[0].rstrip()
    prepared["description"] = (
        base_description.rstrip() + MCP_ARTIFACT_MARKER + json.dumps(refs, sort_keys=True)
    )
    return prepared


def mission_prepare(
    manifest: dict[str, Any],
    *,
    design_path: str,
    design_sha: str,
    plan_path: str,
    plan_sha: str,
    expected_base_sha: str,
) -> dict[str, Any]:
    """Validate and bind an immutable Mission candidate without creating queue work."""
    try:
        root = repo_tools.repo_root()
        current_base = bi.resolve_base_sha(root)
        if current_base != expected_base_sha:
            return receipt(
                "mission_prepare",
                ok=False,
                state="needs_decision",
                error_code="stale_base",
                error=(
                    f"expected base {expected_base_sha} does not match current Builder base "
                    f"{current_base}"
                ),
                next_action="Rebase/review the design and plan against current main.",
            )
        prepared = _bind_artifacts(
            manifest,
            design_path=design_path,
            design_sha=design_sha,
            plan_path=plan_path,
            plan_sha=plan_sha,
            base_sha=expected_base_sha,
        )
        errors = bi.validate_manifest(prepared)
        if errors:
            return receipt(
                "mission_prepare",
                ok=False,
                state="needs_decision",
                error_code="manifest_invalid",
                error="; ".join(errors),
                next_action="Correct the Mission manifest before approval.",
                validation_errors=errors,
            )
        warnings = bi.warn_manifest(prepared, repo_root=root)
        digest = bi.manifest_sha256(prepared)
        refs = _artifact_refs_from_manifest(prepared)
        assert refs is not None
        return receipt(
            "mission_prepare",
            ok=True,
            state="prepared",
            summary="Mission is bound to exact code/design/plan revisions.",
            next_action="Present this exact prepared version for explicit human approval.",
            mission_id=prepared.get("initiative_id"),
            manifest_sha256=digest,
            expected_base_sha=expected_base_sha,
            warnings=warnings,
            approval_nonce=_approval_nonce(
                manifest_sha=digest,
                base_sha=expected_base_sha,
                refs=refs,
            ),
            prepared_manifest=prepared,
        )
    except Exception as exc:
        return receipt(
            "mission_prepare",
            ok=False,
            state="needs_decision",
            error_code="prepare_failed",
            error=f"{type(exc).__name__}: {exc}",
            next_action="Resolve the named preparation error before approval.",
        )


def mission_approve(
    prepared_manifest: dict[str, Any],
    *,
    expected_manifest_sha: str,
    expected_base_sha: str,
    approval_nonce: str,
) -> dict[str, Any]:
    """Apply only the exact prepared Mission version approved by the client/user."""
    try:
        root = repo_tools.repo_root()
        current_base = bi.resolve_base_sha(root)
        if current_base != expected_base_sha:
            return receipt(
                "mission_approve",
                ok=False,
                state="needs_decision",
                error_code="stale_base",
                error=f"Builder base moved from {expected_base_sha} to {current_base}",
                next_action="Prepare and approve a new Mission version against the new base.",
            )
        errors = bi.validate_manifest(prepared_manifest)
        if errors:
            return receipt(
                "mission_approve",
                ok=False,
                state="needs_decision",
                error_code="manifest_invalid",
                error="; ".join(errors),
                next_action="Prepare a valid Mission version.",
            )
        digest = bi.manifest_sha256(prepared_manifest)
        refs = _artifact_refs_from_manifest(prepared_manifest)
        if digest != expected_manifest_sha or refs is None:
            return receipt(
                "mission_approve",
                ok=False,
                state="needs_decision",
                error_code="approval_mismatch",
                error="prepared Mission contents no longer match the approved version",
                next_action="Run mission_prepare again and review the new version.",
            )
        expected_nonce = _approval_nonce(
            manifest_sha=digest,
            base_sha=expected_base_sha,
            refs=refs,
        )
        if not hmac.compare_digest(expected_nonce, approval_nonce):
            return receipt(
                "mission_approve",
                ok=False,
                state="needs_decision",
                error_code="approval_mismatch",
                error="approval nonce does not match this Mission/design/plan/base version",
                next_action="Run mission_prepare again and approve the exact returned nonce.",
            )
        _verify_bound_artifacts(refs, base_sha=expected_base_sha)
        applied = bi.apply_manifest(prepared_manifest, repo_root=root)
        return receipt(
            "mission_approve",
            ok=True,
            state="accepted",
            summary="Mission accepted into KittyBuilder durable state.",
            next_action="Start Builder execution or continue discussing the accepted work.",
            mission_id=applied.get("initiative_id"),
            manifest_sha256=applied.get("manifest_sha256"),
            apply_status=applied.get("status"),
            tasks=applied.get("packets") or [],
        )
    except Exception as exc:
        return receipt(
            "mission_approve",
            ok=False,
            state="needs_decision",
            error_code="approval_failed",
            error=f"{type(exc).__name__}: {exc}",
            next_action="Inspect the durable Builder error before retrying approval.",
        )


def execution_pause(mission_id: str, reason: str) -> dict[str, Any]:
    try:
        _validate_id(mission_id, label="mission_id")
        if not reason or not reason.strip():
            raise ValueError("pause reason must be non-empty")
        bi.pause_initiative(mission_id, reason=reason)
        return receipt(
            "execution_pause",
            ok=True,
            state="paused",
            mission_id=mission_id,
            summary=f"Builder initiative {mission_id} paused.",
            next_action="Resume when the blocker or decision is resolved.",
        )
    except Exception as exc:
        return receipt(
            "execution_pause",
            ok=False,
            state="unknown",
            error_code="pause_failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def execution_resume(mission_id: str) -> dict[str, Any]:
    try:
        _validate_id(mission_id, label="mission_id")
        bi.resume_initiative(mission_id)
        return receipt(
            "execution_resume",
            ok=True,
            state="active",
            mission_id=mission_id,
            summary=f"Builder initiative {mission_id} resumed.",
            next_action="Call execution_start to continue eligible work.",
        )
    except Exception as exc:
        return receipt(
            "execution_resume",
            ok=False,
            state="unknown",
            error_code="resume_failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def execution_cancel(
    task_id: str,
    reason: str,
    *,
    actor: str = "mcp-client",
) -> dict[str, Any]:
    try:
        _validate_id(task_id, label="task_id")
        if not reason or not reason.strip():
            raise ValueError("cancel reason must be non-empty")
        result = bq.operator_cancel_task(task_id, reason=reason, actor=actor)
        return receipt(
            "execution_cancel",
            ok=True,
            state=result.get("state"),
            task_id=task_id,
            summary=f"Builder task {task_id} cancelled durably.",
        )
    except Exception as exc:
        return receipt(
            "execution_cancel",
            ok=False,
            state="unknown",
            error_code="cancel_failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def _selected_packets(work: dict[str, Any], packet_id: str | None) -> list[dict[str, Any]]:
    packets = list(work.get("packets") or [])
    if packet_id is None:
        return packets
    selected = [packet for packet in packets if packet.get("packet_id") == packet_id]
    if not selected:
        raise ValueError(f"packet not found in mission: {packet_id}")
    return selected


def execution_start(
    mission_id: str,
    packet_id: str | None = None,
    *,
    free: bool = True,
    spend_authorized: bool = False,
) -> dict[str, Any]:
    """Detach the existing bounded Builder run loop; durable truth stays in Builder."""
    try:
        _validate_id(mission_id, label="mission_id")
        if packet_id is not None:
            _validate_id(packet_id, label="packet_id")
        if not free and not spend_authorized:
            return receipt(
                "execution_start",
                ok=False,
                state="needs_approval",
                error_code="spend_not_authorized",
                error="paid Builder execution requires explicit spend authorization",
                next_action="Authorize paid execution explicitly or use the free Builder route.",
            )

        status = work_status(mission_id=mission_id)
        if not status.get("ok"):
            status["operation"] = "execution_start"
            return status
        work = status["work"]
        packets = _selected_packets(work, packet_id)
        live = next(
            (packet for packet in packets if packet.get("task_state") in _LIVE_TASK_STATES),
            None,
        )
        if live is not None:
            return receipt(
                "execution_start",
                ok=True,
                state=live.get("task_state"),
                mission_id=mission_id,
                packet_id=live.get("packet_id"),
                task_id=live.get("task_id"),
                existing=True,
                summary="Builder work is already live; no duplicate worker was launched.",
                next_action=(live.get("projection") or {}).get("next_action"),
            )

        mission_state = work.get("state")
        if mission_state == "completed":
            return receipt(
                "execution_start",
                ok=True,
                state="completed",
                mission_id=mission_id,
                existing=True,
                summary="Mission is already complete.",
                next_action="Inspect the verified result or start a new Mission version.",
            )
        if mission_state == "paused":
            return receipt(
                "execution_start",
                ok=False,
                state="paused",
                error_code="mission_paused",
                error="Mission is paused and must be explicitly resumed before execution.",
                next_action="Resolve the pause reason, then call execution_resume.",
            )
        if mission_state == "failed":
            blockers = [
                packet.get("blocked_reason") or packet.get("last_error")
                for packet in packets
                if packet.get("task_state") in {"blocked", "failed", "cancelled"}
            ]
            return receipt(
                "execution_start",
                ok=False,
                state="needs_decision",
                error_code="mission_needs_decision",
                error="Mission has blocked/failed durable state; refusing blind relaunch.",
                next_action="Inspect work_status, recover/resolve the blocker, then resume.",
                blockers=[value for value in blockers if value],
            )

        root = repo_tools.repo_root()
        kitty = root / "kitty"
        if not kitty.exists():
            raise FileNotFoundError(f"Kitty launcher does not exist: {kitty}")
        args = [str(kitty), "builder", "initiative"]
        if packet_id:
            args.extend(["run-packet", mission_id, packet_id])
        else:
            args.extend(["run", mission_id])
        if free:
            args.append("--free")

        log_dir = root / "data" / "kittybuilder" / "mcp-launch"
        log_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"-{packet_id}" if packet_id else ""
        log_path = log_dir / f"{mission_id}{suffix}.log"
        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(
                args,
                cwd=str(root),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
                start_new_session=True,
                close_fds=True,
            )
        return receipt(
            "execution_start",
            ok=True,
            state="launched",
            mission_id=mission_id,
            packet_id=packet_id,
            launcher_pid=process.pid,
            existing=False,
            summary="Builder run loop launched; the MCP request is no longer its owner.",
            next_action="Use work_status/resume_context for durable progress, not launcher narration.",
            log_path=str(log_path.relative_to(root)),
        )
    except Exception as exc:
        return receipt(
            "execution_start",
            ok=False,
            state="unknown",
            error_code="start_failed",
            error=f"{type(exc).__name__}: {exc}",
            next_action="Inspect Builder status before retrying; do not launch another owner blindly.",
        )


def publication_status(
    task_id: str | None = None,
    mission_id: str | None = None,
) -> dict[str, Any]:
    status = work_status(mission_id=mission_id, task_id=task_id)
    if not status.get("ok"):
        status["operation"] = "publication_status"
        return status
    work = status["work"]
    if "task_id" in work:
        publications = [
            {
                "packet_id": work.get("packet_id"),
                "task_id": work.get("task_id"),
                "publication": work.get("publication"),
            }
        ]
    else:
        publications = [
            {
                "packet_id": packet.get("packet_id"),
                "task_id": packet.get("task_id"),
                "publication": packet.get("publication"),
            }
            for packet in work.get("packets") or []
        ]
    return receipt(
        "publication_status",
        ok=True,
        state=status.get("state"),
        publications=publications,
    )


def publication_prepare(
    task_id: str,
    *,
    confirmed: bool = False,
    actor: str = "mcp-client",
) -> dict[str, Any]:
    """Run Builder's operator-gated push/PR path only after explicit confirmation."""
    if not confirmed:
        return receipt(
            "publication_prepare",
            ok=False,
            state="needs_approval",
            error_code="approval_required",
            error=(
                "publication pushes a branch/creates or updates a PR and requires "
                "explicit confirmation"
            ),
            next_action="Confirm publication explicitly after reviewing result/evidence.",
        )
    try:
        _validate_id(task_id, label="task_id")
        result = command_publish(task_id, actor=actor)
        if not result.ok:
            return receipt(
                "publication_prepare",
                ok=False,
                state="blocked",
                error_code="publish_failed",
                error=result.error or result.detail or "Builder publication failed",
                task_id=task_id,
                evidence=result.evidence,
            )
        return receipt(
            "publication_prepare",
            ok=True,
            state="pr_opened",
            task_id=task_id,
            summary=result.detail,
            pr=result.evidence,
            next_action=(
                "Review the PR and required checks; merging remains a separate human action."
            ),
        )
    except Exception as exc:
        return receipt(
            "publication_prepare",
            ok=False,
            state="blocked",
            error_code="publish_failed",
            error=f"{type(exc).__name__}: {exc}",
        )
