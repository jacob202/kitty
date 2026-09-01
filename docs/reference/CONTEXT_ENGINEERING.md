# Context Engineering Playbook

Keep only high-signal context for the requested outcome. `START_HERE.md` owns
cold-start checks and `verified-delivery` owns completion language.

## Load by task

1. Prove `workspace_global` access first, then choose the receipt from the actual
   continuation source:
   - when an unread GAR handoff or known durable thread identifies the
     assignment, use `./kitty context --agent --skip-legacy-continuity` for code
     work; add `--compact --skip-builder` for informational/planning work;
   - when GAR is available but no durable room locator exists yet and a legacy
     checkpoint is needed as the compatibility fallback, run the strict
     `./kitty context --agent` receipt and trust the checkpoint only if that
     validation succeeds;
   - when GAR is unavailable, report that and use the same strict compatibility
     receipt.
   Treat unknowns as unknowns. A legacy-skipping receipt never validates a
   legacy fallback.
2. Classify the request:
   - informational: authority map plus directly relevant authority;
   - planning: add roadmap, active mission, and a deterministically located
     `workspace_global` handoff/thread when one exists;
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
implementation state, exact verification commands and results, unresolved failures and blockers,
and one concrete next action. Publish those facts as the final validated
`workspace_global` result/handoff after final verification, not before
compatibility writes or validation. On resume, retrieve the known room thread or
unread direct handoff and validate it against live Git and runtime state. When no
durable room locator exists yet, use the strict-receipt-validated legacy
compatibility checkpoint rather than pretending the global recent window is an
assignment index.

Use exactly one completion state: `verified`, `implemented, awaiting
verification`, `blocked`, or `failed`. Do not infer runtime success from code
inspection, a green aggregate status, a wiki write, or optimistic wording.

## Anti-waste rule

Do not run Builder checks, broad repository archaeology, full test suites, or
large CodeGraph queries unless the task has an unresolved question that needs
them. Prefer one batched, bounded command with an explicit end condition over
repeated read/run/check loops. If a tool result is oversized, narrow the next
query instead of re-reading the whole output.
