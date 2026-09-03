# Coordination Kernel MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that two supported Kitty agents cannot both own conflicting mutation scope and that staged mutation outside the winning claim is rejected.

**Architecture:** Store short-lived interactive claims in Kitty's existing SQLite state database. Acquire mutating ownership atomically with `BEGIN IMMEDIATE`, detect semantic and path overlap before insert, expose lifecycle/guard operations through a dedicated CLI, and call the guard from the pre-commit hook template. GAR receives lifecycle projections but is not the mutex.

**Tech Stack:** Python 3.12+, SQLite, existing `gateway.db` migrations, argparse, pytest, shell pre-commit template.

**Spec:** `docs/superpowers/specs/2026-09-03-kitty-multi-agent-amplifier-design.md`

## Global Constraints
- Git/GitHub remain publication truth.
- KittyBuilder remains engineering execution authority; this milestone does not mutate Builder task state.
- `workspace_global` remains communication truth; GAR messages are projections, not locks.
- `OWN` and `INTEGRATE` are the only mutating roles in this milestone.
- Claims fail closed on missing/expired ownership for mutation guard operations.
- No paid provider execution, roadmap activation, autonomous dispatch, or merge.

---

### Task 1: Claim schema and atomic lifecycle
**Files:** create `gateway/migrations/056_agent_coordination_claims.sql`, `gateway/agent_coordination.py`; test `tests/test_agent_coordination.py`.
**Interfaces:** `claim(...) -> dict`, `renew(claim_id, session_id, lease_seconds=...) -> dict`, `release(claim_id, session_id) -> dict`, `list_claims(active_only=True) -> list[dict]`.
- [ ] Write tests that import the missing module and define claim lifecycle expectations.
- [ ] Run focused tests and verify RED from missing behavior.
- [ ] Add migration with claim row plus JSON path/resource payloads and useful active/worktree indexes.
- [ ] Implement input normalization, `BEGIN IMMEDIATE` claim acquisition, lease renewal, release, and active listing.
- [ ] Run focused tests GREEN and commit the coherent lifecycle slice.

### Task 2: Collision semantics
**Files:** modify `gateway/agent_coordination.py`, `tests/test_agent_coordination.py`.
**Interfaces:** `find_conflicts(...) -> list[dict]`; path overlap is segment-aware ancestry; semantic overlap is exact normalized resource equality for MVP.
- [ ] Add RED tests for same resource conflict, directory/file ancestry conflict, unrelated mutation coexistence, and REVIEW/RESEARCH coexistence.
- [ ] Implement minimal normalized conflict detection inside the same immediate transaction used by `claim`.
- [ ] Verify simultaneous attempts serialize so only one conflicting mutating claim succeeds.
- [ ] Run focused tests GREEN and commit.

### Task 3: Mutation guard
**Files:** modify `gateway/agent_coordination.py`, `tests/test_agent_coordination.py`.
**Interfaces:** `guard_paths(worktree_path: str, paths: list[str], now: float | None = None) -> dict` returning the authorizing claim and normalized covered paths or raising `CoordinationClaimError`.
- [ ] Add RED tests for no claim, expired claim, uncovered staged path, and covered staged path.
- [ ] Implement worktree-bound active claim resolution and path-fence coverage.
- [ ] Verify the guard never authorizes REVIEW/RESEARCH claims.
- [ ] Run focused tests GREEN and commit.

### Task 4: CLI and launcher seam
**Files:** create `gateway/agent_coordination_cli.py`; modify `kitty`; test `tests/test_agent_coordination_cli.py`.
**Interfaces:** `./kitty agent claim|renew|release|status|guard` with `--json`; repeated `--path` and `--resource`; `guard --staged` obtains staged paths from Git.
- [ ] Write CLI RED tests for claim JSON, conflict exit code, status visibility, and staged guard failure.
- [ ] Implement argparse CLI and one `cmd_agent` launcher dispatch analogous to `cmd_room`.
- [ ] Ensure worktrees resolve the shared canonical Kitty data root exactly as `cmd_room` does.
- [ ] Run CLI tests GREEN and commit.

### Task 5: GAR lifecycle projection
**Files:** modify `gateway/agent_coordination.py` or CLI projection seam; test focused projection behavior.
**Interfaces:** successful claim/release can post bounded `status`/`result` messages using existing `agent_workspace.post_global_message`; projection failure must not create false ownership success or silently erase the claim.
- [ ] Add RED tests proving claim truth is committed atomically and projection is explicitly reported when unavailable.
- [ ] Implement bounded projection for acquire/conflict/release; renew remains silent.
- [ ] Run focused tests GREEN and commit.

### Task 6: Git mutation backstop
**Files:** modify `scripts/pre-commit.template`; test `tests/test_agent_coordination_hook.py` or focused shell test.
**Interfaces:** before expensive tests, staged mutation invokes `./kitty agent guard --staged`; missing/expired/out-of-scope claims return nonzero with owner/scope guidance.
- [ ] Add RED test showing an uncovered staged file would currently reach the test runner.
- [ ] Add the guard before the existing metadata/full-test logic.
- [ ] Verify a covered claim passes the guard and existing metadata/test behavior is preserved.
- [ ] Run focused hook tests GREEN and commit.

### Task 7: Exact-head acceptance and publication
**Files:** no new product scope.
- [ ] Run coordination tests, agent-room lifecycle regressions, migration tests, Ruff, and `git diff --check`.
- [ ] Demonstrate two independent processes racing for one semantic resource: exactly one succeeds.
- [ ] Demonstrate a winning claim cannot commit a staged path outside its path fence using the guard directly in the isolated worktree.
- [ ] Re-fetch remote main and re-run overlap check before publication.
- [ ] Push the non-main branch and open a reviewable PR; do not merge.
- [ ] Post exact SHA, tests, race proof, residual limitations, and next step to GAR/#490.
