# Agent Runtime Lifecycle Checkpoint 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every Builder worker launch to one durable run identity with a persisted creation-time worktree identity and an atomic, complete KX semantic claim set that stays live until the run terminates.

**Architecture:** Keep Builder queue leases as scheduling ownership and KX as semantic mutation ownership. Persist a deterministic `runs/<run_id>/ownership.json` sidecar beside the existing Builder run record, use public `run_workspace` authentication/verification APIs, add one transactional KX multi-acquire operation plus conservative declared-scope resolution, and couple KX renewal/release to the existing Builder heartbeat/finalization lifecycle.

**Tech Stack:** Python 3.12, SQLite WAL, Git worktrees, pytest, existing Kitty Builder/KX modules.

**Spec:** `docs/superpowers/specs/2026-09-04-agent-runtime-lifecycle-checkpoint-2-design.md`

## Global Constraints

- No new daemon, scheduler, claim store, GAR ownership semantics, or autonomous dispatch.
- Queue lease and KX ownership remain separate trust domains joined only by durable run identity.
- Worker launch is forbidden until queue lease, durable run, authenticated worktree, semantic resolution, and full atomic KX acquisition all succeed.
- No production code is written before a focused failing test demonstrates the missing behavior.
- GAR projection failures remain non-authoritative and never roll back successful SQLite ownership state.
- Preserve all checkpoint-1 containment behavior, including trusted audit of already-authenticated worktrees.
- Use the existing deterministic Builder task worktree layout; do not migrate Builder to a second worktree manager.

---### Task 1: Persistable Worktree Identity

**Files:**
- Modify: `gateway/run_workspace.py`
- Test: `tests/test_run_workspace.py`

**Interfaces:**
- Produces: `authenticate_existing_worktree(repo: Path, worktree: Path, *, base_commit: str) -> WorktreeIdentity`
- Produces: `verify_worktree_identity(identity: WorktreeIdentity, *, repo: Path, worktree: Path) -> None`
- Produces: `WorktreeIdentity.to_payload() -> dict[str, str]`
- Produces: `WorktreeIdentity.from_payload(payload: Mapping[str, Any]) -> WorktreeIdentity`

- [ ] **Step 1: Write failing serialization/authentication tests**

```python
identity = authenticate_existing_worktree(repo, worktree, base_commit=base)
payload = identity.to_payload()
restored = WorktreeIdentity.from_payload(payload)
assert restored == identity
verify_worktree_identity(restored, repo=repo, worktree=worktree)
```

Add a second test that rewrites the worktree `.git` file after authentication and asserts `verify_worktree_identity(...)` raises `RunWorkspaceError` without changing the existing `GitWorktreeManager.audit` tamper test.

- [ ] **Step 2: Run the two tests and verify RED**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q tests/test_run_workspace.py -k 'persisted or verify_worktree_identity'`
Expected: FAIL because the public persistence/verification API does not exist.- [ ] **Step 3: Implement the minimal public identity API**

`authenticate_existing_worktree` must resolve the controlling repo git/common dirs, the exact linked-worktree git/common dirs, verify common-dir equality and base ancestry, and return a frozen `WorktreeIdentity`. `verify_worktree_identity` must compare live repo/worktree discovery to every persisted path field and then call the trusted base verifier.

`to_payload` / `from_payload` serialize only these exact string keys:

```python
{
    "repo_git_dir": str(identity.repo_git_dir),
    "repo_common_dir": str(identity.repo_common_dir),
    "worktree_git_dir": str(identity.worktree_git_dir),
    "base_commit": identity.base_commit,
}
```

- [ ] **Step 4: Run the full run-workspace suite GREEN**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q tests/test_run_workspace.py`
Expected: PASS, including the existing checkpoint-1 tamper audit behavior.

- [ ] **Step 5: Commit Task 1**

```bash
git add gateway/run_workspace.py tests/test_run_workspace.py
git commit -m "feat(runtime): persist builder worktree identity"
```

### Task 2: Atomic KX Scope Acquisition

**Files:**
- Modify: `gateway/agent_coordination.py`
- Test: `tests/test_agent_coordination_acceptance.py`

**Interfaces:**
- Produces: `resolve_scopes_to_resources(scopes: Iterable[str], *, registry_path: Path | None = None) -> list[str]`
- Produces: `acquire_many(session_id: str, *, role: str, resource_ids: Iterable[str], base_sha: str, paths: Iterable[str], participant: str | None = None, lane: str | None = None, task_id: str | None = None, branch: str | None = None, worktree: str | None = None, lease_seconds: int = DEFAULT_LEASE_SECONDS, db_path: Path | None = None, registry_path: Path | None = None, now: str | datetime | None = None) -> dict[str, Any]`- [ ] **Step 1: Write failing KX tests**

Add tests proving:

```python
result = agent_coordination.acquire_many(
    session_id="loser",
    role="OWN",
    resource_ids=["docs:roadmap", "runtime:provenance"],
    base_sha=BASE,
    paths=["docs/ROADMAP.md", "gateway/runtime_manifest.py"],
    db_path=db_path,
    registry_path=registry_path,
    now=T0,
)
assert result["status"] == "CONFLICT"
assert agent_coordination.list_claims(db_path=db_path, now=T0) == [existing_owner]
```

Also add a spawned-process race where two `acquire_many` calls overlap one resource and assert at most one set is acquired, plus scope-resolution cases for an exact file, a directory prefix, and an unmapped scope.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q tests/test_agent_coordination_acceptance.py -k 'many or scope'`
Expected: FAIL because `acquire_many` / `resolve_scopes_to_resources` do not exist.

- [ ] **Step 3: Implement one-transaction multi-acquire**

Use one `BEGIN IMMEDIATE`: validate/sort/dedupe the full resource set, expire stale rows, query all active conflicting mutators for requested resources, and if any exist commit only expiry work and return `{"status": "CONFLICT", "holders": [...]}`. Otherwise insert every claim before one commit and return `{"status": "ACQUIRED", "claims": [...]}`. Project GAR events only after the transaction commits.

`resolve_scopes_to_resources` treats Builder scopes as repo-relative prefixes. It returns every registry resource whose path pattern overlaps the declared prefix conservatively; a scope with zero overlaps is unresolved and Builder must reject it.

- [ ] **Step 4: Run KX acceptance GREEN**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q tests/test_agent_coordination_acceptance.py`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add gateway/agent_coordination.py tests/test_agent_coordination_acceptance.py
git commit -m "feat(coordination): acquire builder resource sets atomically"
```### Task 3: Durable Ownership Manifest and Launch Ordering

**Files:**
- Modify: `gateway/builder_runner.py`
- Test: `tests/test_builder_runner.py`

**Interfaces:**
- Consumes: Task 1 worktree identity APIs.
- Consumes: Task 2 KX resolver/multi-acquire APIs.
- Produces: deterministic `runs/<run_id>/ownership.json` with schema version 1.
- Adds optional test seams to `run_worker`: `coordination_db_path: Path | None = None`, `coordination_registry_path: Path | None = None`.

Ownership payload:

```python
{
    "version": 1,
    "run_id": run_id,
    "kx_session_id": f"builder-run:{run_id}",
    "task_id": task_id,
    "branch": branch,
    "worktree": str(wt_path),
    "declared_paths": sorted(task["allowed_paths"]),
    "required_resources": required_resources,
    "worktree_identity": identity.to_payload(),
}
```

- [ ] **Step 1: Write failing launch-ordering tests**

Add one successful run test asserting the sidecar exists and persisted identity verifies. Add setup-failure tests for empty/unmapped allowed paths and KX conflict that patch `subprocess.Popen` and assert it is never reached. Assert zero active KX claims remain for the generated `builder-run:<run_id>` session after setup failure.

- [ ] **Step 2: Run the new runner tests and verify RED**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q -m integration tests/test_builder_runner.py -k 'ownership or kx or unmapped'`
Expected: FAIL because Builder does not create the ownership sidecar or acquire KX.- [ ] **Step 3: Implement prelaunch ownership sequence**

Inside `run_worker`, after `ensure_worktree` and before `Popen`:

1. authenticate the exact worktree against `root` and `start_sha`;
2. create the existing durable Builder run row;
3. create `run_dir` and atomically write `ownership.json` via temp file + `os.replace`;
4. resolve all declared Builder scopes to semantic resources and fail if the declaration is empty or any scope resolves to zero resources;
5. atomically acquire the complete KX set using `session_id=f"builder-run:{run_id}"`;
6. re-read the persisted ownership file and verify the exact stored identity immediately before spawn;
7. set runner-owned `KB_KX_SESSION_ID` and `KB_OWNERSHIP_PATH` environment variables.

Any failure after the run row exists must finalize that run as `RUN_FAILED` / `runner_setup_failed`; any acquired KX claims must be released in cleanup. Any failure before run creation returns the queue lease as today.

- [ ] **Step 4: Run launch-ordering tests GREEN**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q -m integration tests/test_builder_runner.py -k 'ownership or kx or unmapped'`
Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add gateway/builder_runner.py tests/test_builder_runner.py
git commit -m "feat(builder): bind launches to durable kx ownership"
```

### Task 4: Coupled Heartbeat, Tamper Detection, and Cleanup

**Files:**
- Modify: `gateway/builder_runner.py`
- Test: `tests/test_builder_runner.py`

**Interfaces:**
- Consumes: persisted ownership sidecar from Task 3.
- KX renew uses the same `kx_session_id` and `lease_seconds` as the run's acquisition.
- KX release is idempotent and runs from one final cleanup path.

- [ ] **Step 1: Write failing lifetime tests**

Add focused tests proving KX renewal failure terminates a long-lived worker and no later run heartbeat is recorded; replacing/tampering the worktree identity during a live run terminates it at the next control-loop verification; and normal exit, nonzero exit, timeout, cancellation, launch failure, and setup failure each leave zero active KX claims for the run.- [ ] **Step 2: Run lifetime tests and verify RED**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q -m integration tests/test_builder_runner.py -k 'renewal or tamper or cleanup'`
Expected: at least the new KX/tamper assertions fail.

- [ ] **Step 3: Couple ownership in the control loop**

On each heartbeat iteration, perform in order: queue `renew_lease`, KX `renew`, persisted worktree identity verification, current mutation snapshot + `agent_coordination.preflight_mutation` against the run KX session, then `bq.update_run(... mark_heartbeat=True)`. Any queue/KX/identity/preflight failure terminates the process group and prevents a success heartbeat.

After process exit, fence both queue and KX once more before classifying success. In a `finally`-equivalent cleanup path, release the run's KX session regardless of normal exit, failure, timeout, cancellation, setup failure, or launch failure. Preserve expiry as crash-recovery fallback.

- [ ] **Step 4: Run full runner suite GREEN**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q -m integration tests/test_builder_runner.py`
Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add gateway/builder_runner.py tests/test_builder_runner.py
git commit -m "feat(builder): couple kx authority to worker lifetime"
```

### Task 5: Checkpoint Regression and Review Evidence

**Files:**
- Modify only if a focused regression exposes a checkpoint-2 defect in already-owned files.

- [ ] **Step 1: Run checkpoint suites**

Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q tests/test_run_workspace.py tests/test_builder_contract_gate.py tests/test_agent_coordination_acceptance.py`
Run: `/Users/jacobbrizinnski/Projects/kitty/venv/bin/python -m pytest -q -m integration tests/test_builder_runner.py tests/test_builder_loop.py tests/test_discord_command_center_phase0.py`
Expected: all PASS.

- [ ] **Step 2: Run focused static checks**

Run Ruff on changed Python files and focused mypy on `gateway/run_workspace.py gateway/agent_coordination.py gateway/builder_runner.py` using the shared validation environment. Expected: PASS.

- [ ] **Step 3: Run real KX staged preflight before every remaining commit/push**

Run: `./kitty agent preflight --staged --json`
Expected: `"ok": true` and only the currently owned semantic resources.

- [ ] **Step 4: Review the final diff against the spec**

Verify no queue/KX trust-domain merge, no partial claim path, no audit-time-only Builder identity fallback, no worker launch before ownership, and no unrelated product/UI changes.
