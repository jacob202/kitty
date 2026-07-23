# Learnings

**Date:** 2026-07-06

## Durable Lessons

1. A writer without a reader kills the habit loop. Quick Capture only matters because inbox entries resurface through Kitty.
2. Stale handoffs are worse than no handoff. They create false confidence and waste the next session.
3. Abandoned paths need cleanup in the same phase. OpenWebUI leftovers caused port, doc, and test drift.
4. Localhost is not a security boundary. Keep gateway auth and host assumptions explicit.
5. Do not broaden architecture because the product feels exciting. Phase B is consolidation, not expansion.
6. Test counts must come from a command actually run in the current context.
7. Agent hooks must be simple enough to inspect; a hook with unreachable blocks is theater.

## Candidate Lessons (recovery session 2026-06-20)

### L-CAND-1 — Codex CLI runs concurrently and races the opencode agent on the same branch

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** post-crash recovery on `codex/phase-b-prep`
- **Problem:** The host crashed with three opencode sessions + Codex CLI running. Codex came back to life after the crash and continued scaffolding B1 (`gateway/db.py` + `tests/test_db.py`) on the same branch. The opencode recovery session's pre-commit hook blocked one commit because `tests/test_db.py` was mid-edit and `from gateway import db` was racing.
- **Evidence:** `git log --oneline` shows `a919901 feat(storage): add phase b sqlite foundation` (Codex) landing at 19:40 — 6 minutes after the user thought "codex is done." `tests/test_db.py` and `gateway/db.py` mtime: 19:40:20–19:40:46, while the opencode session's first baseline pytest was at ~19:25 (got 544 passed, no `test_db.py`).
- **Scope:** repo-wide for any branch where the user runs Codex CLI alongside another agent.
- **Lesson:** Before staging a commit, check `ps -ef | grep codex` (or the equivalent) and `git status` for files you did not create. If another agent is mid-edit, stash your work and wait for it to land, then `git stash pop` and rerun tests.
- **Action for future agents:** Document the "Codex may be running concurrently" check in `docs/AGENT_RUNTIME.md` (done). Add a script under `scripts/` that asserts no other agent is writing to the repo before `git add` if this recurs.
- **Confidence:** high
- **Review trigger:** any future commit-blocked-by-mid-edit-elsewhere event.
- **Promotion target:** AGENT_RUNTIME if a second instance occurs.
- **Notes:** This is the underlying cause of the original 0b44932 scramble. Worth a stable rule.

### L-CAND-2 — D9 #1 "memory_graph shim collapse DONE 2026-06-18" overstates completion

- **Status:** resolved
- **Date:** 2026-06-20 (opened) / 2026-07-06 (closed)
- **Source session:** recovery session, when applying the D9 deepening-candidates hunk from stash
- **Problem:** The hunk claims D9 #1 is DONE 2026-06-18, but the six module-level `_XxxAdapter` shims (`gateway/memory_graph.py:393–399`) are still present, and `GraphResult._get_adapters()` (line 442–456) still falls through to `_default_adapters()`. The work is small and unblocking; the "DONE" label is wrong.
- **Evidence (at open):** `git grep -n "_MemoryAdapter\|_KnowledgeAdapter\|_JournalAdapter\|_TracesAdapter\|_TodosAdapter\|_InboxAdapter" gateway/` returns the six shim definitions. `sed -n '442,456p' gateway/memory_graph.py` shows the `_get_adapters` fall-through. No external importers use the shims (verified by `git grep "_MemoryAdapter\|..."` excluding the shim file itself).
- **Resolution (2026-07-06):** The shims and the `_get_adapters` fall-through no longer exist. The file is now 602 lines (vs. 393–399 at the time of the original report); the `_XxxAdapter` shim class definitions are gone, and `MemoryGraph.__init__` (now at `gateway/memory_graph.py:466`) calls `_default_adapters()` directly with no fall-through. The D9 #1 collapse is genuinely done now; the original "DONE 2026-06-18" claim was correct but the lesson was opened before the next agent verified. Promoting the lesson to **durable** for the verification pattern.
- **Scope:** local to `memory_graph.py` and any D9 deepening list referencing it.
- **Lesson (promoted to durable, #8):** When a "done" claim sits across a crash or a session boundary, the next agent must verify the claim against the current tree before propagating it. The verification is cheap: read the lines you would touch, or run the evidence commands the original report cites. If the artifact is gone, the claim is true *now*; if it isn't, downgrade the status to "in progress."
- **Action for future agents:** When applying a stashed status-update hunk, run a quick `git grep` for the actual artifact (shim names, function names, version strings) and either confirm the work landed or downgrade the status. Closing a candidate lesson requires a fresh evidence pass against the current tree, not a re-read of the original evidence.
- **Confidence:** high
- **Promotion target:** durable (lesson #8, this file).

### L-CAND-3 — `gh` "error connecting to github.com" is a misleading 401 mask

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** PR #27/#28/#29 close pass
- **Problem:** `gh` returned `error connecting to github.com / check your internet connection` but curl could reach `github.com` and `api.github.com` in <1s. The actual problem was an invalid `GITHUB_TOKEN` env var shadowing the working keyring token. `gh auth login` would not have fixed it because env vars beat the keyring.
- **Evidence:** `gh auth status` showed "Failed to log in to github.com using token (GITHUB_TOKEN) — The token in GITHUB_TOKEN is invalid" and "Logged in to github.com account jacob202 (keyring) — Active account: false." After `unset GITHUB_TOKEN`, `gh api user --jq .login` returned `jacob202` and `gh pr list` worked.
- **Scope:** any session that uses `gh` and has `GITHUB_TOKEN` set in the env (kitty/.env or shell rc).
- **Lesson:** When `gh` says "check your internet," run `gh auth status` first. If a `GITHUB_TOKEN` is in env and marked invalid, `unset GITHUB_TOKEN` to fall through to the keyring.
- **Action for future agents:** None required at the runtime-rules level; this is operator-side. Note in the operator runbook.
- **Confidence:** medium → **high** (recurred)
- **Review trigger:** any future `gh` "connection" error.
- **Promotion target:** none.
- **Notes:** Worth a paragraph in `docs/AGENT_RUNTIME.md` if this recurs, but not a stable operating rule.
- **Recurrence (2026-07-22):** Same failure, this time on a raw `git push` (not `gh`): "Invalid username or token. Password authentication is not supported for Git operations." The operator-side note did not prevent it happening again a month later. `unset GITHUB_TOKEN` still fixes it in the moment, but root cause was never found — every standard dotfile was checked twice (`.zshrc`, `.zprofile`, `.zshenv`, `.bash_profile`, `.bashrc`, `.profile`, `.envrc`, Claude Code's shell snapshot) and none export it. Handed Jacob a real diagnostic instead of another workaround — but the first version of it was itself a mistake, worth flagging: `zsh -xv 2>&1 | grep -i github_token` prints the matching source line verbatim, which means if the export looks like `export GITHUB_TOKEN=ghp_...`, the actual token value lands in the terminal transcript. Correct, safe version: `zsh -xv 2>&1 | grep -i github_token | sed -E 's/(GITHUB_TOKEN[=: ]+).*/\1<redacted>/I'` — still shows which sourced file/command sets it, never the value. **Confidence raised to high given the second occurrence; promote to `docs/AGENT_RUNTIME.md` if it recurs a third time without the trace having been run.**

### L-CAND-4 — Test counts vary between runs of the same suite (warnings count specifically)

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** B0 baseline capture
- **Problem:** `python3.12 -m pytest tests/ -q --tb=short` returned 4 warnings on one run and 3 on another of the same checkout. The +1 is a `DeprecationWarning: builtin type swigvarlink has no __module__ attribute` from CPython that varies by Python build state. Pretending the warning count is stable leads to false "test count regressed" alarms.
- **Evidence:** Run 1 (post-prep): 544 passed, 2 deselected, 4 warnings. Run 2 (after B1): 547 passed, 2 deselected, 4 warnings. PROJECT_STATUS.md at one point claimed "3 warnings" — that was a transient.
- **Scope:** any pytest gate that compares warning counts.
- **Lesson:** Track passed/ deselected only. Treat warning counts as approximate. If a new warning type appears, that's a signal; +/-1 of an existing warning is not.
- **Action for future agents:** When you write a pytest gate or a "test count regressed" check, compare `passed` and `deselected` only, never `warnings`.
- **Confidence:** medium
- **Review trigger:** any new pytest gate.
- **Promotion target:** none (narrow).
- **Notes:** Not currently a rule anywhere; just a note.

### L-CAND-5 — `make agent-wrap` was not run for the recovery session; the handoff was filled manually

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** recovery session
- **Problem:** The wrap-up protocol says "run `make agent-wrap`" but the recovery session filled `.agent/session_logs/20260620T012911Z-handoff.md` by hand because running `make agent-wrap` in mid-recovery would have created a handoff before the actual work was done.
- **Evidence:** The `.gitkeep` and the timestamped handoff were created at 19:29 by the prep commit (the handoff is gitignored, but its mtime shows it was written before the recovery session's first tool call). The recovery session rewrote the handoff body manually.
- **Scope:** any session that is itself a recovery.
- **Lesson:** The wrap-up script is for normal sessions. Recovery sessions can either rewrite the existing handoff in place (what we did) or run the script at the very end. Either is fine; the handoff just needs to be filled in before the session ends.
- **Action for future agents:** No code change. The exit-protocol section of `docs/AGENT_RUNTIME.md` could mention "or, for recovery sessions, edit the most recent `session_logs/*.md` in place." Optional.
- **Confidence:** low
- **Review trigger:** next recovery session.
- **Promotion target:** none.
- **Notes:** The script is fine; this is just a usage note.

## Candidate Lessons (memory-loop + imagen-recovery session 2026-06-28)

### L-CAND-6 — Merging on the combined commit `status` without checking the separate `check_runs` let a non-compiling file reach `main`

- **Status:** candidate
- **Date:** 2026-06-28
- **Source session:** memory-loop + imagen reconstruction
- **Problem:** PR #46 was merged after confirming the combined commit `status` was green (only CodeRabbit reports there). The blocking-looking `check_runs` (lint/typecheck/pytest) were never inspected and were already red. A `mcp/imagen/server.py` that never compiled reached `main`.
- **Evidence:** `mcp/imagen/server.py` had `SyntaxError: unmatched ')'` at line 839 on `main` (commit 2a4708e); the same file was byte-identical and broken on the source branch. `pull_request_read get_status` returned only the CodeRabbit context; `get_check_runs` returned lint/typecheck/pytest, all failing.
- **Scope:** any agent merging a PR via API or `gh`.
- **Lesson:** `status` and `check_runs` are different GitHub surfaces. A green `status` says nothing about Actions check runs. Always read `get_check_runs` (or the Actions tab) before merging.
- **Action for future agents:** Before any merge, fetch check runs explicitly and confirm each required job is `success`. Do not infer green from a single combined status.
- **Confidence:** high
- **Review trigger:** next PR merge.
- **Promotion target:** `docs/AGENT_RUNTIME.md` (operating rule) if it recurs.

### L-CAND-7 — CI coverage gap: `mcp/` is linted and type-checked by nothing

- **Status:** candidate
- **Date:** 2026-06-28
- **Source session:** memory-loop + imagen reconstruction
- **Problem:** The imagen server was broken for multiple commits and no check caught it. Ruff lints only `gateway/ tests/`; mypy runs only `gateway/`. The pytest job hit a collection error in `tests/test_imagen/` and died before reaching the tests that import `mcp/imagen/server.py`, so the syntax error stayed invisible.
- **Evidence:** `.github/workflows/tests.yml` runs `ruff check gateway/ tests/` and `mypy gateway/`. The lint job was green while `server.py` did not compile. CI pytest reported "2 deselected, 1 error" (collection) without running the imagen server tests.
- **Scope:** anything under `mcp/` (and any path outside `gateway/`/`tests/`).
- **Lesson:** A directory outside the lint/type globs has zero static safety net. New top-level code trees need to be added to the CI globs, or they rot silently.
- **Action for future agents:** When adding code under a new top-level dir, extend the `ruff`/`mypy` targets in `tests.yml` to cover it. A collection error masks every test after it — treat collection errors as P0.
- **Confidence:** high
- **Review trigger:** next change under `mcp/`.
- **Promotion target:** none yet.

### L-CAND-8 — A non-blocking check allowed to stay red forever is theater

- **Status:** candidate
- **Date:** 2026-06-28
- **Source session:** memory-loop + imagen reconstruction
- **Problem:** The `typecheck` job was `continue-on-error: true`. 80 mypy errors accreted across many PRs because the red was cosmetic and never blocked anything.
- **Evidence:** `mypy gateway/` reported 80 errors in 27 files; the job had been non-blocking since introduction. One was a real latent crash (`clerk._extract_visual_descriptions` returned `str` but was typed and consumed as `list[VisualExtraction]`).
- **Scope:** any `continue-on-error` / advisory check.
- **Lesson:** Echoes Durable Lesson 7 (hooks must not be theater). A check that can stay red indefinitely trains everyone to ignore it, and real bugs hide in the noise. Flip advisory checks to blocking the moment they are clean.
- **Action for future agents:** When you make an advisory check pass, drop `continue-on-error` in the same PR so it cannot rot again. (Done for `typecheck` in #51.)
- **Confidence:** high
- **Review trigger:** next time an advisory check is made green.
- **Promotion target:** `docs/AGENT_RUNTIME.md`.

### L-CAND-9 — Squash-merging an old-base branch against a refactored `main` produced a franken-file

- **Status:** candidate
- **Date:** 2026-06-28
- **Source session:** memory-loop + imagen reconstruction
- **Problem:** The imagen branch was cut from an old `main`. Between then and merge, `#44` refactored `mcp/imagen/` from a monolith into modules. The squash merge spliced the new modular shim into the middle of the monolith's unclosed string tuple and left orphaned fragments — multiple syntax errors.
- **Evidence:** `server.py` on `main` mixed `from mcp.imagen.tools.* import ...` (modular) with inline `@mcp.tool()` monolith definitions of the same tools, plus a duplicated `FastMCP(instructions=...)` tail after `make_gallery`.
- **Scope:** long-lived branches merged after the base was restructured.
- **Lesson:** Rebase a long-lived branch onto current `main` (resolving conflicts deliberately) before merging, and confirm the merged file compiles. A clean squash does not mean a clean result when both sides rewrote the same file.
- **Action for future agents:** After any non-trivial merge, run a compile/import check on the touched files before declaring done.
- **Confidence:** medium
- **Review trigger:** next merge of a branch older than a refactor on its base.
- **Promotion target:** none yet.

## Candidate Lessons (post-swarm reconcile session 2026-07-02)

### L-CAND-10 — #70 merged with red check runs and broke main; L-CAND-6/9 repeated exactly

- **Status:** candidate
- **Date:** 2026-07-02
- **Source session:** post-swarm reconcile (PR #79)
- **Problem:** #70 (gateway deepening, 17-commit refactor) merged with pytest/lint/typecheck all failing, _after_ #75/#77 had landed on its refactored files. Main got a startup ImportError, re-seeded fake loop rows, and a broken adapter contract. This is L-CAND-6 (merged without checking check runs) + L-CAND-9 (old-base branch vs restructured main) happening again three weeks later.
- **Evidence:** `gh api .../commits/d349f4f/check-runs` → all failure; `routes/insights.py` importing names deleted from `routes/dream.py`; fixed in #79.
- **Scope:** any multi-agent swarm where PRs merge concurrently.
- **Lesson:** Red check runs are a hard merge-stop, no matter who or what merges. When two merged PRs rewrote the same file, the reconciliation is a deliberate decision (which semantic wins), not a mechanical rebase.
- **Action for future agents:** Before merging: check check_runs. After any merge into main: verify main's own check_runs went green before starting anything else.
- **Confidence:** high
- **Review trigger:** next swarm session with >2 concurrent PRs.
- **Promotion target:** already a rule in AGENTS.md/CODEX.md — repeat offense suggests promoting to a branch-protection setting (require green checks) instead of prose.

### L-CAND-11 — kitty-chat tests are invisible: not in CI, and `npm run` is silently broken locally

- **Status:** candidate
- **Date:** 2026-07-02
- **Source session:** post-swarm reconcile / console-home planning preflight
- **Problem:** 6 UI tests fail on main (`SessionSidebar` ×5, `TopBar` ×1) and nobody knew: CI has no kitty-chat job, and on Jacob's Mac `npm run <script>` exits 194 with zero output (node 26.4.0 / npm 11.17.0, repo-specific — clean dirs work), so local runs printed a banner and died silently.
- **Evidence:** `./node_modules/.bin/vitest run` → 91 passed / 6 failed; `npm run test` → exit 194, empty stderr.
- **Scope:** every UI change since the last green vitest run.
- **Lesson:** A test suite that no gate executes is documentation, not protection. Silent runner death (exit >128, no output) means bypass the runner (`./node_modules/.bin/vitest run`, `node node_modules/next/dist/bin/next build`) and treat the runner itself as broken.
- **Action for future agents:** Use the direct invocations until `npm run` is fixed; console-home phase step 0 adds a kitty-chat CI job.
- **Confidence:** high
- **Review trigger:** console-home phase step 0.
- **Promotion target:** CI workflow change (kitty-chat job), not prose.

### L-CAND-12 — Packet numbers got double-assigned: the registry and new spec files drifted

- **Status:** candidate
- **Date:** 2026-07-05
- **Source session:** Fable wave-3 close-out
- **Problem:** PRs #101 and #102 (authored in separate planning sessions) added spec files numbered 021 and 022 — but the registry had already assigned 021 to the project registry (shipped, #106) and 022 to Magic Kitty (D13). Neither PR added a registry row, so the collision was invisible until someone listed the directory.
- **Evidence:** `ls docs/packets/` on 2026-07-05 showed both `021-memory-taste-and-creative-continuity.md` and `021-project-registry-and-resume.md`.
- **Scope:** any session that authors a packet file without opening the registry first.
- **Lesson:** The registry table in `docs/packets/README.md` owns numbering. A packet file that isn't in the registry doesn't exist as work — it's a stray file. Authoring = pick the next free number *from the table*, add the row, then create the file, in one PR.
- **Action for future agents:** Before naming a packet file: read the registry table, take max(number)+1, add your row in the same commit as the file. If you find a file/registry mismatch, fix it immediately (renumber the file — the registry's assignment wins because shipped code may reference it).
- **Confidence:** high
- **Review trigger:** next packet authored by a session that didn't read this file.
- **Promotion target:** the packet intake gate section in `docs/packets/README.md` (one added line), if it recurs.

### L-CAND-13 — Packet 026 got double-assigned a third time; side branches don't own numbers

- **Status:** candidate — promoted to one added line in the packet intake gate (L-CAND-12's named promotion target)
- **Date:** 2026-07-14
- **Source session:** reasoning-engine authoring (packet 028)
- **Problem:** PR #164's session authored `026-chat-cutting-edge.md` on its branch (2026-07-12); a day later `026-builder-reliability.md` landed on main (2026-07-13, `00b018a`). Neither added a registry row. #164 then closed unmerged during stabilization, leaving a phantom 026 spec on a preserved branch and a real 026 file on main with no registry entry. Meanwhile packet 027 exists only as a Builder initiative manifest (`docs/initiatives/packet-027-v1.json`) — also invisible to the registry. The registry additionally contained two full copies of its own table (merge artifact), disagreeing on 016's status.
- **Evidence:** `git show FETCH_HEAD:docs/packets/026-chat-cutting-edge.md` vs `docs/packets/026-builder-reliability.md` on main; `docs/packets/README.md` lines 89–143 before this fix.
- **Scope:** any session authoring specs on a branch, and any merge that duplicates a registry table.
- **Lesson:** A number is owned by main's registry table, not by whoever typed it first on a branch. Specs that live outside `docs/packets/` (initiative manifests) still consume numbers and need rows. A duplicated source-of-truth table is worse than a missing one — both copies look authoritative.
- **Action for future agents:** Before naming a packet: read main's registry table (the one and only), take max(number)+1 across rows *and* `docs/initiatives/packet-*.json`, add the row in the same commit. If you find two tables, merging them is part of your job, not someone else's.
- **Confidence:** high
- **Review trigger:** next packet authored after a period of concurrent sessions.
- **Promotion target:** done in this same PR — the intake gate's numbering paragraph now states the main-owns-numbers rule.

## Candidate Lessons (CP-08 dogfood session, 2026-07-22)

KB-S5 sign-off (`docs/KITTYBUILDER_SELF_BUILDING_MVP.md`): two real
initiatives run unattended on free workers through CP-06 evidence-gated
auto-merge, zero fixtures. Campaign A (single doc-fix packet) needed five
live attempts before a clean one landed — the first four each surfaced a
real, previously-unexercised bug in the free-worker/auto-merge path, fixed
and shipped to `main` in the same session. Campaign B (4-packet,
prototype-gated) proved the prototype-gate gates the field, and that
same-invocation continuation to downstream packets works once the gate
opens — 3 of 4 packets auto-merged live; the 4th correctly stopped
`needs_decision` on a genuine scope overreach, not an infra bug. **What
fired as designed:** the scope enforcement (both checks, post-fix), CP-03's
stop classification, CP-06's auto-merge + the tripwire's absence-of-false-
triggering, CP-02's lint warning (predicted the exact file collision that
later caused a real merge conflict). **What never fired:** the tripwire
itself (no reverts occurred) and CP-06's auto-revert path — both remain
unexercised in this session; a deliberate revert drill (§3.3 negative test
4 in the daily-driver plan) is still owed before trusting them blind.

### L-CAND-14 — Two independent scope-check implementations silently drifted

- **Status:** candidate
- **Date:** 2026-07-22
- **Source session:** CP-08 dogfood, Campaign A/B live runs
- **Problem:** `builder_runner.py`'s live heartbeat scope check and
  `builder_identity.py`'s post-hoc identity verification both exist to
  enforce the same rule (stay in `allowed_paths`) but were two separate
  implementations. One had grown exemptions for repo convention residue
  (`.claude/STATE.md`/`HANDOFF.md`) and the runner's own worker-staging
  files; the other hadn't. A free worker that dutifully followed
  CLAUDE.md's own "update STATE.md before stopping" convention failed
  identity verification for doing exactly that — not a modeling error, an
  enforcement-layer inconsistency.
- **Evidence:** `gateway/builder_runner.py` commit `7a5f2e7` (runner-side
  fix), `gateway/builder_scope.py` commit `28bd51c` (centralized the
  exemption as `is_expected_residue`, both checks now call it).
- **Scope:** any pair of independently-evolved safety mechanisms meant to
  enforce the same invariant.
- **Lesson:** When two modules implement "the same" safety check
  separately, they will drift, and the drift surfaces as a false positive
  against legitimate work, not as a caught violation — the failure mode is
  silent and expensive (burned attempt budget) rather than loud. Prefer one
  canonical implementation with importers, even at the cost of an extra
  import, over two.
- **Action for future agents:** Before adding a new "safety check" near an
  existing one, grep for the existing one's exemption list first — a new
  duplicate is the default failure mode, not the exception.
- **Confidence:** high
- **Review trigger:** any future "worker did the right thing but got
  flagged" report.
- **Promotion target:** candidate; promote if a third independent scope
  check ever appears.

### L-CAND-15 — Sequential auto-merged packets in one initiative can genuinely conflict, and `.claude/STATE.md` guarantees they eventually will

- **Status:** candidate, not yet fixed (named follow-up)
- **Date:** 2026-07-22
- **Source session:** CP-08 dogfood, Campaign B (`cp08b-column`,
  `cp08b-filter`)
- **Problem:** Every packet's worktree branches from the same `base_sha`.
  When an upstream packet in the initiative auto-merges, `main` moves; a
  sibling packet's branch — cut from the *old* base — can develop a real
  git conflict against the new `main` before its own merge is attempted.
  This isn't hypothetical: it happened twice in one campaign, both times on
  `.claude/STATE.md` specifically, because every worker convention-writes
  to that one shared file, so any two concurrent-ish commits touching it
  will eventually collide. `cp08b-column` and `cp08b-filter` also
  genuinely collided on `tests/test_builder_cli.py` — the exact file CP-02's
  own lint warning had already named as a collision risk at manifest-apply
  time.
- **Evidence:** PR #226/#227 both showed `mergeStateStatus: DIRTY` /
  `CONFLICTING` before manual resolution; `gh pr view --json
  mergeable,mergeStateStatus`.
- **Scope:** any multi-packet initiative where sibling packets' allowed
  paths don't share a dependency edge (exactly what CP-02's collision
  warning flags) — `.claude/STATE.md` conflicts specifically are universal
  regardless of allowed_paths, since every worker touches it.
- **Lesson:** CP-06's auto-merge never rebases a packet's branch onto a
  freshly-advanced `main` before attempting its own merge — it assumes the
  branch is still current. It was operator-resolved by hand this session,
  not automatically.
- **Action for future agents:** Two candidate fixes, not yet chosen: (a)
  `merge_and_verify` rebases onto current `main` before attempting `gh pr
  merge`, retrying once on a clean rebase; (b) stop instructing free
  workers to touch `.claude/STATE.md` at all — Builder tracks its own state
  via the queue DB, not that file, and CLAUDE.md's "Session State"
  convention was written for Jacob's own Claude Code sessions, not for
  isolated Builder attempts. (b) is cheaper and removes the universal
  collision source; (a) is still needed for genuine content collisions
  like the `test_builder_cli.py` case. Do both when this is picked up.
- **Confidence:** high
- **Review trigger:** the next multi-packet campaign with siblings that
  share an allowed-path prefix (CP-02 will warn) or run long enough for
  another session's commit to land on `main` mid-campaign.
- **Promotion target:** `docs/DECISIONS.md` once a fix is chosen — this is
  an architecture gap in CP-06, not just an observation.

## Candidate Lessons (branch-sprawl triage + frontend harvest, 2026-07-22/23)

### L-CAND-16 — `.claude/STATE.md`/`HANDOFF.md` are a single shared file, not a session-scoped journal; concurrent writers stomp each other

- **Status:** candidate
- **Date:** 2026-07-22/23
- **Source session:** frontend code-harvest wave 1 + branch-sprawl triage (cloud session, `claude/session-3pgcib`)
- **Problem:** This is L-CAND-1's pattern (concurrent agents racing on the same file) recurring in a new domain. Within roughly one hour, three different actors wrote to `.claude/STATE.md`/`HANDOFF.md`: a Mac-local session (stale-branch audit), this cloud session (frontend harvest + branch triage), and an autonomous KittyBuilder Campaign B loop running packets on its own schedule. A carefully-written, CI-verified hygiene update (PR #223) was fully overwritten by Campaign B's own state-tracking commits within about 20 minutes of merging — not through conflict, just through last-write-wins on a single shared file with no per-actor scoping.
- **Evidence:** `git log --format='%an %s' -- .claude/STATE.md` around 2026-07-22T05:00–2026-07-23T01:40 shows alternating authorship (this session, `jacobbrizinski@MacBookAir...`, and Campaign B's own commits) each replacing the prior narrative wholesale. `origin/main`'s `STATE.md` went from "Frontend Harvest + Tailnet Card Shipped" to "CP-08 Campaign B In Progress" with zero trace of the prior content beyond git history.
- **Scope:** any session or automated loop (KittyBuilder campaigns included) that writes `.claude/STATE.md` or `HANDOFF.md`, whenever more than one such actor can be active in the same window.
- **Lesson:** Do not treat a fresh read of STATE.md/HANDOFF.md from earlier in a long conversation as still current — re-read immediately before writing, every time, because another actor may have replaced it since. Do not assume "session hygiene" means "write my session's full narrative" when the file's current content belongs to a different, still-active workstream (autonomous campaign, another human's session) — check whose story is currently there before overwriting it wholesale.
- **Action for future agents:** Before writing STATE.md/HANDOFF.md, `git fetch` and read the live `origin/main` copy fresh, not a cached read. If the current content is clearly a different active workstream's narrative (different mission, recent `updated_at`, unfamiliar branch/PR references), don't clobber it — either leave it alone and put your own findings in chat / a durable doc (`docs/LEARNINGS.md`, a dated note), or scope your addition narrowly instead of replacing the whole file. Preserve the continuity schema's accepted status values (`complete`, `in_progress`, `blocked`, and related states); `done` is not valid metadata.
- **Confidence:** high
- **Review trigger:** next time two sessions or an autonomous campaign are confirmed active on the same repo in the same window.
- **Promotion target:** `docs/AGENT_RUNTIME.md` — this has now recurred across two completely different actor-pairs (Codex/opencode on `gateway/db.py`, per L-CAND-1; Mac-session/cloud-session/Campaign-B on `.claude/STATE.md`, here). That's a repo-wide, repeated, high-risk pattern, not a one-off.

### L-CAND-17 — A three-dot git diff (`main...branch`) shows what's unique since the fork point, not what's missing from main *now*

- **Status:** candidate
- **Date:** 2026-07-22
- **Source session:** branch-sprawl triage (cloud session, `claude/session-3pgcib`)
- **Problem:** While auditing `feat/packet-022-magic-kitty` for unique work, `git diff origin/main...origin/feat/packet-022-magic-kitty -- gateway/magic_kitty.py` showed a privacy-tier fix as a `+` addition, read as "the branch adds this, main lacks it." It was wrong: the branch's merge-base predates a same-day commit (`7f278d9`, #153) that added the identical fix directly to main. `git diff A...B` diffs `merge-base(A,B)` against `B` — it cannot see what happened on `A`'s side after the fork. Confirmed only by comparing final file contents directly (`git show branch:path` vs the working tree file) — byte-identical, nothing unique.
- **Evidence:** `git merge-base origin/main origin/feat/packet-022-magic-kitty` → `2986c6a` (2026-07-12 03:56); the privacy fix landed on main via `7f278d9` at 2026-07-12 04:02 — six minutes later, on a different branch entirely. The three-dot diff still showed it as a `+` because the merge-base lacked it, even though current `main` has had it the whole time.
- **Scope:** any stale-branch audit that uses `git diff origin/main...branch` to decide if a branch contributes something main lacks — which was the primary method for the other ~84 branches audited this session.
- **Lesson:** A three-dot diff proves a branch is *different from its own history*; it does not prove main is *currently missing* what the branch adds. For a genuine "is this unique" call, do a direct comparison of the specific files against current `main`'s working tree (or `git show origin/main:path`), not just the ancestry-relative diff. This matters most for old branches whose fork point is far behind current main, and most of all right after a fast-moving day of merges (exactly when superseding commits are most likely to have landed a different way).
- **Action for future agents:** When a stale-branch audit's diff shows a "unique" addition worth flagging as a real candidate, confirm it with a direct file-content comparison against current main before reporting it as a find. Don't stop at the three-dot diff.
- **Confidence:** high
- **Review trigger:** next stale-branch or dead-code audit using diff-based supersession checks.
- **Promotion target:** none yet — one confirmed occurrence; would promote to `docs/AGENT_RUNTIME.md` if it recurs.

## Candidate Lessons (rejected or not promoted)

Empty — nothing rejected this session that was strong enough to mention.

## Promotion criteria (do not change these)

- Promote to `docs/AGENT_RUNTIME.md` only if: repeated, high-risk, repo-wide, clearly useful as an operating rule.
- Promote to `docs/DECISIONS.md` only if: actual architecture or workflow decision, alternatives were considered, rationale and tradeoffs recorded.
- Archive a learning if: stale, contradicted by current code, too narrow, duplicates another lesson, caused agent over-correction.
