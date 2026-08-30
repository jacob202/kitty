# Context Engineering Playbook

Keep only high-signal context for the requested outcome. `START_HERE.md` owns
cold-start checks and `verified-delivery` owns completion language.

## Load by task

1. Run the full `./kitty context --agent` for code/Builder work. For
   informational or planning work, use `./kitty context --agent --compact
   --skip-builder`; treat unknowns as unknowns.
2. Classify the request:
   - informational: authority map plus directly relevant authority;
   - planning: add roadmap, active mission, and checkpoint when relevant;
   - code change: use the full `START_HERE.md` order.
3. Load the smallest code, test, runtime, or Builder surface that answers the
   open question. Expand only when evidence requires it.
4. For implementation or repair, load the outcome contract before editing.
5. Re-check authorization, ownership, branch, and exact files immediately
   before mutation.

## Keep and clear

Keep the user outcome, acceptance criteria, canonical constraints, branch/
worktree/SHA, changed paths, live failures, blockers, and next verification.

Clear, summarize, or re-fetch bulky file reads, API responses, repeated
discussion, speculative explanations, stale plans, and evidence already
represented by a reproducible receipt.

Use memory for durable facts and corrections, not transcript dumps. Use a fresh
context for independent investigation or verification when acceptance depends
on a separate trust boundary.

## Handoff and completion

Before compaction or handoff, preserve the outcome contract and non-goals,
accepted decisions and their authority, current branch/worktree, and SHA plus
implementation state,
exact verification commands and results, unresolved failures and blockers, and
one concrete next action. On resume, validate that record against live Git and
runtime state.

Use exactly one completion state: `verified`, `implemented, awaiting
verification`, `blocked`, or `failed`. Do not infer runtime success from code
inspection, a green aggregate status, a wiki write, or optimistic wording.

## Anti-waste rule

Do not run Builder checks, broad repository archaeology, full test suites, or
large CodeGraph queries unless the task has an unresolved question that needs
them. Prefer one batched, bounded command with an explicit end condition over
repeated read/run/check loops. If a tool result is oversized, narrow the next
query instead of re-reading the whole output.
