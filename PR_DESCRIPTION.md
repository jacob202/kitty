# Engineering Leverage + Builder integrity closeout

> **Suggested title:** `chore(leverage): close audit work and enforce Builder identity`
> **Branch:** `chore/engineering-leverage-phase-8-9`
> **Base:** `origin/main @ 6cd464fe6f867b6cd90a7f8d5e6c63ac8239c753`

## Summary

This PR combines the low-risk Engineering Leverage implementation with the
Builder Phase 2 integrity work required to make that tooling safe to dogfood.
The result is one reviewable branch that removes verified friction, strengthens
CI, and turns the Builder branch-lease/identity contract into real production
behavior rather than test-only scaffolding.

### Builder execution integrity

- Atomically claim the packet's exclusive branch lease and create its attempt.
- Bind packet, worker, branch, canonical worktree path, durable base SHA, and
  attempt lease ID; reject drift rather than repairing it silently.
- Create new worktrees from the packet's immutable base SHA instead of the live
  `main` ref.
- Verify post-worker branch, ancestry, packet markers on every commit (including
  merges), and committed/staged/unstaged/untracked path scope before validation.
- Close the attempt and release the exact owner-fenced lease in one transaction.
- Give success, implementation/identity/validation failure, cancellation,
  lease loss, orchestration crash, retry, exhaustion, and stale reconciliation
  deliberate outcomes and budget semantics.
- Fail first-time manifest apply before mutation when no durable base ref exists;
  dry runs and unchanged re-applies remain independent of live refs.

The three former strict xfails in `TestLeaseIdentityIntegration` are now ordinary
passing integration tests. Additional tests cover detached HEAD, unmarked merge
commits, duplicate/corrupt lease migration, wrong-owner release rollback,
concurrent claims, cancellation, and blocked-task crash recovery.

### Engineering Leverage work

- Add CodeGraph freshness checks and keep generated CodeGraph data untracked.
- Add Vulture, Lychee, advisory Deptry, TruffleHog, and MCP Ruff/mypy coverage.
- Make the expanded MCP target green instead of adding a known-red CI gate.
- Remove the proven `context_builder` facade and migrate active callers to
  `context_assembler`; reconcile the canonical architecture reference.
- Extract shared ISC derivation/checking into `builder_isc.py` and add the
  KittyBench state-machine/ISC fixtures.
- Add `./kitty doctor --spend`, correct stale Honcho/status claims, remove the
  duplicate `second-opinion` skill, and add the corrected repo skill registry.
- Keep the audit's H1-H6 decisions and per-row implementation status as the
  authority for work intentionally left out.

### Why this remains one PR

Jacob selected one branch and one PR. The existing logical commits are retained
because each is independently reviewable and reversible; no rebase, squash, or
history rewrite was used. The two lanes compose: Engineering Leverage makes the
Builder cheaper to operate, while the identity closeout makes using Builder on
the repository safe enough to trust. Splitting now would duplicate the shared
schema, test, documentation, and CI reconciliation work.

## Reviewer guide

Suggested order:

1. `gateway/builder_queue.py` and `gateway/builder_attempt.py` — schema ownership,
   atomic claim/close, migration behavior, and owner fencing.
2. `gateway/builder_loop.py`, `gateway/builder_identity.py`,
   `gateway/builder_scope.py`, `gateway/builder_runner.py` — execution and all
   deliberate exit paths.
3. `tests/test_builder_identity.py`, `tests/test_builder_loop.py`, and
   `tests/test_builder_run.py` — integration evidence.
4. ISC/context/Doctor/CI changes, then the audit and closeout documentation.

## Branch-level defects corrected during closeout

- The partial Phase 2 port duplicated `branch_leases` ownership and left runtime
  attempts unbound because `run_packet` still called `start_attempt`.
- New worktrees were based on live `main`, allowing unrelated commits after
  packet creation to enter the worker ancestry.
- Lease release was optional/idempotent and could conceal missing or stale
  ownership; release is now exact and fail-loud.
- First manifest apply could store `base_sha = NULL` and fail much later during
  execution.
- The expanded MCP CI scope was not Ruff/mypy clean.
- The initiative integration harness stored Kitty's base SHA while running in a
  temporary repo, which the full suite exposed as an invalid worktree reference.
- Active architecture/registry docs still described a deleted facade, three
  nonexistent skills, and H5 as undecided.

## Test plan

- [x] Combined closeout suite (Doctor, ISC, gates, bench, queue, attempt, runner,
  identity, loop, initiative, initiative driver): **504 passed**
- [x] Builder identity + loop: **65 passed**
- [x] Focused queue/attempt/runner/identity/loop: **324 passed**
- [x] Manifest/attempt/loop after durable-base correction: **179 passed**
- [x] Initiative driver: **7 passed**
- [x] `python3.12 -m ruff check gateway/ tests/ mcp/` — all checks passed
- [x] Mypy over 36 affected Builder/context/Doctor/MCP source files — no issues
- [x] Mypy over `mcp/` — 25 source files, no issues
- [x] `vulture gateway/ --min-confidence 80 --exclude gateway/kitty-chat/` — 0 findings
- [x] `lychee --root-dir docs docs/` — 102 OK, 0 errors, 7 redirects
- [x] `git diff --check` and `git diff --check origin/main...HEAD`

Full-suite evidence: **2241 passed, 1 skipped, 2 deselected, 4 failed** before
the final closeout fixes. Three failures were the branch-caused temporary-repo
base mismatch; `tests/test_builder_run.py` now passes 7/7. The sole unchanged
failure is `tests/test_mail_connector.py::TestAuthFailures::test_expired_creds_refresh`,
which cannot import optional `google.auth`; the mail connector and test are
unchanged from `origin/main`.

`./kitty doctor --json` reports 4 PASS, 4 WARN, and 5 FAIL in this checkout. The
FAIL entries are explicit local prerequisites/services (`.env`, `venv`, Gateway,
LiteLLM, mem0); CodeGraph reports its existing dead-daemon warning.

## Audit disposition and out of scope

No pending or deferred audit row was promoted during the identity closeout.
These remain intentionally suitable for cheaper, evidence-gated follow-up:

- D2/A1 — inspect references/history for five root temporary artifacts.
- A2/H5 — archive eight generic skills without deleting their content.
- D4/A3/H2 — migrate unique `scripts/curation/` behavior before removal.

Also unchanged: the four active worktrees, cancelled initiative
`kb_mrm5ru85_9ea7`, user data under `data/`, generated CodeGraph data, T2
auth/SSRF work, and agent/task-runner false-completion/stop reliability.

The full Builder UI is deliberately not included. `.claude/HANDOFF.md` defines
the implementation-ready read projection, canonical owners/states, safe polling
behavior, operator-action gates, and fields that must not be exposed.

## Risk and rollback

The highest-risk area is crash/retry reconciliation across task leases, packet
leases, and attempts. It is covered by integration tests, but should still be
reviewed before the first live dogfood run. Database changes are additive and
idempotent; the worker-identity unique index deliberately fails loudly if an
old database already contains contradictory live worker leases.

Rollback should use normal commit reverts in reverse dependency order. Do not
rewrite shared history. No remote action, production migration, or user-data
mutation was performed by this branch.
