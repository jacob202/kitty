"""Scoped user grants evaluated at the action execution boundary (issue #554).

``config/action_tiers.json`` stays the baseline authority: which action kinds
exist, which are hard-disabled, and the minimum approval floor for each. That is
code/config truth, not user preference.

This module records the *user's* standing decisions on top of that baseline —
allow / ask / deny, bound to a scope, optionally expiring, session-bound, or
capped by a spend ceiling — and answers one question for the action queue:

    may this specific proposal dispatch right now, or must the user be asked?

A grant can authorize an action the baseline would have asked about. It can
never make a disabled kind, a missing executor, or a domain refusal valid:
``action_queue`` checks those first and never reaches this module for them.

Decision precedence, fail-closed (issue #554):

1. hard-disabled / missing executor / domain refusal → deny (enforced upstream)
2. matching explicit scoped deny → deny
3. baseline requires approval and a valid matching standing allow exists → allow
4. valid one-shot approval for this exact proposal → allow
5. otherwise → ask

More specific scope outranks broader scope. Within one specificity, the
fail-closed order deny > ask > allow decides. Expired, revoked, or
tier-escalated grants never authorize.

Public API:
  evaluate(*, capability, tier, status, scope_type, scope_id, session_id,
           estimated_cost_usd, now) -> Decision
  create_grant(*, capability, decision, granted_tier, reason, ...) -> dict
  revoke_grant(grant_id) -> dict
  get_grant(grant_id) -> dict | None
  list_grants(*, capability=None, include_inactive=False, limit=100) -> list[dict]
  record_spend(grant_id, amount_usd) -> dict
  approval_posture(*, project_id=None, session_id=None) -> dict
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

logger = logging.getLogger("kitty.action_grants")

GRANTS_DB_FILE = KITTY_DB_FILE

DECISIONS = frozenset({"allow", "ask", "deny"})

# Only scopes a real action can actually carry. Deliberately a small typed set:
# the issue's non-goals rule out a combinatorial ACL language.
SCOPE_TYPES = frozenset(
    {
        "global",
        "project",
        "repo",
        "site",
        "integration",
        "mcp_server",
        "skill",
        "tool",
        "provider",
        "automation",
        "session",
    }
)

# T0 < T1 < T2. A grant made when a kind was T0 must not silently authorize it
# after the signed sheet escalates it to T2.
_TIER_RANK = {"T0": 0, "T1": 1, "T2": 2}

# Fail-closed ordering used to break ties between grants at the same specificity.
_DECISION_RANK = {"allow": 0, "ask": 1, "deny": 2}

# Grant rows are inspected by the user and summarized into the runtime manifest.
# Bounding them keeps an oversized blob (or pasted secret material) out of both.
_MAX_TEXT = 500

# The manifest's grant summary is inlined into every chat turn's runtime
# context. Cap what is listed and report the remainder as a count.
_MAX_LISTED_GRANTS = 25

_COLUMNS = (
    "id, created_at, capability, decision, scope_type, scope_id, session_id, "
    "granted_tier, expires_at, budget_limit_usd, budget_spent_usd, reason, "
    "created_by, revoked_at"
)


class GrantError(RuntimeError):
    """Base for grant errors."""


class GrantValidationError(GrantError):
    """A grant field is missing or invalid (400-shaped)."""


class GrantNotFound(GrantError):
    """No grant row with that id (404-shaped)."""


@dataclass(frozen=True)
class Decision:
    """The policy layer's answer for one proposal.

    ``outcome`` is the tri-state the action queue acts on. ``basis`` says which
    precedence rule produced it, so a refusal or an auto-execute can be
    explained to the user without re-deriving the evaluation.
    """

    outcome: str  # allow | ask | deny
    basis: str
    reason: str
    grant_id: int | None = None
    # True only when a budget-limited grant authorized this and the executed
    # cost must be charged back to its ceiling. A grant without a ceiling is
    # never charged, so the caller does not need to re-read the row to find out.
    charges_budget: bool = False

    @property
    def allowed(self) -> bool:
        return self.outcome == "allow"


def init_db() -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=GRANTS_DB_FILE)


# --- Evaluation ------------------------------------------------------------


def evaluate(
    *,
    capability: str,
    tier: str,
    status: str,
    scope_type: str = "global",
    scope_id: str = "",
    session_id: str | None = None,
    estimated_cost_usd: float | None = None,
    auto_execute_tiers: frozenset[str] | set[str] = frozenset({"T0", "T1"}),
    now: float | None = None,
) -> Decision:
    """Decide whether this proposal may dispatch now.

    ``tier`` is the tier the signed sheet carries *now*, not the tier stamped on
    the row when it was proposed — the action queue already resolves that, and
    an escalation must gate a queued action rather than be bypassed.
    """
    if tier not in _TIER_RANK:
        raise GrantValidationError(f"unknown risk tier {tier!r}")
    _validate_scope(scope_type, scope_id)
    now = time.time() if now is None else now

    winner = _winning_grant(
        capability=capability,
        scope_type=scope_type,
        scope_id=scope_id,
        session_id=session_id,
        tier=tier,
        now=now,
    )

    if winner is None:
        return _baseline_decision(tier, status, auto_execute_tiers)

    decision = winner["decision"]
    grant_id = winner["id"]
    where = _scope_label(winner["scope_type"], winner["scope_id"])

    if decision == "deny":
        # Above one-shot approval on purpose: a scoped "never allow here" must
        # not be defeated by approving the individual proposal.
        return Decision(
            "deny",
            "scoped_deny",
            f"{capability} is denied for {where}",
            grant_id,
        )

    if decision == "ask":
        # An explicit "ask every time" suppresses any broader standing allow,
        # but the user approving this exact proposal still authorizes it.
        if status == "approved":
            return Decision(
                "allow",
                "one_shot_approval",
                f"approved for this proposal; {capability} still asks for {where}",
                grant_id,
            )
        return Decision(
            "ask",
            "scoped_ask",
            f"{capability} asks every time for {where}",
            grant_id,
        )

    return _allow_within_budget(winner, capability, where, estimated_cost_usd)


def _baseline_decision(
    tier: str, status: str, auto_execute_tiers: frozenset[str] | set[str]
) -> Decision:
    """No grant matched: fall back to the signed sheet's own policy."""
    if tier in auto_execute_tiers:
        return Decision("allow", "baseline_tier", f"{tier} executes without approval")
    if status == "approved":
        return Decision("allow", "one_shot_approval", f"{tier} approved for this proposal")
    return Decision("ask", "baseline_tier", f"{tier} requires approval")


def _allow_within_budget(
    grant: dict[str, Any],
    capability: str,
    where: str,
    estimated_cost_usd: float | None,
) -> Decision:
    """Apply a standing allow, failing closed for spend-capped grants.

    Proposal-supplied estimates are advisory data, not spending authority. Until
    the executor/provider supplies a server-owned estimate and reconciles actual
    cost, a budget-limited grant can never auto-authorize dispatch.
    """
    grant_id = grant["id"]
    limit = grant["budget_limit_usd"]
    if limit is None:
        return Decision("allow", "standing_grant", f"{capability} allowed for {where}", grant_id)

    return Decision(
        "ask",
        "budget_requires_authoritative_cost",
        f"{capability} is allowed for {where} up to ${limit:.2f}, but paid "
        "execution requires server-owned cost authority and reconciliation",
        grant_id,
    )


def _winning_grant(
    *,
    capability: str,
    scope_type: str,
    scope_id: str,
    session_id: str | None,
    tier: str,
    now: float,
) -> dict[str, Any] | None:
    """Most specific applicable grant, fail-closed within a specificity tier."""
    candidates = [
        grant
        for grant in _active_grants(capability, now)
        if _applies(
            grant,
            scope_type=scope_type,
            scope_id=scope_id,
            session_id=session_id,
            tier=tier,
        )
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda g: (
            _specificity(g),
            _is_session_bound(g),
            _DECISION_RANK[g["decision"]],
            g["id"],
        ),
    )


def _applies(
    grant: dict[str, Any],
    *,
    scope_type: str,
    scope_id: str,
    session_id: str | None,
    tier: str,
) -> bool:
    if not _scope_matches(grant, scope_type=scope_type, scope_id=scope_id):
        return False
    if grant["session_id"] is not None and grant["session_id"] != session_id:
        return False
    if grant["decision"] == "allow" and _TIER_RANK[tier] > _TIER_RANK[grant["granted_tier"]]:
        # The kind is riskier now than when the user granted it. Restrictions
        # (deny/ask) still apply; only the permission lapses.
        logger.info(
            "grant %s no longer authorizes %s: tier escalated %s -> %s",
            grant["id"],
            grant["capability"],
            grant["granted_tier"],
            tier,
        )
        return False
    return True


def _scope_matches(
    grant: dict[str, Any], *, scope_type: str, scope_id: str
) -> bool:
    """Match the small hierarchy needed by MCP without becoming a generic ACL.

    Tool targets use the canonical ``<server>/<tool>`` id. A server grant
    therefore applies to all tools under that server, while an exact tool grant
    is more specific and can override it (for example allow server, deny delete).
    Other scope types remain exact-match only.
    """
    grant_type = grant["scope_type"]
    grant_id = grant["scope_id"]
    if grant_type == "global":
        return True
    if grant_type == scope_type and grant_id == scope_id:
        return True
    if grant_type == "mcp_server" and scope_type == "tool":
        server, sep, _tool = scope_id.partition("/")
        return bool(sep) and server == grant_id
    return False


def _specificity(grant: dict[str, Any]) -> int:
    """Scope-type narrowness only. Session binding is a separate, strictly
    lower-priority tie-break (see :func:`_is_session_bound`) — it must never
    let a session-scoped grant at a broader scope outrank a narrower one that
    isn't session-bound (AUTH-002)."""
    if grant["scope_type"] == "global":
        return 0
    elif grant["scope_type"] == "mcp_server":
        return 1
    elif grant["scope_type"] == "tool":
        return 2
    else:
        return 1


def _is_session_bound(grant: dict[str, Any]) -> bool:
    """Tie-break only within one scope-specificity rank: between two grants
    at the same scope narrowness, prefer the one scoped to this session."""
    return grant["session_id"] is not None


def _scope_label(scope_type: str, scope_id: str) -> str:
    return scope_type if scope_type == "global" else f"{scope_type} {scope_id!r}"


# --- Storage ---------------------------------------------------------------


def create_grant(
    *,
    capability: str,
    decision: str,
    granted_tier: str,
    reason: str,
    scope_type: str = "global",
    scope_id: str = "",
    session_id: str | None = None,
    expires_at: float | None = None,
    budget_limit_usd: float | None = None,
    created_by: str,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Record one standing decision with explicit provenance.

    A permission-widening ``allow`` is accepted only from a user-confirmed
    boundary. Gateway bearer authentication alone is intentionally insufficient.
    """
    capability = _require_text(capability, "capability")
    reason = _require_text(reason, "reason")
    created_by = _require_text(created_by, "created_by")
    if decision not in DECISIONS:
        raise GrantValidationError(f"decision must be one of {sorted(DECISIONS)}, got {decision!r}")
    if granted_tier not in _TIER_RANK:
        raise GrantValidationError(f"unknown granted_tier {granted_tier!r}")
    if decision == "allow" and not (created_by == "user" and user_confirmed):
        raise GrantValidationError(
            "standing allow requires an explicit user-confirmed approval boundary"
        )
    _validate_scope(scope_type, scope_id)
    if session_id is not None:
        session_id = _require_text(session_id, "session_id")
    if expires_at is not None and expires_at <= time.time():
        raise GrantValidationError("expires_at must be in the future")
    if budget_limit_usd is not None:
        if budget_limit_usd <= 0:
            raise GrantValidationError("budget_limit_usd must be positive")
        if decision != "allow":
            raise GrantValidationError("only an allow grant can carry a budget ceiling")

    init_db()
    with kitty_db.connect(GRANTS_DB_FILE) as conn:
        cursor = conn.execute(
            "INSERT INTO action_grants (capability, decision, scope_type, scope_id, "
            "session_id, granted_tier, expires_at, budget_limit_usd, reason, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                capability,
                decision,
                scope_type,
                scope_id,
                session_id,
                granted_tier,
                expires_at,
                budget_limit_usd,
                reason,
                created_by,
            ),
        )
        conn.commit()
        grant_id = cursor.lastrowid
    if grant_id is None:
        raise GrantError("insert did not return a row id")
    return _require(grant_id)


def grant_from_approved_action(
    action: dict[str, Any],
    *,
    expires_at: float | None = None,
    session_only: bool = False,
) -> dict[str, Any]:
    """Mint the standing allow behind the UI's "always allow here" choice.

    This is the user-confirmed boundary :func:`create_grant` demands, and the
    only way a permission-widening grant can be created in production. It is
    reachable solely from the approve route, after ``action_queue.approve()``
    has moved a genuinely ``proposed`` row to ``approved`` — so a caller cannot
    mint an allow without a real proposal the user acted on.

    Every field that decides what is permitted is read off the action row, never
    supplied by the caller: capability, risk tier and scope come from the
    proposal, and the reason is the preview the user was actually shown. A
    client approving a ``todo.create`` for one project therefore cannot walk
    away holding a global ``email.send`` grant.

    The caller chooses only how long it lasts. There is deliberately no way to
    widen the scope past the action's own — "here" means where the approved
    action was, and nowhere else.
    """
    capability = _require_text(action.get("kind"), "action kind")
    granted_tier = _require_text(action.get("risk_tier"), "action risk_tier")
    if action.get("status") != "approved":
        raise GrantValidationError(
            "a standing allow can only be remembered from an approved action, "
            f"got status {action.get('status')!r}"
        )

    session_id = action.get("session_id")
    if session_only and not session_id:
        raise GrantValidationError(
            "this action carries no session, so the grant cannot be limited to one"
        )

    return create_grant(
        capability=capability,
        decision="allow",
        granted_tier=granted_tier,
        reason=_remember_reason(action),
        scope_type=str(action.get("scope_type") or "global"),
        scope_id=str(action.get("scope_id") or ""),
        session_id=session_id if session_only else None,
        expires_at=expires_at,
        created_by="user",
        user_confirmed=True,
    )


def _remember_reason(action: dict[str, Any]) -> str:
    """The preview the user saw, trimmed to the column's bound."""
    preview = str(action.get("preview") or "").strip()
    if not preview:
        preview = f"approved {action.get('kind')} action {action.get('id')}"
    return preview[:_MAX_TEXT]


def revoke_grant(grant_id: int) -> dict[str, Any]:
    """Stop a grant authorizing anything from now on. Past receipts stay."""
    grant = _require(grant_id)
    if grant["revoked_at"] is not None:
        return grant
    init_db()
    with kitty_db.connect(GRANTS_DB_FILE) as conn:
        conn.execute(
            "UPDATE action_grants SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (time.time(), grant_id),
        )
        conn.commit()
    return _require(grant_id)


def record_spend(grant_id: int, amount_usd: float) -> dict[str, Any]:
    """Reserve spend against a budget-limited grant, before the side effect runs.

    Conditioned on the ceiling inside the UPDATE, so two executions that both
    passed :func:`evaluate` cannot together spend past it — the second one's
    reservation fails and its action never dispatches.

    Callers reserve first and :func:`release_spend` on failure. Charging after
    dispatch instead would let that same pair overspend by one action's cost:
    both would pass the check, both would run, and only one charge would land.
    Over-reserving briefly is the safe direction for money; under-charging is
    not.
    """
    if amount_usd < 0:
        raise GrantValidationError("amount_usd must not be negative")
    grant = _require(grant_id)
    if grant["budget_limit_usd"] is None:
        raise GrantValidationError(f"grant {grant_id} carries no budget ceiling")

    init_db()
    with kitty_db.connect(GRANTS_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE action_grants SET budget_spent_usd = budget_spent_usd + ? "
            "WHERE id = ? AND budget_spent_usd + ? <= budget_limit_usd",
            (amount_usd, grant_id, amount_usd),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise GrantValidationError(
                f"grant {grant_id} cannot absorb ${amount_usd:.2f}: "
                f"${grant['budget_spent_usd']:.2f} of ${grant['budget_limit_usd']:.2f} used"
            )
    return _require(grant_id)


def release_spend(grant_id: int, amount_usd: float) -> dict[str, Any]:
    """Return a reservation whose side effect did not happen.

    Floored at zero so a double release cannot manufacture budget the user
    never granted.
    """
    if amount_usd < 0:
        raise GrantValidationError("amount_usd must not be negative")
    _require(grant_id)

    init_db()
    with kitty_db.connect(GRANTS_DB_FILE) as conn:
        conn.execute(
            "UPDATE action_grants SET budget_spent_usd = MAX(0, budget_spent_usd - ?) "
            "WHERE id = ?",
            (amount_usd, grant_id),
        )
        conn.commit()
    return _require(grant_id)


def get_grant(grant_id: int) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(GRANTS_DB_FILE) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM action_grants WHERE id = ?", (grant_id,)
        ).fetchone()
    return _row_to_grant(row) if row else None


def list_grants(
    *,
    capability: str | None = None,
    include_inactive: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Grants newest first. Active-only unless ``include_inactive``."""
    init_db()
    clauses: list[str] = []
    params: list[Any] = []
    if capability is not None:
        clauses.append("capability = ?")
        params.append(capability)
    if not include_inactive:
        clauses.append("revoked_at IS NULL")
        clauses.append("(expires_at IS NULL OR expires_at > ?)")
        params.append(time.time())
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with kitty_db.connect(GRANTS_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM action_grants{where} ORDER BY id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [_row_to_grant(row) for row in rows]


def approval_posture(
    *,
    project_id: str | None = None,
    session_id: str | None = None,
    max_listed: int = _MAX_LISTED_GRANTS,
) -> dict[str, Any]:
    """Effective grant posture for the runtime manifest.

    Summarized, never secrets. This lands in every chat turn's runtime context,
    so the list is capped and the overflow is reported as a count — inlining an
    unbounded fact here is what once cost ~107k tokens a turn on the Builder
    snapshot. Truncation is stated, never silent.
    """
    grants = list_grants(limit=200)
    relevant = [
        grant
        for grant in grants
        if grant["scope_type"] == "global"
        or (project_id is not None and _matches(grant, "project", project_id))
        or (session_id is not None and grant["session_id"] == session_id)
    ]
    posture: dict[str, Any] = {
        "grant_count": len(grants),
        "relevant_grant_count": len(relevant),
        "relevant_grants": [_summarize(grant) for grant in relevant[:max_listed]],
    }
    if len(relevant) > max_listed:
        posture["truncated"] = len(relevant) - max_listed
    return posture


def _matches(grant: dict[str, Any], scope_type: str, scope_id: str) -> bool:
    return grant["scope_type"] == scope_type and grant["scope_id"] == scope_id


def _summarize(grant: dict[str, Any]) -> dict[str, Any]:
    """Manifest-safe view: what is permitted where, not why or by whom."""
    return {
        "id": grant["id"],
        "capability": grant["capability"],
        "decision": grant["decision"],
        "scope": _scope_label(grant["scope_type"], grant["scope_id"]),
        "expires_at": grant["expires_at"],
        "budget_limit_usd": grant["budget_limit_usd"],
        "budget_spent_usd": grant["budget_spent_usd"],
    }


# --- Internals -------------------------------------------------------------


def _active_grants(capability: str, now: float) -> list[dict[str, Any]]:
    init_db()
    with kitty_db.connect(GRANTS_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM action_grants WHERE capability = ? "
            "AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)",
            (capability, now),
        ).fetchall()
    return [_row_to_grant(row) for row in rows]


def _require(grant_id: int) -> dict[str, Any]:
    grant = get_grant(grant_id)
    if grant is None:
        raise GrantNotFound(f"no grant with id {grant_id}")
    return grant


def validate_scope(scope_type: str, scope_id: str) -> None:
    """Raise :class:`GrantValidationError` unless this is a scope a grant can match.

    Public so a proposer can reject a bad scope at propose time rather than
    storing a row no grant will ever apply to.
    """
    _validate_scope(scope_type, scope_id)


def _validate_scope(scope_type: str, scope_id: str) -> None:
    if scope_type not in SCOPE_TYPES:
        raise GrantValidationError(
            f"scope_type must be one of {sorted(SCOPE_TYPES)}, got {scope_type!r}"
        )
    if scope_type == "global":
        if scope_id:
            raise GrantValidationError("the global scope takes no scope_id")
        return
    if not isinstance(scope_id, str) or not scope_id.strip():
        raise GrantValidationError(f"scope_type {scope_type!r} requires a non-empty scope_id")
    if len(scope_id) > _MAX_TEXT:
        raise GrantValidationError(f"scope_id must be at most {_MAX_TEXT} characters")


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GrantValidationError(f"{field} must be a non-empty string")
    if len(value) > _MAX_TEXT:
        raise GrantValidationError(f"{field} must be at most {_MAX_TEXT} characters")
    return value


def _row_to_grant(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "capability": row["capability"],
        "decision": row["decision"],
        "scope_type": row["scope_type"],
        "scope_id": row["scope_id"],
        "session_id": row["session_id"],
        "granted_tier": row["granted_tier"],
        "expires_at": row["expires_at"],
        "budget_limit_usd": row["budget_limit_usd"],
        "budget_spent_usd": row["budget_spent_usd"],
        "reason": row["reason"],
        "created_by": row["created_by"],
        "revoked_at": row["revoked_at"],
    }
