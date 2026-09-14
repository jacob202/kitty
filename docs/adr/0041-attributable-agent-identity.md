# ADR-0041: Attributable Agent Identity for Human-Only Controls

**Status:** Proposed — awaiting Jacob's decision
**Date:** 2026-09-13

## Context

Sensitive pull requests require "explicit exact-head human approval and trusted
independent review" (`scripts/pr_policy.py`). The review half of that requirement
works: the `pr-agent-review` workflow posts its verdict as
`github-actions[bot]`, and the gate accepts it only when the comment is bound to
the exact 40-character head SHA. That half is machine-checkable and currently
machine-checked.

The human half is not checkable at all. Mechanically it is a label
(`risk/approved`) plus a body line:

```
Risk approval: APPROVE <40-char-sha> — <reason>
```

`_exact_head_approval` and `parse_exact_head_override` both parse text. Neither is
actor-bound. Any actor able to edit the PR body or apply the label can satisfy
them, including an agent, including an agent acting on its own initiative.

The obvious guard — require the approving actor to differ from the PR author —
cannot be implemented here. Every pull request in this repository is authored by
`jacob202`, and agents push commits, apply labels, and post comments using the
owner's own credentials. GitHub records `jacob202` as the actor for Jacob's
actions and for every agent acting on his behalf, and it keeps no other
distinction. There is no field the gate could read, so this is not a gate defect
to be patched; it is a missing property of how agents authenticate.

A separate defect makes the body line unattributable even in principle, and
fixing identity alone would not repair it. `evaluate_policy` reads only the
*current* `pr["body"]` and the PR creator; `_exact_head_approval` matches text and
returns a reason string, discarding any edit provenance. GitHub's pull-request
object exposes no field naming who last edited the body. An agent can therefore
insert an exact-head approval line while the PR still shows `jacob202` as author,
and no gate reading that body can tell who wrote it — with or without a distinct
agent identity. Any durable fix must move the human receipt onto an
**actor-bearing object** — an issue comment or a pull-request review, both of
which carry `user.login` — rather than the mutable body.

The consequence is that the strongest control in the repository's merge policy
rests entirely on agent discipline. PR #853 is the worked example: the risk
approval was recorded only after Jacob gave explicit approval at the exact head,
because the agent involved knew it must not originate the decision. Nothing in
the system enforced that. A different agent, or the same agent on a different day,
could have written the same line for itself and the gate would have returned
green.

## Decision

Adopt attributable agent identity **and** move human receipts onto actor-bearing
objects. Both are required; neither is sufficient alone.

**1. Attributable agent identity.** Agents performing GitHub actions — pushing,
commenting, labelling, and editing bodies — should act under a distinct machine
identity (a separate account or GitHub App) rather than the owner's personal
credentials. The owner's identity is then reserved for actions that are meant to
be human attestations.

**2. Human receipts on an actor-bearing object.** An approval must be carried by
an object that names its author — an issue comment or a pull-request review —
never by the mutable PR body. `_exact_head_approval`'s body-line format survives
only as a transitional mechanism, because identity alone cannot attribute a body
edit (see Context). The gate must read the acting login from the receiving object
and bind it to the exact head SHA.

With both in place, human-only controls become mechanically checkable rather than
behavioural:

- a risk approval must originate from an actor that is neither the pull-request
  author nor the lane that implemented or rebased the change;
- self-approval becomes detectable, and therefore a gate failure rather than a
  process failure;
- "who decided this" becomes answerable from the platform's own record instead of
  from prose in a handoff.

Transitional note: until step 2 lands, moving to a bot identity has no effect on
the risk-approval path, because the receipt it protects is still unattributable.
Step 2 is the one that changes what a gate can see.

## What this does not do

It does not prevent a human from delegating a decision, and it does not make an
approval true. Its whole value is attributability: after this change the platform
records *who* acted, so a policy can act on it. Before it, a policy cannot,
because the information does not exist. Attributability is a necessary condition
for enforcement, not a substitute for judgement.

It also does not, on its own, decide what the gate should then require. That rule
— "an approval from an actor other than the author and other than the
implementing lane" — should be written and reviewed separately once actors are
distinguishable, so the two changes can be evaluated independently.

## Alternatives considered

**Require the approver to differ from the PR author.** Not implementable. The
author is always `jacob202`, and the only actors able to label or edit are also
`jacob202`. A naive form of this rule would not strengthen the gate; it would make
correct approvals impossible while leaving the same hole for anyone acting as the
owner.

**Require an approving GitHub review instead of a body line.** Blocked for the
same reason. GitHub forbids self-approval, and with one human account every PR is
self-reviewed, so `reviewDecision` can never be satisfied.

**Keep it behavioural and document it well.** This is the current state and it was
worth doing — `docs/reference/MULTI_AGENT_COORDINATION.md` now records the rule and
its limits. But it is detection-free: a violation is invisible until someone reads
the comment history and notices. It should be kept as defence in depth, not
treated as the control.

**Do nothing.** Rejected. The risk approval gates the class of change that can
alter what the pipeline trusts and what it can spend, and it is currently
unverified.

## Consequences

**Easier.** Review-gate rules can be enforced in code instead of relying on
discipline. Agent actions become auditable. Attestation-bearing actions are
separable from routine ones. Future controls that need "a human did this" — spend
approval, destructive operations, publication — become implementable rather than
aspirational.

**Harder.** Identity and credential management becomes a real surface: a bot
account or App, its token, and its installation must be configured for `git`
(commit identity), `gh`/API access, CI, the Agent Room participant, and Builder
workers. Rotation and revocation need an owner. Some existing automation assumes
the owner's token and will need auditing.

**Off-limits once adopted.** Agents must not use the owner's identity for
attestation-bearing actions. Falling back to the owner's credentials "just to
unblock a merge" would recreate exactly the ambiguity this ADR removes.

## Status and next step

This ADR is **Proposed**. It deliberately records no implementation and changes no
credentials, tokens, or CI secrets — that is an auth change requiring Jacob's
deliberate intent, and it must not be an agent's unilateral edit.

Decision needed: accept, defer, or reject. If accepted, the follow-on work is a
separate change with four required parts:

1. **Provision the agent identity** and migrate agent GitHub actions to it.
2. **Move the human receipt** from the PR body to an actor-bearing object (an
   issue comment or a review) and have `scripts/pr_policy.py` read the acting
   login from there, still bound to the exact head SHA.
3. **Admit trusted machine-authored PRs to `agent-review`.**
   `.github/workflows/pr-agent-review.yml` currently runs the reviewer only when
   `github.event.pull_request.author_association == 'OWNER'`. A separate account or
   GitHub App will not carry that association on a personal repository, so PRs it
   opens would skip `agent-review` while `policy-gate` still requires exact-head
   independent review for sensitive changes — leaving them blocked or dependent on
   a human override. The eligibility condition needs to admit the trusted agent
   identity, with regression tests covering both the admitted and skipped cases.
4. **Add the actor-binding rule** to `scripts/pr_policy.py` with a regression that
   proves a self-issued approval is rejected.

Part 3 is the one most likely to be missed: adopting the identity without it
trades an unenforceable gate for a blocked pipeline.

Until all four land, the behavioural rule in
[`docs/reference/MULTI_AGENT_COORDINATION.md`](../reference/MULTI_AGENT_COORDINATION.md)
is the only control, and it is not enforced.
