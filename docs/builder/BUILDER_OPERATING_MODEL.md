# Builder Operating Model

Runtime rules for KittyBuilder execution. Every worker and controller must
follow these. They are enforced where possible and relied upon everywhere else.

## §1 — Bounded Scope

Every packet carries a contract: `objective`, `acceptance_criteria`,
`allowed_paths`, `validation_commands`. Builder executes only what the contract
authorises. No implicit scope expansion.

See `gateway/builder_scope.py` for runtime enforcement.

## §2 — Attempt Budget

Each packet has `policy.max_attempts` (default 3). Builder uses at most that
many execution attempts. When exhausted, the task goes `blocked` with reason
`budget_exhausted` and control returns to the operator.

## §3 — Validate Scope (Pre-Execution Gate)

Before any worktree or attempt exists, `validate_scope()` checks the packet
contract:

1. Is the objective non-empty and specific?
2. Are acceptance criteria present and measurable?
3. Are `allowed_paths` bounded and repo-relative?
4. Does the packet touch a protected architecture/governance zone without
   explicit authority?

Any finding triggers **STOP → Escalate → Return Control**. No worktree is
created. No attempt is consumed.

Protected-zone authority is deterministic: the exact file (or bounded
directory) must be named in the packet contract. ADR references alone are
context, not authority.

## §4 — Investigation Budget

Every packet gets a finite investigation budget. This prevents unbounded
curiosity from consuming time and credits.

**Rule:** Maximum 3 investigation hops per packet.

An "investigation hop" is any attempt where the worker discovers something
unexpected and re-enters the loop to investigate rather than implementing the
original objective. The attempt counter (`policy.max_attempts`) IS the
investigation budget.

**Enforcement:**

```
attempt_no > policy.max_attempts
    → STOP
    → Produce final report
    → Return control
```

No fourth rabbit hole. The report must state:

- What was discovered
- Why execution is blocked
- What evidence exists
- What decision is needed from the operator

**Before every new investigation, the worker asks:**

> Does this directly unblock my packet?

- YES → continue
- NO → stop, produce a finding, return control

This is not optional discipline. It is a runtime constraint.

## §5 — Implementation Judgment Doctrine

Builder is paid to implement. Builder is not paid to become an expert on every
repository mystery.

When implementation expands into any of the following, STOP and return
control:

- Repository archaeology (tracing git history to explain current state)
- Historical reconstruction (figuring out why past commits were made)
- Infrastructure debugging (fixing CI, test harnesses, or toolchain issues
  unrelated to the packet)
- Test-isolation forensics (proving a failure is environmental rather than
  a regression)

These are findings, not side quests.

**Finding template:**

```
Category:    <infrastructure | test-isolation | environmental>
Severity:    <blocking | non-blocking>
Evidence:    <what was observed, minimal reproduction steps>
Suggested:   <new packet to address this, or "pre-existing — not this packet's scope">
```

After emitting the finding, STOP. Do not continue investigating.

## §6 — Pre-Existing Failure Protocol

When a test fails during packet execution, follow this sequence exactly:

1. **Reproduce** the failure (run the test in isolation).
2. **Disable your change** (restore the original code for the failing module).
3. **Reproduce again** (run the same test).
4. **Same failure?** → PRE-EXISTING.

**If pre-existing:**

```
Status:      PRE-EXISTING
Evidence:    <test name, error output, confirmation that it fails without your change>
Impact:      <does it block your packet? yes/no>
Next action: <open a separate packet, or continue if non-blocking>
STOP
```

**If different failure** → your change caused it. Fix it.

Do not spend more than one additional investigation hop on pre-existing
failures. The goal is to determine *whether* your change caused the failure,
not *why* the pre-existing failure exists.

## §7 — Return Control

Every STOP produces a structured report:

```json
{
  "outcome": "blocked | escalated | budget_exhausted",
  "reason": "<concise description>",
  "evidence": "<what was observed>",
  "findings": ["<category: description>"],
  "recommendation": "<what the operator should do next>"
}
```

Control returns to the operator. Builder does not retry, expand scope, or
self-heal beyond the attempt budget.
