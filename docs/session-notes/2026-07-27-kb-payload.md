# KB payload — 2026-07-27

Staged because `~/kb` is not present in this container. Merge these into the
knowledge base on the canonical Mac, then delete this file.

Target: `~/kb/wiki/2026-07-27-red-base-branch-poisons-every-pr.md`
Plus one line under the Wiki section of `~/kb/INDEX.md`.

---

# A red base branch fails every PR built on it

**Source:** 2026-07-27 session, Claude Opus 5 (Kitty repo, PRs #276 and #278)
**Date:** 2026-07-27
**Why it matters:** Stops an hour of debugging a branch whose own diff is fine.
**Verified:** `git checkout origin/main && ruff check gateway/ tests/ mcp/` →
7 errors in `gateway/insight_loop.py` and `tests/test_insight_loop.py`;
`mypy gateway/ mcp/` → 2 errors in `gateway/routes/knowledge.py`;
`pytest tests/test_cold_start_acceptance.py` → failed on `main`'s own checkpoint
files. All three reproduced on a pristine `origin/main` checkout, with no
branch changes applied.

GitHub runs a PR's checks against **the PR merged into its base**, not against
the branch head. So a branch that is green locally still shows red CI the moment
its base is broken, and the failure names files the branch never touched.

Check the base before debugging the branch:

```bash
git fetch origin main && git checkout origin/main
ruff check gateway/ tests/ mcp/ ; mypy gateway/ mcp/ ; pytest tests/ -q
```

If the base is red, say so in the PR thread rather than treating it as your
failure — and fix it if the fix is mechanical, because otherwise every open PR
in the repo stays blocked behind it.

---

Target: `~/kb/wiki/2026-07-27-read-only-surveys-must-not-init.md`

# A "read-only" probe that calls init_db is not read-only

**Source:** 2026-07-27 session, Codex PR review on jacob202/kitty#276
**Date:** 2026-07-27
**Why it matters:** A survey meant to observe state silently created and
migrated the store it was observing, and turned "unknown" into "empty".
**Verified:** `gateway/builder_queue.queue_status()` line 793 calls `init_db()`;
`init_db()` runs `path.parent.mkdir(parents=True, exist_ok=True)` plus schema
and column migrations. Confirmed the container's
`data/kittybuilder/builder_queue.db` was created at the timestamp of the first
survey run, with 0 tasks and 0 events.

Before calling any CLI from a read-only context, trace the handler to the
storage layer. Convenience status commands very often initialize on the way in.
Use the dedicated read-only projection instead (`builder_status.
build_control_plane_summary`), and treat an absent database as unknown state,
never as an empty one.
