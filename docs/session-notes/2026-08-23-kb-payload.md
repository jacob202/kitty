# KB payload — staged because `~/kb` is absent

**Staged:** 2026-08-23 · claude-code · execution owner `interactive`
**Why staged here:** `~/kb` is not present in this remote container. It is
Jacob's Mac-side repository with real history; creating it here would redirect
receipts into storage that dies with the container. Release check: `test -d ~/kb`.

---

# Strict up-to-date turns parallel green PRs into serial re-approval

**Source:** 2026-08-23 session, claude-code
**Date:** 2026-08-23
**Why it matters:** It sets the real cost of having many agents work in parallel
against one protected branch, and it is not fixed by making CI faster.
**Verified:** PR #606 reached a green, fully-approved head three times
(`c27e04dd`, `57e6b7a7`, `4d86ef9d`) and fell `BEHIND` each time as #593, #607,
and #608/#611 merged. Each refresh produced a new head SHA, which invalidated the
exact-head risk receipt and forced a fresh full CI run plus a fresh human
approval. Confirmed from live `policy-gate` logs naming
`risky scope requires exact-head risk approval` on each new head.

With strict up-to-date plus exact-head approval receipts, N ready PRs cost N-1
forced revalidations regardless of merge order. Speeding up CI reduces the pain
per cycle but not the number of cycles. The only structural fix is admitting one
PR at a time into final merge-candidate validation.

---

# A post-merge full CI run detects nothing a strict-mode PR gate missed

**Source:** 2026-08-23 session, claude-code
**Date:** 2026-08-23
**Why it matters:** It was 12.2 runner-minutes per merge spent on evidence that
could not, even in principle, find a new failure.
**Verified:** Run 32626738131 — the push that merged docs-only PR #603 — spent
730 runner-seconds (pytest 305s, browser-smoke 201s, typecheck 99s, kitty-chat
69s, hygiene 39s) re-validating a tree whose own PR gate had passed 38 seconds
earlier. The active ruleset requires strict up-to-date checks with zero bypass
actors, so the merge commit carries exactly the tree the PR head validated.

Residual value of a post-merge run is limited to time-based drift (a dependency
that changed between PR CI and merge), which belongs on a nightly clock, not on
every merge.

---

# Advisory checks that gate nothing are read by nobody

**Source:** 2026-08-23 session, claude-code
**Date:** 2026-08-23
**Why it matters:** Distinguishes "cheap" from "worth running per PR".
**Verified:** The `hygiene` job ran on every PR and every push to `main` at ~39
runner-seconds each, with `continue-on-error: true`, so it could never block a
merge. Its own inline comment recorded 65 known deptry findings as of 2026-07-15
that had been carried unfixed. Moved to `nightly-health.yml` where a delta
comparison can make its findings actionable.
