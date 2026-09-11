"""Shared deterministic orientation projection for Kitty's cross-agent work.

``gateway.context_receipt`` remains the single public orientation owner. This
module is the bounded implementation beneath that public interface: it turns
read-only authority evidence (Git/GitHub, KX, Builder, runtime, and Global Agent
Room conversation/presence/events) into one structured operating picture, and
exposes Room Briefing as a scoped view of that same result.

Invariants:

* GAR contributes evidence; it is never execution, ownership, or task authority.
* Assignment resolves only from explicit current scope or exact scoped
  thread/handoff/lane/session/candidate correlation; otherwise ``unresolved``.
* Participant-wide unread directs are attention, never this session's assignment.
* Untrusted prose stays structurally separate from trusted typed metadata.
* Generation is deterministic and model-free; nothing here calls a provider.
* Nothing here persists derived state, so deleting any briefing artifact cannot
  destroy authoritative source truth.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway import agent_coordination, agent_workspace

SCHEMA_VERSION = 1

SOURCE_CURRENT = "current"
SOURCE_STALE = "stale"
SOURCE_UNAVAILABLE = "unavailable"
SOURCE_UNKNOWN = "unknown"
SOURCE_STATES = (SOURCE_CURRENT, SOURCE_STALE, SOURCE_UNAVAILABLE, SOURCE_UNKNOWN)

ASSIGNMENT_RESOLVED = "resolved"
ASSIGNMENT_UNRESOLVED = "unresolved"
ASSIGNMENT_CONFLICTED = "conflicted"
ASSIGNMENT_STATES = (ASSIGNMENT_RESOLVED, ASSIGNMENT_UNRESOLVED, ASSIGNMENT_CONFLICTED)

AUTHORITATIVE_AUTHORITIES = ("user:explicit_scope", "kx:claim")

# Trusted callers may supply these. Everything else is untrusted evidence.
UNTRUSTED_KINDS = ("gar_message", "pr_body", "handoff", "log", "issue_comment")

# Message metadata keys that carry prose rather than typed facts.
_UNTRUSTED_METADATA_KEYS = ("content", "text", "body", "message", "prose", "summary")

# Producer metadata keys that would read as directives. They are demoted to
# delimited untrusted text so no machine event can surface an instruction.
_DIRECTIVE_METADATA_KEYS = (
    "instruction",
    "instructions",
    "directive",
    "command",
    "authorization",
    "authority",
    "action",
)

_DO_NOT_REDO = re.compile(r"(?im)^\s*do not redo\b\s*[:\u2014-]?\s*(.*)$")
_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
_PR_REF = re.compile(r"#(\d+)")
_SCOPED_LOCATOR_KEYS = (
    "scope_key",
    "lane",
    "lane_id",
    "session_id",
    "candidate",
    "candidate_ref",
    "pr",
    "pr_ref",
    "head",
    "commit",
    "thread",
    "thread_root",
    "message_id",
    "task",
    "task_id",
)


class OrientationError(RuntimeError):
    """Raised when orientation input is malformed."""


@dataclass
class OrientationEvidence:
    """Read-only evidence bundle gathered from authority read surfaces.

    Tests and callers may construct this directly; that keeps the projection
    deterministic and lets a fixture delete/rebuild derived artifacts without
    touching authoritative state.
    """

    observed_at: str
    context_receipt: dict[str, Any] | None = None
    context_receipt_error: str | None = None
    claims: list[dict[str, Any]] = field(default_factory=list)
    claims_error: str | None = None
    inbox: list[dict[str, Any]] | None = field(default_factory=list)
    inbox_error: str | None = None
    presence: list[dict[str, Any]] | None = field(default_factory=list)
    presence_error: str | None = None
    events: list[dict[str, Any]] | None = field(default_factory=list)
    events_error: str | None = None
    thread: list[dict[str, Any]] | None = None
    thread_error: str | None = None
    candidate_evidence: list[dict[str, Any]] = field(default_factory=list)
    candidate_evidence_error: str | None = None
    untrusted: list[dict[str, Any]] = field(default_factory=list)


def _observed_at(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
        except ValueError:
            return value
    return str(value)


def _source(
    state: str,
    source: str,
    observed_at: str,
    *,
    evidence: list[dict[str, Any]] | None = None,
    diagnostic: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    if state not in SOURCE_STATES:
        raise OrientationError(f"unknown source state: {state!r}")
    section: dict[str, Any] = {
        "state": state,
        "source": source,
        "observed_at": observed_at,
        "evidence": list(evidence or []),
        "diagnostic": diagnostic,
    }
    section.update(extra)
    return section


def _evidence_item(kind: str, locator: str, observed_at: str, **extra: Any) -> dict[str, Any]:
    item = {"kind": kind, "locator": locator, "observed_at": observed_at}
    item.update(extra)
    return item


def _no_remote_github_lookup(number: int) -> dict[str, Any]:
    """Local-only GitHub facet: orientation never fetches.

    A live GitHub query would make orientation non-deterministic and network
    dependent. The candidate/publication section reports ``unknown`` until an
    explicit refresh supplies GitHub truth.
    """
    return {
        "state": SOURCE_UNKNOWN,
        "number": number,
        "reason": "orientation does not query GitHub live; refresh candidate state explicitly",
    }


def _normalize_explicit_scope(value: dict[str, Any] | str | None) -> dict[str, Any] | None:
    """Normalize trusted caller scoping input.

    ``explicit_scope`` is trusted caller input describing the current user or
    session scope. It is never derived from GAR/PR/log/handoff prose.
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return {"action": text, "authority": "user"}
    if not isinstance(value, dict):
        raise OrientationError("explicit_scope must be a string, mapping, or None")
    scope = {str(key): item for key, item in value.items()}
    scope.setdefault("authority", "user")
    return scope


def _scope_tokens(
    explicit_scope: dict[str, Any] | None,
    session_id: str | None,
    claims: list[dict[str, Any]],
    presence: list[dict[str, Any]],
    thread_root: str | None,
) -> dict[str, str]:
    """Return locator -> source-map for exact assignment correlation.

    Only trusted structural locators participate. Untrusted message prose is
    deliberately never scanned for locators, so text cannot self-correlate.
    """
    tokens: dict[str, str] = {}

    def add(value: Any, origin: str) -> None:
        if isinstance(value, str) and value.strip():
            tokens.setdefault(value.strip(), origin)

    if explicit_scope:
        for key in _SCOPED_LOCATOR_KEYS:
            add(explicit_scope.get(key), "explicit_scope")
        action = explicit_scope.get("action")
        if isinstance(action, str) and _looks_like_locator(action):
            add(action, "explicit_scope")
    add(session_id, "session")
    add(thread_root, "thread")
    for claim in claims:
        for key in ("id", "lane", "task_id", "branch", "base_sha"):
            add(claim.get(key), "kx_claim")
    for row in presence:
        for key in ("session_id", "lane_id", "exact_ref"):
            add(row.get(key), "gar_presence")
    return tokens


def _looks_like_locator(value: str) -> bool:
    if _SHA.fullmatch(value.strip()):
        return True
    if _PR_REF.fullmatch(value.strip()):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,}", value.strip()))


def _dedupe_messages(*groups: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return each message once, preserving first-seen order (id-keyed)."""
    seen: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for group in groups:
        for message in group or []:
            if not isinstance(message, dict):
                continue
            message_id = message.get("id")
            if isinstance(message_id, str) and message_id:
                seen.setdefault(message_id, message)
            else:
                anonymous.append(message)
    return list(seen.values()) + anonymous


def _message_scope_map(
    messages: list[dict[str, Any]] | None, tokens: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split messages into exactly-correlated assignment evidence and attention."""
    typed = [item for item in (messages or []) if isinstance(item, dict)]
    correlated: list[dict[str, Any]] = []
    attention: list[dict[str, Any]] = []
    for message in typed:
        matched = None
        for key in ("id", "parent_message_id"):
            value = message.get(key)
            if isinstance(value, str) and value in tokens:
                matched = (value, tokens[value])
                break
        if matched is None:
            attention.append(message)
            continue
        correlated.append({**message, "_correlation": {"locator": matched[0], "origin": matched[1]}})
    return correlated, attention


def _attention_item(message: dict[str, Any], observed_at: str) -> dict[str, Any]:
    recipient = message.get("recipient_id")
    if isinstance(recipient, str) and recipient:
        kind = "participant_wide_direct"
        reason = (
            "direct message addressed to the participant identity, not to this session; "
            "it cannot independently grant this session an assignment or mutation lane"
        )
    else:
        kind = "broadcast_context"
        reason = "participant-wide broadcast is shared context only, never an assignment"
    return {
        "kind": kind,
        "message_id": message.get("id"),
        "sender_id": message.get("sender_id"),
        "sender_kind": message.get("sender_kind"),
        "message_kind": message.get("message_kind"),
        "observed_at": _iso(message.get("created_at")) or observed_at,
        "trust": "untrusted",
        "evidence_locator": f"gar:{message.get('id')}",
        "reason": reason,
    }


def _correlated_scope(
    message: dict[str, Any], tokens: dict[str, str]
) -> dict[str, Any]:
    correlation = message["_correlation"]
    scope: dict[str, Any] = {
        "locator": correlation["locator"],
        "origin": correlation["origin"],
        "thread_root": message.get("parent_message_id") or message.get("id"),
        "lane": None,
        "candidate_ref": None,
    }
    if correlation["origin"] == "kx_claim":
        scope["lane"] = correlation["locator"]
    return scope


def _resolve_assignment(
    *,
    identity: str,
    session_id: str | None,
    explicit_scope: dict[str, Any] | None,
    tokens: dict[str, str],
    inbox: list[dict[str, Any]] | None,
    thread: list[dict[str, Any]] | None,
    claims: list[dict[str, Any]],
    presence: list[dict[str, Any]] | None,
    inbox_error: str | None,
    observed_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    correlated_inbox, attention_messages = _message_scope_map(inbox, tokens)
    correlated_thread, _ = _message_scope_map(thread, tokens)
    correlated = _dedupe_messages(correlated_inbox, correlated_thread)

    evidence: list[dict[str, Any]] = []
    scopes: dict[tuple[str, str], dict[str, Any]] = {}

    if explicit_scope:
        source_origin = "explicit_scope"
        evidence.append(
            _evidence_item(
                "explicit_scope",
                str(explicit_scope.get("scope_key") or "explicit_scope"),
                observed_at,
                authority=str(explicit_scope.get("authority") or "user"),
                action=explicit_scope.get("action"),
            )
        )
        scopes[("explicit_scope", "explicit_scope")] = {
            "locator": explicit_scope.get("scope_key") or "explicit_scope",
            "origin": source_origin,
            "thread_root": explicit_scope.get("thread") or explicit_scope.get("thread_root"),
            "lane": explicit_scope.get("lane") or explicit_scope.get("lane_id"),
            "candidate_ref": explicit_scope.get("candidate_ref") or explicit_scope.get("candidate"),
        }

    for message in correlated:
        scope = _correlated_scope(message, tokens)
        evidence.append(
            _evidence_item(
                "gar_message",
                f"gar:{message.get('id')}",
                _iso(message.get("created_at")) or observed_at,
                correlation_locator=scope["locator"],
                correlation_origin=scope["origin"],
            )
        )
        scopes[(scope["origin"], str(scope["locator"]))] = scope

    session_claims = [
        claim
        for claim in claims
        if session_id and claim.get("session_id") == session_id
    ]
    for claim in session_claims:
        evidence.append(
            _evidence_item(
                "kx_claim",
                f"kx:{claim.get('id')}",
                _iso(claim.get("created_at")) or observed_at,
                role=claim.get("role"),
                resource=claim.get("resource_id"),
                lane=claim.get("lane"),
                expires_at=_iso(claim.get("expires_at")),
            )
        )
        scopes[("kx_claim", str(claim.get("lane") or claim.get("task_id") or claim.get("id")))] = {
            "locator": claim.get("id"),
            "origin": "kx_claim",
            "thread_root": None,
            "lane": claim.get("lane") or claim.get("task_id"),
            "candidate_ref": claim.get("base_sha"),
        }

    if presence and session_id:
        for row in presence:
            if row.get("session_id") != session_id:
                continue
            lane = row.get("lane_id") or row.get("exact_ref")
            if not lane:
                continue
            evidence.append(
                _evidence_item(
                    "gar_presence",
                    f"gar_presence:{row.get('session_id')}",
                    observed_at,
                    presence_state=row.get("presence_state"),
                    lane_id=row.get("lane_id"),
                )
            )
            scopes[("gar_presence", str(row.get("session_id")))] = {
                "locator": row.get("session_id"),
                "origin": "gar_presence",
                "thread_root": None,
                "lane": lane,
                "candidate_ref": row.get("exact_ref"),
            }

    if explicit_scope:
        chosen = scopes[("explicit_scope", "explicit_scope")]
        state = ASSIGNMENT_RESOLVED
        authority_source = "explicit_scope"
        reason = "explicit current user/session scope resolves this assignment"
    elif not scopes:
        chosen = None
        state = ASSIGNMENT_UNRESOLVED
        authority_source = None
        if inbox_error is not None:
            reason = (
                "no explicit scope and GAR conversation evidence was unavailable: "
                f"{inbox_error}"
            )
        else:
            reason = (
                "no explicit scope and no exact scoped thread/handoff/lane/session/"
                "candidate correlation; participant-wide directs are attention only"
            )
    elif len(scopes) > 1:
        chosen = None
        state = ASSIGNMENT_CONFLICTED
        authority_source = None
        reason = (
            "multiple distinct scoped locators correlate to this session: "
            + ", ".join(sorted(f"{key[0]}:{key[1]}" for key in scopes))
        )
    else:
        chosen = next(iter(scopes.values()))
        state = ASSIGNMENT_RESOLVED
        authority_source = chosen["origin"]
        reason = f"exact {chosen['origin']} correlation resolves this assignment"

    attention = [_attention_item(message, observed_at) for message in attention_messages]

    assignment = {
        "state": state,
        "identity": identity,
        "session_id": session_id,
        "scope": chosen,
        "authority_source": authority_source,
        "evidence": evidence,
        "attention": attention if inbox is not None else None,
        "attention_source": "gateway.agent_workspace.list_inbox",
        "reason": reason,
        "note": (
            "participant identity is not assignment identity; presence and "
            "participant-wide directs never grant this session a lane"
        ),
    }
    return assignment, attention


def _project_lanes(
    claims: list[dict[str, Any]], claims_error: str | None, observed_at: str
) -> dict[str, Any]:
    if claims_error is not None:
        return _source(
            SOURCE_UNAVAILABLE,
            "gateway.agent_coordination.list_claims",
            observed_at,
            active=None,
            diagnostic=claims_error,
        )
    active = [
        {
            "session_id": claim.get("session_id"),
            "participant": claim.get("participant"),
            "role": claim.get("role"),
            "resource": claim.get("resource_id"),
            "lane": claim.get("lane"),
            "task": claim.get("task_id"),
            "branch": claim.get("branch"),
            "worktree": claim.get("worktree"),
            "base_sha": claim.get("base_sha"),
            "expires_at": _iso(claim.get("expires_at")),
            "evidence_locator": f"kx:{claim.get('id')}",
        }
        for claim in claims
    ]
    active.sort(key=lambda item: (str(item["resource"]), str(item["session_id"])))
    return _source(
        SOURCE_CURRENT,
        "gateway.agent_coordination.list_claims",
        observed_at,
        active=active,
        issue={
            "ref": "#490",
            "state": SOURCE_UNKNOWN,
            "reason": (
                "the #490 coordination issue is not fetched during deterministic "
                "orientation; live markers require an explicit refresh"
            ),
        },
    )


def _project_builder(
    receipt: dict[str, Any] | None, error: str | None, observed_at: str
) -> dict[str, Any]:
    if error is not None:
        return {
            "state": SOURCE_UNAVAILABLE,
            "source": "gateway.builder_status.build_control_plane_summary",
            "observed_at": observed_at,
            "diagnostic": error,
            "queue": None,
            "initiatives": None,
        }
    builder = dict((receipt or {}).get("builder") or {})
    raw_state = builder.get("state")
    if raw_state == "available":
        state = SOURCE_CURRENT
    elif raw_state == "unavailable":
        state = SOURCE_UNAVAILABLE
    else:
        state = SOURCE_UNKNOWN
    return {
        "state": state,
        "source": builder.get("source") or "gateway.builder_status.build_control_plane_summary",
        "observed_at": observed_at,
        "diagnostic": builder.get("reason"),
        "database": builder.get("database"),
        "queue": builder.get("queue"),
        "initiatives": builder.get("initiatives"),
    }


def _project_candidate(
    receipt: dict[str, Any] | None, error: str | None, observed_at: str
) -> dict[str, Any]:
    if error is not None or not receipt:
        return {
            "state": SOURCE_UNAVAILABLE if error else SOURCE_UNKNOWN,
            "source": "git",
            "observed_at": observed_at,
            "diagnostic": error or "no repository receipt was available",
            "branch": None,
            "head": None,
            "origin_main": None,
            "working_tree": None,
            "publication": None,
        }
    git = dict(receipt.get("git") or {})
    origin_main = git.get("origin_main") or {}
    head = git.get("head")
    origin_relation = origin_main.get("state")
    if head and origin_relation == "available":
        state = SOURCE_CURRENT
    elif head:
        state = SOURCE_UNKNOWN
    else:
        state = SOURCE_UNKNOWN
    return {
        "state": state,
        "source": "git",
        "observed_at": observed_at,
        "diagnostic": origin_main.get("reason"),
        "branch": git.get("branch"),
        "head": head,
        "origin_main": origin_main,
        "working_tree": git.get("working_tree"),
        "publication": {
            "state": SOURCE_UNKNOWN,
            "reason": (
                "no live GitHub query was performed; PR/check/merge state requires "
                "an explicit refresh"
            ),
        },
        "exact_head_binding": True,
        "evidence_locator": "git:HEAD",
    }


def _project_candidate_evidence(
    items: list[dict[str, Any]], head: str | None, observed_at: str
) -> dict[str, Any]:
    """Bind review/validation/publication evidence to the exact candidate head."""
    projected = []
    for item in items:
        ref = item.get("candidate_ref")
        if not ref:
            state = SOURCE_UNKNOWN
            reason = "evidence declares no candidate_ref, so exact-head binding is unknown"
        elif not head:
            state = SOURCE_UNKNOWN
            reason = "current head is unknown, so candidate binding cannot be verified"
        elif str(ref) == str(head):
            state = SOURCE_CURRENT
            reason = "evidence is bound to the current head"
        else:
            state = SOURCE_STALE
            reason = f"candidate mutated: evidence bound to {ref}, head is {head}"
        projected.append({**item, "state": state, "reason": reason, "observed_at": observed_at})
    return {
        "state": SOURCE_CURRENT,
        "source": "builder/github candidate-bound evidence",
        "observed_at": observed_at,
        "items": projected,
    }


def _project_runtime(
    identity: str,
    session_id: str | None,
    presence: list[dict[str, Any]] | None,
    presence_error: str | None,
    observed_at: str,
) -> dict[str, Any]:
    if presence_error is not None:
        return _source(
            SOURCE_UNAVAILABLE,
            "gateway.agent_workspace.list_presence",
            observed_at,
            runtime=None,
            diagnostic=presence_error,
        )
    rows = [row for row in (presence or []) if row.get("participant_id") == identity]
    if session_id is None:
        return _source(
            SOURCE_UNKNOWN,
            "gateway.agent_workspace.list_presence",
            observed_at,
            runtime=None,
            diagnostic="no session_id was provided, so runtime identity is not attributable",
        )
    match = next((row for row in rows if row.get("session_id") == session_id), None)
    if match is None:
        return _source(
            SOURCE_UNKNOWN,
            "gateway.agent_workspace.list_presence",
            observed_at,
            runtime=None,
            diagnostic=f"no live presence session {session_id!r} was observed for {identity!r}",
        )
    presence_state = match.get("presence_state")
    state = SOURCE_CURRENT if presence_state == "active" else SOURCE_STALE
    return _source(
        state,
        "gateway.agent_workspace.list_presence",
        observed_at,
        runtime=match.get("runtime"),
        role=match.get("role"),
        lane_id=match.get("lane_id"),
        exact_ref=match.get("exact_ref"),
        presence_state=presence_state,
        diagnostic=(
            None
            if state == SOURCE_CURRENT
            else f"presence session {session_id!r} is {presence_state!r}"
        ),
    )


def _project_presence(
    presence: list[dict[str, Any]] | None, presence_error: str | None, observed_at: str
) -> dict[str, Any]:
    if presence_error is not None:
        return _source(
            SOURCE_UNAVAILABLE,
            "gateway.agent_workspace.list_presence",
            observed_at,
            sessions=None,
            diagnostic=presence_error,
        )
    sessions = [
        {
            "participant_id": row.get("participant_id"),
            "session_id": row.get("session_id"),
            "runtime": row.get("runtime"),
            "role": row.get("role"),
            "lane_id": row.get("lane_id"),
            "exact_ref": row.get("exact_ref"),
            "declared_status": row.get("declared_status"),
            "presence_state": row.get("presence_state"),
            "heartbeat_at": _iso(row.get("heartbeat_at")),
            "evidence_locator": f"gar_presence:{row.get('session_id')}",
        }
        for row in (presence or [])
    ]
    state = (
        SOURCE_STALE
        if sessions and not any(row["presence_state"] == "active" for row in sessions)
        else SOURCE_CURRENT
    )
    return _source(
        state,
        "gateway.agent_workspace.list_presence",
        observed_at,
        sessions=sessions,
        diagnostic=(
            None
            if state == SOURCE_CURRENT
            else "no observed presence session is currently active"
        ),
        note="presence is liveness only; it never implies assignment or ownership",
    )


def _project_events(
    events: list[dict[str, Any]] | None, events_error: str | None, observed_at: str
) -> dict[str, Any]:
    if events_error is not None:
        return _source(
            SOURCE_UNAVAILABLE,
            "gateway.agent_workspace.list_events",
            observed_at,
            items=None,
            diagnostic=events_error,
            note="machine events are never unread/direct assignments",
        )
    items = []
    for row in events or []:
        metadata = dict(row.get("metadata") or {})
        untrusted_parts: list[str] = []
        typed = {}
        demoted: list[str] = []
        for key, value in sorted(metadata.items()):
            if key in _UNTRUSTED_METADATA_KEYS or key in _DIRECTIVE_METADATA_KEYS:
                if key in _DIRECTIVE_METADATA_KEYS:
                    demoted.append(key)
                untrusted_parts.append(
                    value if isinstance(value, str) else json.dumps(value, sort_keys=True)
                )
            else:
                typed[key] = value
        items.append(
            {
                "event_id": row.get("id"),
                "event_type": row.get("type"),
                "source": "agent_workspace_events",
                "occurred_at": _iso(row.get("created_at")),
                "actor": {"kind": row.get("actor_kind"), "id": row.get("actor_id")},
                "message_id": row.get("message_id"),
                "evidence_locator": f"agent_workspace_events:{row.get('id')}",
                "trusted_metadata": typed,
                "untrusted_text": "\n".join(untrusted_parts) if untrusted_parts else None,
                "demoted_metadata_keys": sorted(demoted),
                "is_assignment": False,
            }
        )
    return _source(
        SOURCE_CURRENT,
        "gateway.agent_workspace.list_events",
        observed_at,
        items=items,
        note="machine events are separate contract types and never direct assignments",
    )


def _negative_knowledge_order(item: dict[str, Any]) -> tuple[int, float, str]:
    """Order negative-knowledge evidence by observation time, then locator."""
    locator = str(item["evidence_locator"])
    try:
        return (0, float(item["_order"]), locator)
    except (TypeError, ValueError):
        return (1, 0.0, locator)


def _project_negative_knowledge(
    messages: list[dict[str, Any]], head: str | None, observed_at: str
) -> dict[str, Any]:
    """Project DO NOT REDO evidence with validity, invalidation, and supersession."""
    extracted: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for match in _DO_NOT_REDO.finditer(content):
            statement = match.group(1).strip() or "(no statement supplied)"
            sha = _SHA.search(statement)
            pr_ref = _PR_REF.search(statement)
            candidate_ref = sha.group(0) if sha else (f"pr:{pr_ref.group(1)}" if pr_ref else None)
            extracted.append(
                {
                    "evidence_locator": f"gar:{message.get('id')}",
                    "scope_key": message.get("parent_message_id") or message.get("id"),
                    "candidate_ref": candidate_ref,
                    "observed_at": _iso(message.get("created_at")) or observed_at,
                    "statement": statement,
                    "trust": "untrusted",
                    "validity_conditions": [
                        "scope_key is unchanged",
                        "candidate_ref still matches the observed candidate",
                    ],
                    "invalidation_conditions": [
                        "a newer DO NOT REDO supersedes this scope",
                        "the candidate changes so candidate_ref no longer matches the head",
                    ],
                    "superseded_by": None,
                    "_order": message.get("created_at") or 0,
                }
            )

    extracted.sort(key=_negative_knowledge_order)
    latest_by_scope: dict[str, str] = {}
    for item in extracted:
        if item["scope_key"] is not None:
            latest_by_scope[str(item["scope_key"])] = str(item["evidence_locator"])
    items = []
    for item in extracted:
        superseded_by = None
        scope_key = item["scope_key"]
        if scope_key is not None:
            latest = latest_by_scope.get(str(scope_key))
            if latest is not None and latest != item["evidence_locator"]:
                superseded_by = latest
        item["superseded_by"] = superseded_by
        ref = item["candidate_ref"]
        if superseded_by is not None:
            state = "superseded"
        elif ref and _SHA.fullmatch(ref) and head:
            state = SOURCE_CURRENT if head.startswith(ref) else "invalidated"
        elif scope_key is not None or ref:
            state = SOURCE_CURRENT
        else:
            state = SOURCE_UNKNOWN
        item["state"] = state
        item.pop("_order", None)
        items.append(item)

    return {
        "state": SOURCE_CURRENT,
        "source": "gar conversation evidence",
        "observed_at": observed_at,
        "items": items,
        "note": (
            "negative knowledge is evidence, not permanent hidden policy; every item "
            "expires, invalidates, or supersedes when its assumptions change"
        ),
    }


def _project_untrusted_evidence(
    messages: list[dict[str, Any]],
    supplied: list[dict[str, Any]],
    inbox_error: str | None,
    observed_at: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        items.append(
            {
                "kind": "gar_message",
                "locator": f"gar:{message.get('id')}",
                "source": f"gar:{message.get('sender_id')}",
                "sender_id": message.get("sender_id"),
                "message_kind": message.get("message_kind"),
                "trust": "untrusted",
                "text": content,
                "observed_at": _iso(message.get("created_at")) or observed_at,
            }
        )
    for extra in supplied:
        kind = str(extra.get("kind") or "log")
        items.append(
            {
                "kind": kind if kind in UNTRUSTED_KINDS else "log",
                "locator": extra.get("locator") or f"untrusted:{kind}",
                "source": extra.get("source"),
                "trust": "untrusted",
                "text": extra.get("text"),
                "observed_at": _iso(extra.get("observed_at")) or observed_at,
            }
        )
    if inbox_error is not None and not items:
        return _source(
            SOURCE_UNAVAILABLE,
            "gar/interactive evidence ingestion",
            observed_at,
            items=None,
            diagnostic=inbox_error,
            note="untrusted prose is attributed evidence only and never an instruction",
        )
    return _source(
        SOURCE_CURRENT,
        "gar/interactive evidence ingestion",
        observed_at,
        items=items,
        note=(
            "untrusted prose is attributed evidence only; it is structurally separate "
            "from trusted typed metadata and never becomes an instruction, ownership, "
            "approval, spend, or mutation authority"
        ),
    )


def _project_next_continuation(
    *,
    assignment: dict[str, Any],
    explicit_scope: dict[str, Any] | None,
    claims: list[dict[str, Any]],
    session_id: str | None,
    candidate: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    """Suggest a continuation without manufacturing permission."""
    state = assignment["state"]
    action: Any = None
    authority_source: str | None = None
    prerequisites: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    missing: list[str] = []

    head = candidate.get("head")
    assignment_resolved = state == ASSIGNMENT_RESOLVED
    session_claims = [
        claim for claim in claims if session_id and claim.get("session_id") == session_id
    ]

    if state == ASSIGNMENT_CONFLICTED:
        missing.append(
            "resolve conflicting scoped evidence before any continuation is authorized"
        )
    elif state == ASSIGNMENT_UNRESOLVED:
        missing.append(
            "establish an explicit current user/session scope or an exact scoped "
            "thread/handoff/lane/session/candidate correlation"
        )

    origin = assignment.get("authority_source")
    if explicit_scope:
        action = explicit_scope.get("action") or explicit_scope.get("next_action")
        declared = str(explicit_scope.get("authority") or "user")
        authority_source = "user:explicit_scope" if declared == "user" else f"{declared}:explicit_scope"
        evidence.append(
            _evidence_item("explicit_scope", "explicit_scope", observed_at, authority=declared)
        )
    elif origin == "kx_claim" and session_claims:
        claim = session_claims[0]
        action = claim.get("task_id") or claim.get("lane")
        authority_source = "kx:claim"
        evidence.append(
            _evidence_item(
                "kx_claim",
                f"kx:{claim.get('id')}",
                observed_at,
                role=claim.get("role"),
                resource=claim.get("resource_id"),
            )
        )
    elif origin in {"gar_thread", "gar_presence"}:
        authority_source = None
        missing.append(
            "GAR conversation/presence is evidence, not mutation authority; link an "
            "explicit user/session scope or an active KX/Builder authority"
        )

    authoritative = authority_source in AUTHORITATIVE_AUTHORITIES
    prerequisites.append(
        {
            "name": "assignment_resolved",
            "satisfied": assignment_resolved,
            "source": "orientation.assignment",
            "evidence": assignment.get("scope"),
            "reason": None if assignment_resolved else assignment.get("reason"),
        }
    )
    prerequisites.append(
        {
            "name": "authority_is_authoritative",
            "satisfied": authoritative,
            "source": "orientation.assignment.authority_source",
            "evidence": authority_source,
            "reason": None if authoritative else "no owning authority is proven for this action",
        }
    )
    head_known = bool(head)
    prerequisites.append(
        {
            "name": "candidate_is_known",
            "satisfied": head_known,
            "source": "git:HEAD",
            "evidence": head,
            "reason": None if head_known else "current candidate head is unknown",
        }
    )

    if not authoritative:
        authorized: Any = False if assignment_resolved else SOURCE_UNKNOWN
    elif all(item["satisfied"] for item in prerequisites):
        authorized = True
    else:
        authorized = SOURCE_UNKNOWN
        for item in prerequisites:
            if not item["satisfied"]:
                missing.append(f"unproven prerequisite: {item['name']}")

    # A declared scope is not a declared action. Without a concrete action from
    # the owning authority there is nothing to authorize.
    if action is None:
        authorized = SOURCE_UNKNOWN
        missing.append(
            "no concrete continuation action was declared by the owning authority"
        )

    return {
        "action": action,
        "authority_source": authority_source,
        "authorized": authorized,
        "prerequisites": prerequisites,
        "evidence": evidence,
        "missing": sorted(set(missing)),
        "note": (
            "authorized=true is legal only when the owning authority and every "
            "required prerequisite are explicitly proven"
        ),
    }


def assemble_orientation(
    identity: str,
    *,
    session_id: str | None,
    explicit_scope: dict[str, Any] | str | None,
    thread_or_handoff: str | None,
    evidence: OrientationEvidence,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project an evidence bundle into the shared orientation result."""
    if not isinstance(identity, str) or not identity.strip():
        raise OrientationError("identity must be a non-empty string")
    identity = identity.strip()
    observed_at = evidence.observed_at or _observed_at(now)

    scope = _normalize_explicit_scope(explicit_scope)

    inbox = evidence.inbox
    thread = evidence.thread
    presence = evidence.presence
    events = evidence.events
    claims = list(evidence.claims)

    conversation = _dedupe_messages(inbox, thread)
    thread_error: str | None
    if thread_or_handoff and not evidence.thread_error and not thread:
        thread_error = f"no messages were found for locator {thread_or_handoff!r}"
    else:
        thread_error = evidence.thread_error

    thread_root = None
    if thread:
        root = next((row for row in thread if not row.get("parent_message_id")), thread[0])
        thread_root = root.get("id")

    tokens = _scope_tokens(scope, session_id, claims, presence or [], thread_root)

    assignment, attention = _resolve_assignment(
        identity=identity,
        session_id=session_id,
        explicit_scope=scope,
        tokens=tokens,
        inbox=inbox,
        thread=thread,
        claims=claims,
        presence=presence,
        inbox_error=evidence.inbox_error,
        observed_at=observed_at,
    )

    receipt = evidence.context_receipt
    candidate = _project_candidate(receipt, evidence.context_receipt_error, observed_at)
    head = candidate.get("head")

    presence_section = _project_presence(presence, evidence.presence_error, observed_at)
    events_section = _project_events(events, evidence.events_error, observed_at)
    if evidence.candidate_evidence_error is None:
        candidate_evidence_section = _project_candidate_evidence(
            evidence.candidate_evidence, head, observed_at
        )
    else:
        candidate_evidence_section = _source(
            SOURCE_UNAVAILABLE,
            "builder/github candidate-bound evidence",
            observed_at,
            items=None,
            diagnostic=evidence.candidate_evidence_error,
        )

    sources = {
        "git": _source(
            candidate["state"],
            "git",
            observed_at,
            diagnostic=candidate.get("diagnostic"),
            branch=candidate.get("branch"),
            head=head,
        ),
        "github": _source(
            SOURCE_UNKNOWN,
            "github",
            observed_at,
            diagnostic=(
                "no live GitHub query was performed; publication state requires a refresh"
            ),
        ),
        "kx": _project_lanes(claims, evidence.claims_error, observed_at),
        "builder": _project_builder(receipt, evidence.context_receipt_error, observed_at),
        "runtime": _project_runtime(
            identity, session_id, presence, evidence.presence_error, observed_at
        ),
        "gar": _source(
            SOURCE_UNAVAILABLE if evidence.inbox_error else SOURCE_CURRENT,
            "gateway.agent_workspace",
            observed_at,
            diagnostic=evidence.inbox_error,
            conversation_count=len(conversation),
            thread_error=thread_error,
        ),
        "presence": presence_section,
        "events": events_section,
    }

    degraded = sorted(
        name for name, section in sources.items() if section["state"] != SOURCE_CURRENT
    )

    orientation = {
        "schema_version": SCHEMA_VERSION,
        "kind": "orientation",
        "identity": identity,
        "session_id": session_id,
        "generated_at": observed_at,
        "evidence_locator": f"orientation:{identity}:{session_id or '-'}:{observed_at}",
        "model_free": True,
        "sources": sources,
        "degraded": degraded,
        "assignment": assignment,
        "attention": attention if inbox is not None else None,
        "lanes": sources["kx"],
        "builder": sources["builder"],
        "candidate": candidate,
        "candidate_evidence": candidate_evidence_section,
        "runtime": sources["runtime"],
        "presence": presence_section,
        "events": events_section,
        "negative_knowledge": _project_negative_knowledge(conversation, head, observed_at),
        "untrusted_evidence": _project_untrusted_evidence(
            conversation, evidence.untrusted, evidence.inbox_error, observed_at
        ),
        "next_continuation": _project_next_continuation(
            assignment=assignment,
            explicit_scope=scope,
            claims=claims,
            session_id=session_id,
            candidate=candidate,
            observed_at=observed_at,
        ),
        "evidence": {
            "receipt_source": "gateway.context_receipt",
            "lanes_source": sources["kx"]["source"],
            "builder_source": sources["builder"]["source"],
            "gar_source": sources["gar"]["source"],
            "observed_at": observed_at,
        },
    }
    return orientation


def collect_orientation_evidence(
    identity: str,
    *,
    session_id: str | None = None,
    thread_or_handoff: str | None = None,
    repo_root: Path | None = None,
    include_builder: bool = True,
    now: datetime | None = None,
) -> OrientationEvidence:
    """Gather read-only authority evidence, degrading explicitly rather than silently."""
    observed_at = _observed_at(now)
    evidence = OrientationEvidence(observed_at=observed_at)

    # Imported lazily: context_receipt remains the public owner and imports this
    # module for its public surface.
    from gateway import context_receipt

    try:
        evidence.context_receipt = context_receipt.build_context_receipt(
            repo_root or context_receipt.ROOT,
            include_builder=include_builder,
            include_legacy_continuity=False,
            github_lookup=_no_remote_github_lookup,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
        evidence.context_receipt_error = f"{type(exc).__name__}: {exc}"

    try:
        evidence.claims = agent_coordination.list_claims(active_only=True)
    except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
        evidence.claims_error = f"{type(exc).__name__}: {exc}"

    try:
        evidence.inbox = agent_workspace.list_inbox(identity, unread_only=True, limit=200)
    except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
        evidence.inbox_error = f"{type(exc).__name__}: {exc}"

    try:
        evidence.presence = agent_workspace.list_presence(identity)
    except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
        evidence.presence_error = f"{type(exc).__name__}: {exc}"

    try:
        evidence.events = agent_workspace.list_events(
            agent_workspace.GLOBAL_WORKSPACE_ID, limit=200
        )
    except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
        evidence.events_error = f"{type(exc).__name__}: {exc}"

    if thread_or_handoff:
        try:
            evidence.thread = agent_workspace.list_thread(thread_or_handoff, limit=200)
        except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
            evidence.thread_error = f"{type(exc).__name__}: {exc}"

    return evidence


def build_orientation_receipt(
    identity: str,
    session_id: str | None = None,
    explicit_scope: dict[str, Any] | str | None = None,
    thread_or_handoff: str | None = None,
    *,
    repo_root: Path | None = None,
    include_builder: bool = True,
    now: datetime | None = None,
    evidence: OrientationEvidence | None = None,
    untrusted_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the shared deterministic orientation projection.

    This is the single cross-authority operating picture. CLI, MCP, hooks, and
    future clients must consume this result instead of reassembling authority
    state themselves. ``evidence`` and ``untrusted_sources`` exist for hermetic
    fixtures and for callers that already hold read-only evidence.
    """
    bundle = evidence or collect_orientation_evidence(
        identity,
        session_id=session_id,
        thread_or_handoff=thread_or_handoff,
        repo_root=repo_root,
        include_builder=include_builder,
        now=now,
    )
    if untrusted_sources:
        bundle = replace(
            bundle,
            untrusted=list(bundle.untrusted) + [dict(item) for item in untrusted_sources],
        )
    return assemble_orientation(
        identity,
        session_id=session_id,
        explicit_scope=explicit_scope,
        thread_or_handoff=thread_or_handoff,
        evidence=bundle,
        now=now,
    )


def build_room_briefing(
    orientation: dict[str, Any],
    *,
    identity: str | None = None,
    session_id: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    """Return a bounded Room Briefing view of one shared orientation result.

    The briefing never recomputes truth. Unscoped briefings pass the domain
    result through by reference; a scope filter only narrows collections whose
    items declare a matching locator.
    """
    if orientation.get("kind") != "orientation":
        raise OrientationError("room briefing requires an orientation result")

    if scope is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "room_briefing",
            "identity": identity or orientation["identity"],
            "session_id": session_id if session_id is not None else orientation["session_id"],
            "scope": None,
            "generated_at": orientation["generated_at"],
            "orientation_evidence_locator": orientation["evidence_locator"],
            "degraded": orientation["degraded"],
            "sources": orientation["sources"],
            "assignment": orientation["assignment"],
            "attention": orientation["attention"],
            "lanes": orientation["lanes"],
            "candidate": orientation["candidate"],
            "runtime": orientation["runtime"],
            "presence": orientation["presence"],
            "events": orientation["events"],
            "negative_knowledge": orientation["negative_knowledge"],
            "untrusted_evidence": orientation["untrusted_evidence"],
            "next_continuation": orientation["next_continuation"],
        }

    def _matches(item: dict[str, Any]) -> bool:
        for key in ("locator", "scope_key", "lane", "candidate_ref", "evidence_locator"):
            value = item.get(key)
            if isinstance(value, str) and value == scope:
                return True
        return False

    def _filter(section: dict[str, Any], key: str) -> dict[str, Any]:
        items = section.get(key)
        if not isinstance(items, list):
            return section
        return {
            **section,
            key: [item for item in items if _matches(item)],
            "filter_scope": scope,
            "filter_total": len(items),
        }

    lanes = orientation["lanes"]
    lane_items = lanes.get("active")
    filtered_lanes = {
        **lanes,
        "active": [item for item in (lane_items or []) if _matches(item)]
        if isinstance(lane_items, list)
        else None,
        "filter_scope": scope,
        "filter_total": len(lane_items) if isinstance(lane_items, list) else None,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "room_briefing",
        "identity": identity or orientation["identity"],
        "session_id": session_id if session_id is not None else orientation["session_id"],
        "scope": scope,
        "generated_at": orientation["generated_at"],
        "orientation_evidence_locator": orientation["evidence_locator"],
        "degraded": orientation["degraded"],
        "sources": orientation["sources"],
        "assignment": orientation["assignment"],
        "attention": [
            item for item in (orientation["attention"] or []) if _matches(item)
        ]
        if orientation["attention"] is not None
        else None,
        "lanes": filtered_lanes,
        "candidate": orientation["candidate"],
        "runtime": orientation["runtime"],
        "presence": _filter(orientation["presence"], "sessions"),
        "events": orientation["events"],
        "negative_knowledge": _filter(orientation["negative_knowledge"], "items"),
        "untrusted_evidence": _filter(orientation["untrusted_evidence"], "items"),
        "next_continuation": orientation["next_continuation"],
    }
