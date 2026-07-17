# Session State — 2026-07-16 — Builder UI V1 recovery complete

## Current truth

- Branch: `feat/builder-ui-v1-complete`
- Base: verified `origin/main @ 719ee15072ae53fcfb284a7865af06a0892ccf60`
  (the merge of PR #181).
- Draft PR: https://github.com/jacob202/kitty/pull/183
- Recovery provenance: original UI commit `b1c1d7` from closed stacked PR
  #182 was absent from `main` and was cherry-picked without conflict as
  `da5a117`.
- Completion commits: `8f63233` (bounded backend projection) and `95cfd3e`
  (read-only investigation UI).
- The original recovery worktree at
  `/Users/jacobbrizinski/Projects/kitty/.worktrees/builder-ui-surface-v1`
  remains untouched. No worktree or branch was deleted and no history was
  rewritten.

## What is complete

- `gateway/builder_status.py` exposes schema v2 using eight bulk queries. It
  avoids packet-count N+1 reads, caps attempt history at ten records per packet,
  reports total/truncation and retry-budget consumption, and keeps duplicate
  packet IDs isolated by `(initiative_id, packet_id)`.
- Read derivation lives beside the canonical initiative scheduler in
  `gateway/builder_initiative.py`; it does not create a second execution state
  machine. Direct tests lock dependency, exhaustion, and rollup precedence.
- Malformed JSON/evidence degrades only the affected packet and propagates a
  visible degraded runtime fact. Safe messages are bounded and redact local
  paths and common secret forms. Publication URLs are restricted to canonical
  HTTPS GitHub PR links.
- Kitty now has a Builder home glance, rail entry, attention-first grouped
  overview, and packet detail with objective, run/lease/branch timing,
  publication, bounded attempt evidence, validation/review summaries, explicit
  failure classes, focus restoration, stale/unavailable/empty states, and
  responsive long-content handling.
- V1 is intentionally read-only. It exposes no run, retry, cancel, release,
  approve, reject, publish, or merge controls.

## Safety and deferred delivery contract

- The projection omits raw commands/output, absolute worktree/log/artifact
  paths, process IDs, environment values, credentials, and unbounded payloads.
- Logs and artifacts remain explicitly `unavailable`. A future endpoint must
  return a bounded/cursor-based resource identified by durable IDs, include
  content type, byte/record limits and truncation metadata, apply server-side
  allowlisting/redaction, and never return a local filesystem path, environment,
  command array, or credential-bearing payload.
- A Builder URL deep link was not added because Kitty navigation currently owns
  view state in `page.tsx` rather than a route-per-panel model. Builder follows
  that existing boundary instead of introducing one special-case router.

## Verification

- Full Builder backend selection: **616 passed** outside the filesystem/process
  sandbox. The sandboxed run was **561 passed, 55 failed** solely on denied
  `ps`/`killpg`/default artifact writes; the unrestricted rerun is the result to
  trust.
- Focused status + initiative suite: **115 passed**.
- Complete Kitty frontend suite: **150 passed**.
- Focused Builder/Home frontend suite: **52 passed**.
- TypeScript: `tsc --noEmit --incremental false` passed.
- Ruff on changed Python source/tests passed; mypy on the three changed Python
  source modules passed; `git diff --check` passed.
- Browser QA: **24 scenarios** across desktop and 390x844 mobile. It covered all
  nine failure categories, active/successful runs, publication links, more than
  ten attempts, partial evidence, duplicate IDs, stale/unavailable/empty/fetch
  failure, focus restoration, and Chats/Home isolation. No reproducible Builder
  UI defect was found and the mobile document had no horizontal overflow.
- Production Webpack compilation and standalone TypeScript validation pass after
  moving proxy configuration helpers out of
  `src/app/proxy/[...path]/route.ts`. The route now exports only HTTP handlers,
  as required by Next 16; configuration precedence and secret handling are
  unchanged and remain covered by the existing proxy tests.

## Repository hygiene

- No tracked generated file is present. Inspected ignored runtime artifacts are
  `data/kittybuilder/`, `gateway/kitty-chat/.next/`,
  `gateway/kitty-chat/next-env.d.ts`, and the intentional frontend
  `node_modules` link; none is staged or committed.
- No dependency was added. A pnpm launch briefly displaced packages under the
  linked `node_modules`; it was stopped, the exact packages were restored, and
  the full 150-test frontend suite passed afterward.

## Remaining action

- Push the focused release repairs, verify the refreshed required checks on PR
  #183, then merge. Keep the Builder surface read-only and preserve the existing
  worktrees.

---

## Historical checkpoint preserved below

### Session State — 2026-07-16 — Engineering Leverage closeout

## Current truth

- Branch: `chore/engineering-leverage-phase-8-9`
- Base: `origin/main @ 6cd464fe6f867b6cd90a7f8d5e6c63ac8239c753`
- One-branch/one-PR decision remains intentional; history was not rewritten.
- The four worktrees listed in `.claude/HANDOFF.md` were inspected read-only and preserved.
- Builder initiative `kb_mrm5ru85_9ea7` remains cancelled and was not restarted.
- No push, merge, force-push, branch deletion, or worktree cleanup occurred.

## Builder Phase 2 identity gap closed

- `7ceb511` — atomic packet lease + attempt creation is now the production path in
  `run_packet`; attempts retain their lease ID and every deliberate close releases
  the exact packet/worker-owned lease in the same transaction.
- Post-worker verification now checks the active lease, worker, branch, canonical
  worktree path, durable base ancestry, packet marker on every commit (including
  merges), and committed/staged/unstaged/untracked scope drift before validation.
- Success, implementation failure, identity failure, validation failure,
  cancellation, lease loss, orchestration exception, retry, exhaustion, and stale
  crash reconciliation all have explicit lease and attempt outcomes.
- The three former strict xfails are ordinary passing integration tests.
- `aee7c4a` — first manifest apply now fails before mutation if neither
  `origin/main` nor `main` resolves to a durable full SHA; dry runs and immutable
  re-applies do not unnecessarily depend on live refs.
- `3a7e798` — the initiative-driver tests bind manifest creation to their isolated
  temporary Git repository.

## Whole-branch integration corrections

- `c2584bb` — the newly expanded `mcp/` Ruff/mypy CI target is actually green;
  the branch no longer adds a known-red required check.
- Removed stale active-code and canonical-architecture references to the deleted
  `gateway/context_builder.py` facade.
- Corrected `SKILL_REGISTRY.md`: the live `.agents/skills/` count is 17, three
  nonexistent skills were removed, and Jacob's H5 archive decision is recorded
  as deferred execution rather than an open decision.
- Updated the audit bridge, project status, handoff, and PR narrative to match the
  implemented identity contract. No audit `—` or `⏸` row was promoted to `✓`.

## Validation

- Combined closeout suite: **504 passed** in 114.65s.
- Identity + loop suite: **65 passed**.
- Focused queue/attempt/runner/identity/loop suite: **324 passed**.
- Manifest/attempt/loop suite after durable-base fix: **179 passed**.
- Initiative driver: **7 passed**.
- Ruff: `gateway/ tests/ mcp/` — all checks passed.
- Mypy: 36 affected Builder/context/doctor/MCP source files — no issues.
- MCP-only mypy: 25 source files — no issues.
- Vulture: `gateway/ --min-confidence 80` — 0 findings.
- Lychee: 102 links OK, 0 errors, 7 redirects.
- Full suite: 2241 passed, 1 skipped, 2 deselected, 4 failed before closeout
  fixes. The three Builder failures were caused by the temporary-repo base mismatch
  and now pass in `tests/test_builder_run.py` (7/7). The one remaining unchanged
  failure is `test_expired_creds_refresh`, which cannot import optional
  `google.auth`; neither the mail connector nor its test differs from `origin/main`.
- `./kitty doctor --json`: 4 PASS, 4 WARN, 5 FAIL. The failures are local runtime
  prerequisites/services (`.env`, `venv`, Gateway, LiteLLM, mem0), not code-test
  failures; CodeGraph reports its existing dead-daemon warning.

## Remaining scope

- Mechanical audit rows D2/A1, A2/H5, and D4/A3 remain intentionally deferred
  under their evidence/migration gates. They are suitable for a cheaper worker.
- The Builder UI was not implemented. `.claude/HANDOFF.md` contains the exact
  read-only projection contract and implementation-ready next task.
- T2 cards remain untouched: UI/auth/SSRF boundaries and agent/task-runner
  false-completion/stop reliability.
