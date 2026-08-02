# Session note — KTL2-003 corrective follow-up (2026-08-02)

**Execution owner.** interactive — this corrective PR fixes the review
findings from PR #371. No Builder task, bundle, or lease.

**What this corrects.**
- `tests/workflow/test_parallel_lanes.py` now exercises
  `scripts.resolve_next_work` (the real continuation resolver from KTL2-001),
  not just `scripts.kb_effectiveness.record_receipt`.
- STATE.md and HANDOFF.md carry `origin/main`'s current HEAD and branch
  instead of a stale Builder worktree identity.
- The session note no longer claims a committed JSONL receipt artifact that
  was never committed.

**Evidence recorded.**
- Resolver tests: `TestBareNextNeverTouchesBuilder`, `TestBareNextIgnoresBuilderQueue`,
  `TestBuilderEntrypoints`, `TestDeterministicOutput`, `TestContradictoryIntent`.
- Receipt-layer invariants kept as secondary evidence (tmp_path store,
  reproducible).

**Unavailable (named, not estimated).**
- No live second interactive tool was spawned.
- Token, cost, and elapsed-time measurements: not captured, remain `null`.
- No causal token/quality claim is made.
