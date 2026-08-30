# Kitty Agent Execution Operating Procedure

Purpose: make post-audit coding-agent work predictable, cheap, collision-resistant and evidence-driven without embedding stale provider/model assumptions.

This is operational guidance, not product architecture.

## 1. One owner per semantic lane

One implementation agent owns one coherent remediation chunk at a time.

Parallel work is allowed only when:
- target files do not overlap;
- state-machine semantics do not overlap;
- one lane does not depend on another's unmerged contract;
- active Image Lab work remains isolated unless explicitly assigned.

A separate reviewer may inspect the same lane read-only, but should not independently implement a competing solution.

## 2. Establish runtime/tool truth first

Before coding, inspect current local capabilities rather than relying on a prompt's remembered setup.

Useful checks where applicable:
```bash
orca status
orca account list
orca skills installed
git status --short --branch
git worktree list
git rev-parse HEAD
```

Also inspect current Kitty provider configuration and current GitHub PR/issue ownership before choosing a model/lane.

## 3. Cost-aware model allocation

Use the cheapest capable current model for routine bounded implementation and repetitive verification.

Escalate model capability for:
- ambiguous architecture decisions;
- security/trust-boundary changes;
- state-machine/recovery design;
- high-risk review;
- reconciliation when two implementations disagree.

Do not hard-code yesterday's free-model ladder into durable instructions. Resolve currently available providers/models at execution time.
## 4. Mutation boundary

Read-only analysis/review may safely retry or fall back across models when no external mutation has occurred.

Once a lane has performed a meaningful mutation (code edit, commit, push, PR action, external side effect), do not blindly hand the exact same imperative to another agent/model after an ambiguous timeout. First inspect actual resulting state.

This prevents:
- duplicate commits;
- duplicate pushes/PRs;
- repeated external mutations;
- two agents racing to 'finish' the same work.

## 5. Agent handoff packet

Every handoff should contain only verified current state:
- exact goal / finding IDs;
- current SHA and branch/worktree;
- files intentionally changed;
- files explicitly reserved by other lanes;
- original reproduction;
- changes already made;
- tests already run and exact results;
- outstanding failure/blocker;
- next exact action;
- whether any external mutation already occurred.

Never hand off a giant historical narrative when a compact current-state packet is sufficient.

## 6. Reviewer independence

Reviewer should begin from:
- current diff;
- finding acceptance criteria;
- regression test;
- relevant architecture authority;
- current main.

Reviewer should attempt to disprove correctness, especially:
- stale-base regressions;
- widened permissions;
- retries that duplicate mutation/spend;
- partial state changes;
- unit tests that miss integration failure;
- dead/legacy path accidentally preserved as authority.
## 7. Escalation rules

Escalate to the user only when a decision genuinely changes product intent, money/risk authority, destructive scope, or a design question the audit leaves unresolved.

Do not escalate because:
- a file needs locating;
- a test command needs discovering;
- a GitHub issue needs reading;
- a branch needs inspecting;
- a failure needs ordinary debugging.

Use available tools to resolve those yourself.

## 8. Stop / switch-lane rules

Stop the current implementation lane when:
- target is already fixed on main;
- another PR now owns the same semantics;
- original failure is no longer reproducible;
- required authority is contradictory;
- the patch needs a larger redesign than Chunk 11 approved;
- a destructive/paid action lacks authority.

When blocked, switch only to the next audit-authorized NON-COLLIDING lane. Do not invent a fresh backlog item.

## 9. Completion

An agent may say a chunk is complete only when:
- current diff matches the intended scope;
- regression proof passes;
- required broader gates pass;
- acceptance journey passes where applicable;
- current-main collision check passes;
- residual risk is stated;
- handoff/PR evidence is sufficient for independent review.

The aim is not maximum agent activity. The aim is a small number of changes whose correctness can be demonstrated.
