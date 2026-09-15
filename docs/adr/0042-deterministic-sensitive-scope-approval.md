# ADR-0042: Deterministic Approval for Sensitive Scope; Human Approval Reserved for Irreversible Scope

**Status:** Accepted
**Date:** 2026-09-15

## Context

Sensitive pull requests required three things: a `risk/approved` label, an
exact-head body line, and trusted independent review. The first two are a human
signature on every sensitive change, and they have three problems that together
made them worse than useless.

**The signature is not attributable.** [ADR 0041](0041-attributable-agent-identity.md)
records this in full: `_exact_head_approval` parses text from the mutable PR body,
which carries no editor provenance, and every actor in this repository —
including every agent acting on Jacob's behalf — authenticates as `jacob202`. The
gate cannot tell who wrote the line. A rule that cannot distinguish a human
decision from an agent's is not a human control; it is a discipline requirement
wearing a gate's clothes.

**The signature is phrasing-defeatable.** `scripts/pr_policy.py` matches
`^Risk approval:\s*APPROVE <sha>\s+[—-]\s+(.+)$` and only requires a non-empty
reason. PR #877 carried the line `Risk approval: APPROVE <sha> — I do not accept
this risk yet: ...` for a full day and the check read it as consent. A rejection
sentence is an approval to this parser.

**It blocked on the one person it cannot serve.** Kitty is a local-first
single-user product (ADR 0002). There is no second human to review, so the
control's cost landed entirely on the operator, who by his own statement will not
and does not want to perform it — and, in practice, bypassed the local gate with
`--no-verify` to make progress.

The independent-review half of the requirement is different: it is
machine-checkable, actor-bound, and pinned to the exact 40-character head SHA, so
it is kept. It is also unreliable at the sizes this repository produces — two
consecutive reviews of PR #877 (133 files, four ~59 KB chunks) produced no verdict
at all (non-JSON narration, then a model timeout) — which is a reviewer-reliability
problem to fix separately, not a reason to reinstate the human signature.

## Decision

Split sensitive scope into two tiers, both derived from the one canonical
classifier in `scripts/pr_scope.py`.

**Sensitive and reversible** — the Builder control plane, action/approval
boundaries, and other broad-scope work in the `RISK_PATTERNS` set — requires
trusted exact-head independent review and nothing else. It clears
deterministically and never waits on a human signature.

**Irreversible** — the `IRREVERSIBLE_PATTERNS` subset: credentials, auth and
security, secrets/env, spend controls (`compute_governor`, `providers`,
`paid_review_admission`, `model_routing`), purge/destructive paths, dependency
roots, and the review gate and CI themselves — additionally requires
`risk/approved` and the exact-head approval line.

The line is drawn at changes a later commit cannot simply undo, or that move
money, credentials, or the delivery pipeline itself. Human attestation is
reserved for the places where an automatic reversal is not available.

## Consequences

**Easier.** Ordinary broad-scope work is no longer gated on a ritual that the
sole operator does not perform. The remaining human gate is smaller, so it can be
taken seriously rather than reflexively satisfied. `AGENTS.md` T2 no longer lists
"broad scope"; it lists the irreversible subset.

**Harder.** The approval-regex footgun remains (a rejection formatted as
`APPROVE <sha> — ...` still parses as consent) and is deliberately left as a
separate change, because fixing the parser does not fix attributability and the
attributability fix is ADR 0041's job.

**Unchanged.** Independent review remains required for all sensitive scope, and
the `review/override-approved` exact-head escape hatch still exists for genuine
reviewer outages.

**Not addressed here.** Reviewer reliability on large diffs. Until it is fixed, a
large sensitive PR can be blocked by the reviewer failing to produce a verdict
rather than by a finding. The honest options are to shrink the diff or to treat
an absent verdict as advisory; choosing between them is a separate decision and
is not smuggled in here.

## Alternatives considered

**Keep the human signature for all sensitive scope.** Rejected. It is
unattributable (ADR 0041), phrasing-defeatable, and its cost falls entirely on
a single operator who does not perform it — so it produced friction and a false
audit trail rather than control.

**Remove the human signature entirely.** Rejected. Credentials, spend, and
destructive paths are the cases where a machine cannot undo the consequence, and
those should keep an explicit human decision once ADR 0041 makes one detectable.

**Make the signature deterministic without narrowing it.** Rejected. Requiring a
signature that no one can check while allowing a rejection sentence to satisfy it
is strictly worse than being honest that broad-scope work is governed by review.
