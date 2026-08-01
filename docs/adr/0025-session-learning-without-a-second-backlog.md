# ADR 0025: Session Learning Without a Second Backlog

- **Status:** Accepted; amended 2026-08-01
- **Date:** 2026-08-01
- **Decision owner:** Jacob
- **Relates to:** ADR 0016, ADR 0017, ADR 0020, ADR 0023, ADR 0026

## Context

Kitty's engineering workflow already has several durable authorities:

- `docs/ROADMAP.md` for product delivery order;
- approved Missions for bounded intent;
- KittyBuilder for initiatives, packets, queue tasks, attempts, evidence,
  review, recovery, and publication state;
- `.claude/STATE.md` and `.claude/HANDOFF.md` for interactive cross-session
  continuity;
- `~/kb` for durable cross-tool knowledge and corrections.

The workflow still repeats avoidable failures: agents duplicate another
worker's work, trust stale handoffs, rebuild mature open-source functionality,
accept bootability as product proof, leave unverifiable success claims, and fail
to convert recurring friction into a governed repair.

Simply asking session-end to write more recommendations would turn the
checkpoint into an unbounded backlog. Creating another learning database would
copy state from the roadmap and Builder. Automatically opening issues or queue
tasks for every annoyance would create noise and let a model silently change
project priority.

A second risk became explicit during implementation: treating a bare `next` in
Claude Code/OpenCode/Codex as an instruction to select Builder's next packet
collapses interactive work and Builder's autonomous execution train into the
same lane. That creates duplicate ownership and makes session continuity a
shadow scheduler.

## Decision

Session-end records structured workflow-learning evidence in the existing
cross-tool knowledge base, while execution authority remains in the existing
roadmap and Builder queue.

1. The canonical workflow-signal recorder is `scripts/session_learning.py`.
2. Signals normally live under `~/kb/workflow-signals/`. When `~/kb` is absent,
   the complete payload may be staged under
   `docs/session-notes/workflow-signals/` for later transfer.
3. Each signal has a stable key, bounded category, severity, summary, direct
   evidence, impact, suggested change, source session, and verification method.
4. One ordinary occurrence is observed, not promoted. The same stable key must
   occur in at least two sessions within 30 days before promotion.
5. Critical incidents and data-loss, fabricated-success, paid-waste,
   queue-integrity, or security-boundary signals promote immediately.
6. Promotion is evidence that a problem deserves ownership; it is not authority
   to implement it. Before any recommendation or task is created, the workflow
   checks the roadmap, active Mission, initiative packets, Builder queue, live
   branches/worktrees, open PRs, and issues for an existing owner.
7. Session-end may carry at most one promoted, unowned code improvement through
   ADR 0023's existing recommendation channel. It does not automatically create
   GitHub issues or Builder tasks.
8. A later bounded promotion adapter may create at most one Builder task per
   stable signal key. It must support dry-run, record the source fingerprint,
   suppress existing owners, and use Builder's existing state machine.
9. `.claude/STATE.md` recommendations remain the only interactive cross-session
   next-step channel. Workflow-signal files are evidence history, not another
   backlog.
10. A bare `next` instruction continues the current interactive assignment only.
    It may inspect signal and Builder summaries for relevant context and
    collision detection, but it never applies an initiative, selects a queued
    packet, claims Builder work, or promotes a signal into execution.
11. Explicit `builder next`, a named Builder task/packet, or a valid
    Builder-launched worker bundle enters the Builder lane. Every implementation
    has exactly one execution owner: `interactive` or `builder`.
12. Whether the KB improves outcomes is measured separately under ADR 0026.
    Signal frequency is not itself proof of lower token use or better code.

## Consequences

- Repeated workflow problems become visible across tools and sessions.
- One-off irritation does not automatically consume engineering time.
- High-risk integrity failures surface immediately.
- The workflow can learn without copying Builder state or creating an issue
  flood.
- Stable keys and occurrence counts expose recurring failures that agents would
  otherwise rename every session.
- Interactive continuity no longer acts as a hidden Builder scheduler.
- Signal quality depends on direct evidence; vague self-evaluation and agent
  narration are rejected.
- The separate `~/kb` repository must be available for the normal path. The
  repo fallback is a staged transfer payload, not a permanent fork.

## Acceptance

The decision is implemented only when:

- a first ordinary signal records `observe`;
- its second occurrence within the window records `promote`;
- an integrity-category signal promotes on its first occurrence;
- corrupt prior records fail loudly instead of resetting history;
- session-end reports the signal path and promotion status;
- a promoted signal with an existing roadmap/queue/PR/issue owner creates no
  duplicate recommendation or task;
- a bare interactive `next` cannot apply an initiative or consume Builder work;
- an explicit Builder instruction can still route through Builder's governed
  selection/execution workflow; and
- the future promotion adapter is idempotent by stable signal key.

## Revisit triggers

Revisit this decision when:

- ordinary signals create more noise than useful repairs;
- promotion routinely misses existing owners;
- `~/kb` is unavailable often enough that fallback payloads accumulate;
- stable-key collisions merge genuinely different problems;
- a second execution or recommendation authority appears around the signals;
- interactive and Builder ownership becomes ambiguous again; or
- evidence shows the signal process adds more cost than it prevents.
