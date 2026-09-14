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
* Correlated evidence is resolved by *ownership*: everything attributable to this
  session is one assignment, and a locator belonging to another session's claim is
  a conflict rather than an assignment this session may adopt.
* Participant-wide unread directs are attention, never this session's assignment.
* Untrusted prose stays structurally separate from trusted typed metadata.
* Generation is deterministic and model-free; nothing here calls a provider.
* Nothing here persists derived state, so deleting any briefing artifact cannot
  destroy authoritative source truth.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
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

# When several locators from one session's own evidence agree, the most
# structural one names the assignment: a held claim outranks a handed thread,
# which outranks a bare session match. This only ever picks among the session's
# own evidence, so it can never widen authority.
_ORIGIN_PREFERENCE = {"kx_claim": 0, "thread": 1, "session": 2}

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


# A live GitHub read is a network call, so it is bounded and never implicit.
GITHUB_LOOKUP_TIMEOUT_SECONDS = 20
COORDINATION_ISSUE_NUMBER = 490
_GITHUB_PR_FIELDS = (
    "number,state,headRefOid,url,title,mergedAt,reviewDecision,statusCheckRollup"
)
# Run gh from the checkout so a stdio client launched elsewhere still resolves
# the repository; --repo overrides it when a caller supplies one.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_MAX_ROLLUP_CHECKS = 40
_SUCCESS_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL"})
_FAILURE_CONCLUSIONS = frozenset(
    {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
)
_PENDING_CONCLUSIONS = frozenset(
    {"", "PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "WAITING", "REQUESTED"}
)
_GITHUB_ISSUE_FIELDS = "number,state,title,url,updatedAt,labels"
_GITHUB_FACET_FIELDS = (
    "number",
    "pr_state",
    "issue_state",
    "title",
    "url",
    "review_decision",
    "merged",
    "updated_at",
    "labels",
    "checks",
)


def _normalize_check_rollup(rollup: Any) -> dict[str, Any] | None:
    """Summarize a statusCheckRollup so each required check can be inspected."""
    if not isinstance(rollup, list):
        return None
    counts = {"success": 0, "failure": 0, "pending": 0, "skipped": 0, "other": 0}
    checks: list[dict[str, Any]] = []
    for entry in rollup:
        if not isinstance(entry, dict):
            continue
        conclusion = str(entry.get("conclusion") or entry.get("state") or "").upper()
        if conclusion in _SUCCESS_CONCLUSIONS:
            bucket = "success"
        elif conclusion in _FAILURE_CONCLUSIONS:
            bucket = "failure"
        elif conclusion in _PENDING_CONCLUSIONS:
            bucket = "pending"
        elif conclusion == "SKIPPED":
            bucket = "skipped"
        else:
            bucket = "other"
        counts[bucket] += 1
        name = entry.get("name") or entry.get("context")
        if name:
            checks.append({"name": str(name), "conclusion": conclusion or None})
    return {"counts": counts, "checks": checks[:_MAX_ROLLUP_CHECKS]}


def _run_gh_json(args: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    """Run a bounded ``gh`` read and return ``(payload, error)``. Never raises."""
    if shutil.which("gh") is None:
        return None, "the gh CLI is not installed in this environment"
    env = dict(os.environ)
    # gh must use stored/keyring auth, never an ambient or stale token inherited
    # by this process (repo AGENTS.md requirement, matching builder_publish).
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=GITHUB_LOOKUP_TIMEOUT_SECONDS,
            check=False,
            cwd=str(_REPO_ROOT),
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"gh could not be run: {type(exc).__name__}: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        return None, (detail[0][:200] if detail else f"gh exited {result.returncode}")
    try:
        payload = json.loads(result.stdout or "{}")
    except ValueError as exc:
        return None, f"gh returned unparseable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "gh returned an unexpected payload shape"
    return payload, None


def live_github_lookup(repo: str | None = None):
    """Return a pull-request lookup backed by the ``gh`` CLI.

    Opt-in by construction. Orientation itself never calls this: a caller that
    can afford the network passes the result into
    ``collect_orientation_evidence(github_lookup=...)``, so the default briefing
    stays offline and deterministic.

    The returned callable never raises. A missing ``gh``, a failed query or
    unparseable output all come back as an explicit ``unavailable`` facet
    carrying the reason, so a broken query cannot masquerade as live truth.
    """

    def lookup(number: int) -> dict[str, Any]:
        if not isinstance(number, int) or number <= 0:
            return {
                "state": SOURCE_UNKNOWN,
                "number": number,
                "reason": "a positive pull-request number is required",
            }
        command = ["gh", "pr", "view", str(number), "--json", _GITHUB_PR_FIELDS]
        if repo:
            command += ["--repo", repo]
        payload, error = _run_gh_json(command)
        if error is not None or payload is None:
            return {"state": SOURCE_UNAVAILABLE, "number": number, "reason": error}
        return {
            "state": SOURCE_CURRENT,
            "number": number,
            "head_sha": payload.get("headRefOid"),
            "pr_state": payload.get("state"),
            "title": payload.get("title"),
            "url": payload.get("url"),
            "review_decision": payload.get("reviewDecision"),
            "merged": bool(payload.get("mergedAt")),
            "checks": _normalize_check_rollup(payload.get("statusCheckRollup")),
        }

    return lookup


def live_issue_lookup(repo: str | None = None):
    """Return an issue lookup for coordination markers, backed by ``gh``.

    Separate from the pull-request lookup on purpose: the #490 coordination
    marker is an issue, so ``gh pr view`` is simply the wrong query for it.
    Opt-in and never raises, like its pull-request counterpart.
    """

    def lookup(number: int) -> dict[str, Any]:
        if not isinstance(number, int) or number <= 0:
            return {
                "state": SOURCE_UNKNOWN,
                "number": number,
                "reason": "a positive issue number is required",
            }
        command = ["gh", "issue", "view", str(number), "--json", _GITHUB_ISSUE_FIELDS]
        if repo:
            command += ["--repo", repo]
        payload, error = _run_gh_json(command)
        if error is not None or payload is None:
            return {"state": SOURCE_UNAVAILABLE, "number": number, "reason": error}
        return {
            "state": SOURCE_CURRENT,
            "number": number,
            "issue_state": payload.get("state"),
            "title": payload.get("title"),
            "url": payload.get("url"),
            "updated_at": payload.get("updatedAt"),
            "labels": [
                label.get("name")
                for label in (payload.get("labels") or [])
                if isinstance(label, dict)
            ],
        }

    return lookup


def _github_evidence_item(
    lookup: Any, number: int, locator: str, kind: str
) -> dict[str, Any]:
    """Turn one live GitHub facet into a candidate-bound evidence item."""
    try:
        facet = lookup(number)
    except Exception as exc:  # noqa: BLE001 - contributed as an unavailable item
        facet = {
            "state": SOURCE_UNAVAILABLE,
            "number": number,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(facet, dict):
        facet = {
            "state": SOURCE_UNAVAILABLE,
            "number": number,
            "reason": f"lookup returned {type(facet).__name__}, not a facet",
        }
    item: dict[str, Any] = {
        "source": "github",
        "owner": "github",
        "kind": kind,
        "locator": locator,
        "candidate_ref": facet.get("head_sha"),
    }
    for key in _GITHUB_FACET_FIELDS:
        if facet.get(key) is not None:
            item[key] = facet[key]
    if facet.get("state") != SOURCE_CURRENT:
        item["source_available"] = False
        item["diagnostic"] = facet.get("reason") or f"github reported {facet.get('state')}"
    return item


def _github_evidence_items(
    github_lookup: Any | None,
    issue_lookup: Any | None,
    candidate_pr_numbers: list[int],
    coordination_issue: int | None,
) -> list[dict[str, Any]]:
    """Collect opt-in GitHub evidence: candidate PRs and the coordination marker."""
    items: list[dict[str, Any]] = []
    if github_lookup is not None:
        numbers = sorted(
            {
                int(number)
                for number in candidate_pr_numbers
                if isinstance(number, int) and number > 0
            }
        )
        for number in numbers:
            if number == coordination_issue:
                continue
            items.append(
                _github_evidence_item(github_lookup, number, f"github:pr:{number}", "pull_request")
            )
    if issue_lookup is not None and coordination_issue:
        items.append(
            _github_evidence_item(
                issue_lookup,
                coordination_issue,
                f"github:issue:{coordination_issue}",
                "coordination_marker",
            )
        )
    return items


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


def _claim_locator_index(
    claims: list[dict[str, Any]], session_id: str | None
) -> dict[str, dict[str, Any]]:
    """Map each claim-derived locator to its owning session and lane.

    Separates this session's own evidence from another session's. A locator that
    only ever appears on a foreign claim must never resolve this session's
    assignment. When the same string appears on both, the session's own claim
    wins, so shared values (a branch name, a base SHA) cannot fabricate a
    conflict out of legitimate overlap.
    """
    index: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        lane = claim.get("lane") or claim.get("task_id")
        owner = (
            "own" if session_id and claim.get("session_id") == session_id else "foreign"
        )
        for key in ("id", "lane", "task_id", "branch", "base_sha"):
            value = claim.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            locator = value.strip()
            previous = index.get(locator)
            if previous is None or (previous["owner"] == "foreign" and owner == "own"):
                index[locator] = {"owner": owner, "lane": lane}
    return index


def _correlated_scope(
    message: dict[str, Any],
    tokens: dict[str, str],
    claim_locators: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    correlation = message["_correlation"]
    scope: dict[str, Any] = {
        "locator": correlation["locator"],
        "origin": correlation["origin"],
        "thread_root": message.get("parent_message_id") or message.get("id"),
        "lane": None,
        "candidate_ref": None,
        "owner": "own",
    }
    if correlation["origin"] == "kx_claim":
        claim = claim_locators.get(str(correlation["locator"]))
        scope["lane"] = claim.get("lane") if claim else correlation["locator"]
        scope["owner"] = claim.get("owner") if claim else "foreign"
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
    inbox_error: str | None,
    observed_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    claim_locators = _claim_locator_index(claims, session_id)

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
            "owner": "own",
        }

    for message in correlated:
        scope = _correlated_scope(message, tokens, claim_locators)
        evidence.append(
            _evidence_item(
                "gar_message",
                f"gar:{message.get('id')}",
                _iso(message.get("created_at")) or observed_at,
                correlation_locator=scope["locator"],
                correlation_origin=scope["origin"],
                correlation_owner=scope["owner"],
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
            "owner": "own",
        }

    foreign_scopes = sorted(
        {
            f"{scope['origin']}:{scope['locator']}"
            for scope in scopes.values()
            if scope.get("owner") == "foreign"
        }
    )
    own_lanes = sorted(
        {
            str(claim.get("lane") or claim.get("task_id")).strip()
            for claim in session_claims
            if str(claim.get("lane") or claim.get("task_id") or "").strip()
        }
    )
    own_scopes = [scope for scope in scopes.values() if scope.get("owner") != "foreign"]

    if explicit_scope:
        chosen = scopes[("explicit_scope", "explicit_scope")]
        state = ASSIGNMENT_RESOLVED
        authority_source = "explicit_scope"
        reason = "explicit current user/session scope resolves this assignment"
    elif foreign_scopes:
        chosen = None
        state = ASSIGNMENT_CONFLICTED
        authority_source = None
        reason = (
            "correlated evidence points at locator(s) owned by another session, so this "
            "session cannot adopt it: " + ", ".join(foreign_scopes)
        )
    elif len(own_lanes) > 1:
        chosen = None
        state = ASSIGNMENT_CONFLICTED
        authority_source = None
        reason = (
            "this session holds active claims on more than one lane: "
            + ", ".join(own_lanes)
        )
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
    else:
        chosen = min(own_scopes, key=lambda scope: _ORIGIN_PREFERENCE.get(scope["origin"], 9))
        state = ASSIGNMENT_RESOLVED
        authority_source = chosen["origin"]
        if len(own_scopes) > 1:
            reason = (
                f"exact {chosen['origin']} correlation resolves this assignment; "
                f"{len(own_scopes) - 1} further locator(s) from this session's own "
                "evidence agree instead of conflicting"
            )
        else:
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
            "gateway.agent_coordination.read_current_claims",
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
        "gateway.agent_coordination.read_current_claims",
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
        if item.get("source_available") is False:
            state = SOURCE_UNAVAILABLE
            reason = item.get("diagnostic") or "evidence source unavailable"
        elif not ref:
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
        # The declared event envelope is projected as its own object instead of
        # being flattened into per-type metadata, so a reader can attribute an
        # event to its authority, scope and candidate head without guessing.
        envelope = {
            key: metadata.pop(key)
            for key in agent_workspace.AWARENESS_ENVELOPE_KEYS
            if key in metadata
        }
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
                "envelope": envelope,
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

    assigned_scope = assignment.get("scope") or {}
    assigned_lane = assigned_scope.get("lane")
    # A live claim authorizes only when it is the same lane the assignment
    # resolved to; an unrelated claim must not lend authority to another scope.
    matching_claims = [
        claim
        for claim in session_claims
        if assigned_lane and assigned_lane in {claim.get("lane"), claim.get("task_id")}
    ]

    if explicit_scope:
        action = explicit_scope.get("action") or explicit_scope.get("next_action")
        declared = str(explicit_scope.get("authority") or "user")
        authority_source = "user:explicit_scope" if declared == "user" else f"{declared}:explicit_scope"
        evidence.append(
            _evidence_item("explicit_scope", "explicit_scope", observed_at, authority=declared)
        )
    elif matching_claims:
        claim = matching_claims[0]
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
    elif assignment_resolved:
        missing.append(
            "GAR conversation/presence is evidence, not mutation authority; link an "
            "explicit user/session scope or a matching active KX/Builder authority"
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


def _github_source(evidence: OrientationEvidence, observed_at: str) -> dict[str, Any]:
    """Report GitHub truthfulness from the evidence actually collected.

    A successful opt-in refresh must not still read as ``unknown``, and a partial
    one must not read as healthy: the facet follows the items rather than a
    constant, so the source never contradicts the PR/issue evidence beside it.
    """
    items = [
        item
        for item in (evidence.candidate_evidence or [])
        if item.get("owner") == "github"
    ]
    if not items:
        return _source(
            SOURCE_UNKNOWN,
            "github",
            observed_at,
            diagnostic=(
                "no live GitHub query was performed; publication state requires a refresh"
            ),
        )
    failed = [item for item in items if item.get("source_available") is False]
    if failed:
        return _source(
            SOURCE_UNAVAILABLE,
            "github",
            observed_at,
            diagnostic=(
                failed[0].get("diagnostic") or "a GitHub lookup failed"
            )
            + (f" ({len(failed)} of {len(items)} lookups failed)" if len(failed) > 1 else ""),
            item_count=len(items),
            locators=[item["locator"] for item in items],
        )
    return _source(
        SOURCE_CURRENT,
        "github",
        observed_at,
        item_count=len(items),
        locators=[item["locator"] for item in items],
    )


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

    tokens = _scope_tokens(scope, session_id, claims, thread_root)

    assignment, attention = _resolve_assignment(
        identity=identity,
        session_id=session_id,
        explicit_scope=scope,
        tokens=tokens,
        inbox=inbox,
        thread=thread,
        claims=claims,
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
        "github": _github_source(evidence, observed_at),
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


# Builder states whose task carries a published candidate we can bind to.
_CANDIDATE_TASK_STATES = ("pr_opened", "awaiting_review")


def _collect_candidate_evidence(
    git: dict[str, Any], *, include_builder: bool = True
) -> list[dict[str, Any]]:
    """Gather owner evidence bound to an exact candidate ref.

    Each owner stays authoritative: Git contributes the current candidate head,
    Builder contributes its in-flight published tasks. Nothing is copied into a
    competing store -- these are read surfaces, and the projection binds each
    item to the current head and marks it stale when the candidate moves.

    Git is collected first and unconditionally, so a Builder failure cannot take
    the Git evidence down with it; the Builder failure is contributed as its own
    item carrying the diagnostic. A task that published no ref still contributes
    an item, so an unverifiable binding is visible instead of vanishing.
    """
    items: list[dict[str, Any]] = []

    head = git.get("head")
    if head:
        origin_main = dict(git.get("origin_main") or {})
        items.append(
            {
                "source": "git",
                "owner": "git",
                "kind": "candidate_head",
                "locator": "git:candidate:head",
                "candidate_ref": head,
                "branch": git.get("branch"),
                "origin_main_sha": origin_main.get("sha"),
            }
        )

    if not include_builder:
        return items

    from gateway import builder_queue

    try:
        for state in _CANDIDATE_TASK_STATES:
            for task in builder_queue.list_tasks(state=state):
                task_id = str(task.get("id"))
                links = builder_queue.get_pr_links(task_id)
                latest = links[-1] if links else {}
                items.append(
                    {
                        "source": "gateway.builder_queue",
                        "owner": "builder",
                        "kind": "task_candidate",
                        "locator": f"builder:task:{task_id}",
                        "task_id": task_id,
                        "builder_state": task.get("state"),
                        # The published commit is what the candidate actually is;
                        # workflow_sha is only a fallback because task creation
                        # does not populate it.
                        "candidate_ref": latest.get("head_sha")
                        or task.get("workflow_sha"),
                        "branch": task.get("workflow_ref"),
                        "publication": {
                            "pr_number": latest.get("pr_number"),
                            "pr_url": latest.get("pr_url"),
                            "head_sha": latest.get("head_sha"),
                            "checks_state": latest.get("checks_state"),
                            "review_state": latest.get("review_state"),
                            "merged": bool(latest.get("merged")),
                        }
                        if latest
                        else None,
                    }
                )
    except Exception as exc:  # noqa: BLE001 - contributed as its own item
        items.append(
            {
                "source": "gateway.builder_queue",
                "owner": "builder",
                "kind": "source_error",
                "locator": "builder:queue",
                "candidate_ref": None,
                "diagnostic": f"{type(exc).__name__}: {exc}",
                "source_available": False,
            }
        )

    return items


def collect_orientation_evidence(
    identity: str,
    *,
    session_id: str | None = None,
    thread_or_handoff: str | None = None,
    repo_root: Path | None = None,
    include_builder: bool = True,
    now: datetime | None = None,
    github_lookup: Any | None = None,
    issue_lookup: Any | None = None,
    coordination_issue: int | None = COORDINATION_ISSUE_NUMBER,
) -> OrientationEvidence:
    """Gather read-only authority evidence, degrading explicitly rather than silently.

    ``github_lookup`` is opt-in: orientation performs no network call of its own,
    so the default briefing stays offline and deterministic. Passing
    ``live_github_lookup()`` (or any callable of the same shape) adds GitHub
    PR/check evidence and the coordination marker, each bound to the exact head
    it reports.
    """
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
            github_lookup=github_lookup or _no_remote_github_lookup,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
        evidence.context_receipt_error = f"{type(exc).__name__}: {exc}"

    try:
        evidence.claims = agent_coordination.read_current_claims(now=now)
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

    try:
        receipt = dict(evidence.context_receipt or {})
        candidate_items = _collect_candidate_evidence(
            dict(receipt.get("git") or {}), include_builder=include_builder
        )
        if github_lookup is not None or issue_lookup is not None:
            # Only an explicit caller turns the network on; the candidate PR
            # numbers come from the owners' own records, never from prose.
            candidate_pr_numbers = [
                publication["pr_number"]
                for item in candidate_items
                if isinstance(item.get("publication"), dict)
                and isinstance((publication := item["publication"]).get("pr_number"), int)
            ]
            candidate_items += _github_evidence_items(
                github_lookup, issue_lookup, candidate_pr_numbers, coordination_issue
            )
        evidence.candidate_evidence = candidate_items
    except Exception as exc:  # noqa: BLE001 - attributed as an explicit source failure
        evidence.candidate_evidence_error = f"{type(exc).__name__}: {exc}"

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
    github_lookup: Any | None = None,
    issue_lookup: Any | None = None,
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
        github_lookup=github_lookup,
        issue_lookup=issue_lookup,
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
    items declare a matching locator, and marks them with ``filter_scope`` /
    ``filter_total`` so a narrowed result cannot read as an empty source.
    ``assignment`` always remains the unfiltered domain result.
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
            "candidate_evidence": orientation["candidate_evidence"],
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
        "candidate_evidence": _filter(orientation["candidate_evidence"], "items"),
        "runtime": orientation["runtime"],
        "presence": _filter(orientation["presence"], "sessions"),
        "events": orientation["events"],
        "negative_knowledge": _filter(orientation["negative_knowledge"], "items"),
        "untrusted_evidence": _filter(orientation["untrusted_evidence"], "items"),
        "next_continuation": orientation["next_continuation"],
    }
