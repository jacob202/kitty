# KittyBuilder MCP Bridge v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose KittyBuilder through a small, standards-based MCP server that gives conversational clients trustworthy staged context, durable continuity, governed planning writes, and high-level Builder controls without creating a second execution authority.

**Architecture:** Add a focused `mcp/builder/` adapter package. Read tools compose the existing `gateway.context_receipt` and `gateway.builder_status` projections plus allowlisted Git reads. Mutation tools call canonical Git/Builder APIs and preserve existing execution ownership, approval, fencing, recovery, budget, and publication rules. The MCP server itself owns no task database or workflow state.

**Tech Stack:** Python 3.12, official Model Context Protocol Python SDK/FastMCP, existing Kitty Gateway/Builder Python APIs, Git CLI, pytest.

## Global Constraints

- KPROOF-001 remains the active product mission and scope gate.
- Do not expose unrestricted shell, arbitrary filesystem writes, direct Builder SQLite mutation, raw push/merge, secrets, auth/env, spending, deletes, or heavy dependencies.
- Builder remains authoritative for task/attempt/lease/run/review/publication state.
- `gateway.context_receipt.build_context_receipt()` remains authoritative for cold-start context.
- `gateway.builder_status.build_status_snapshot()` remains authoritative for detailed Builder runtime projection.
- Unknown/unavailable evidence stays unknown; never convert it to success or zero.
- MCP transport must support local stdio and Streamable HTTP; HTTP binds locally by default.
- Planning writes are restricted to `docs/superpowers/specs/` and `docs/superpowers/plans/` and require explicit SHA preconditions.
- No MCP request must need to remain open for the lifetime of a long Builder run.
- Chat/model narration is never execution truth.

---

## File Structure

- Create `mcp/builder/__init__.py` — package marker and public server import.
- Create `mcp/builder/schemas.py` — shared receipt helpers and bounded public response shapes.
- Create `mcp/builder/repo_tools.py` — canonical repo detection, allowlisted tracked reads/search, SHA-bound planning artifact writes.
- Create `mcp/builder/context.py` — Kitty context, Builder status/result filtering, `resume_context()` composition.
- Create `mcp/builder/commands.py` — high-level canonical Builder command adapters only.
- Create `mcp/builder/server.py` — FastMCP registration and transport entry point; no domain logic.
- Create `mcp/builder/requirements.txt` — MCP SDK dependency for standalone/local installation, matching the existing Imagen MCP pattern.
- Create `tests/test_mcp_builder_repo_tools.py` — path/security/read/write tests.
- Create `tests/test_mcp_builder_context.py` — context/status/result tests.
- Create `tests/test_mcp_builder_continuity.py` — fresh-session bounded handoff contract.
- Create `tests/test_mcp_builder_commands.py` — delegation/idempotency/refusal tests.
- Create `tests/test_mcp_builder_server.py` — tool registration/transport import tests with SDK stubs.
- Create `docs/KITTYBUILDER_MCP.md` — local setup, client contract, security and current external-client limitations.

---

### Task 1: Secure Repository Read Boundary

**Files:**
- Create: `tests/test_mcp_builder_repo_tools.py`
- Create: `mcp/builder/__init__.py`
- Create: `mcp/builder/repo_tools.py`

**Interfaces:**
- Produces: `repo_root() -> Path`
- Produces: `repo_head() -> str`
- Produces: `read_tracked_file(path: str, ref: str | None = None, start_line: int | None = None, end_line: int | None = None) -> dict`
- Produces: `search_tracked_repo(query: str, path: str | None = None, ref: str | None = None, limit: int = 20) -> dict`
- Produces: `write_planning_artifact(kind: Literal["design","plan"], slug: str, markdown: str, expected_base_sha: str, expected_dependency_sha: str | None = None) -> dict`

- [ ] **Step 1: Write failing tests for read allowlisting**

Tests prove that tracked Markdown/Python files can be read, while absolute paths, `..`, `.env*`, `data/`, `logs/`, `.git/`, runtime databases and untracked files are rejected.

- [ ] **Step 2: Run the narrow test and confirm RED**

Run: `python3.12 -m pytest tests/test_mcp_builder_repo_tools.py -q`
Expected: import/feature failure because `mcp.builder.repo_tools` does not exist.

- [ ] **Step 3: Implement canonical repo resolution and tracked reads**

Use `git rev-parse --show-toplevel`, `git rev-parse HEAD`, `git ls-files --error-unmatch`, and `git show <ref>:<path>`. Never read an arbitrary filesystem path supplied by the client.

- [ ] **Step 4: Add failing search tests**

Prove search is literal/bounded, operates only over tracked files, and respects optional path/ref without shell interpolation.

- [ ] **Step 5: Implement search using argv-only Git commands**

Use `git grep -n -F --max-count=<bounded>` or an equivalent argv-only tracked-file search. Reject blank queries and cap result count/snippet size.

- [ ] **Step 6: Add failing planning-write tests**

Prove the function derives its destination itself, rejects invalid slugs, refuses a stale `expected_base_sha`, refuses plan/design dependency mismatch, and cannot write outside the two planning directories.

- [ ] **Step 7: Implement planning artifact writes**

Use a generated path `docs/superpowers/specs/YYYY-MM-DD-<slug>-design.md` or `docs/superpowers/plans/YYYY-MM-DD-<slug>.md`; use Git SHA preconditions and a scoped Git commit path. Do not expose arbitrary `path` or `git` arguments.

- [ ] **Step 8: Run the narrow tests and confirm GREEN**

Run: `python3.12 -m pytest tests/test_mcp_builder_repo_tools.py -q`
Expected: all tests pass.

- [ ] **Step 9: Commit**

`git commit -m "feat(mcp): add secure Builder repo tools"`

---

### Task 2: Context, Status, Result, and Fresh-Chat Continuity

**Files:**
- Create: `tests/test_mcp_builder_context.py`
- Create: `tests/test_mcp_builder_continuity.py`
- Create: `mcp/builder/schemas.py`
- Create: `mcp/builder/context.py`

**Interfaces:**
- Produces: `kitty_context() -> dict`
- Produces: `work_status(mission_id: str | None = None, task_id: str | None = None) -> dict`
- Produces: `work_result(mission_id: str | None = None, task_id: str | None = None) -> dict`
- Produces: `resume_context(mission_id: str | None = None, task_id: str | None = None) -> dict`
- Produces: `receipt(operation: str, *, ok: bool, ...) -> dict`

- [ ] **Step 1: Write failing `kitty_context()` tests**

Patch `build_context_receipt()` and prove the MCP adapter returns the authoritative receipt plus only bounded MCP metadata; it must not reinterpret failing continuity checks as success.

- [ ] **Step 2: Run tests and confirm RED**

Run: `python3.12 -m pytest tests/test_mcp_builder_context.py -q`

- [ ] **Step 3: Implement context adapter**

Call `gateway.context_receipt.build_context_receipt(repo_root())` directly.

- [ ] **Step 4: Write failing Builder filtering tests**

Provide synthetic `build_status_snapshot()` data and prove mission/task filters return exact matching durable projections, unknown IDs fail loudly, and task state is never inferred from worker narration.

- [ ] **Step 5: Implement `work_status()` / `work_result()`**

Read only through `gateway.builder_status.build_status_snapshot()`. `work_result()` selects the latest durable attempt/publication/result evidence already present in the snapshot and labels missing evidence as unavailable rather than complete.

- [ ] **Step 6: Write fresh-session continuity tests**

Construct a synthetic repo/context/status containing an active mission, design/plan paths, SHAs, task state, evidence, PR and blocker. Assert `resume_context()` returns objective, artifacts, execution owner, current state, verified evidence, PR, blocker, and exactly one next action without requiring any conversation transcript.

- [ ] **Step 7: Implement bounded `resume_context()`**

Compose only authoritative durable fields. Include source paths/SHAs/freshness. Cap recent events/evidence and omit giant worker output.

- [ ] **Step 8: Run both test files and confirm GREEN**

Run: `python3.12 -m pytest tests/test_mcp_builder_context.py tests/test_mcp_builder_continuity.py -q`

- [ ] **Step 9: Commit**

`git commit -m "feat(mcp): add Builder continuity projection"`

---

### Task 3: Governed Builder Commands

**Files:**
- Create: `tests/test_mcp_builder_commands.py`
- Create: `mcp/builder/commands.py`

**Interfaces:**
- Produces: `mission_prepare(manifest: dict, *, expected_base_sha: str) -> dict`
- Produces: `mission_approve(manifest: dict, *, expected_manifest_sha: str, approval_nonce: str) -> dict`
- Produces: `execution_start(mission_id: str, packet_id: str | None = None, *, free: bool = True) -> dict`
- Produces: `execution_pause(mission_id: str, reason: str) -> dict`
- Produces: `execution_resume(mission_id: str) -> dict`
- Produces: `execution_cancel(task_id: str, reason: str) -> dict`
- Produces: `publication_status(...) -> dict`

- [ ] **Step 1: Write failing prepare/approval tests**

Prove `mission_prepare` uses Builder's existing `validate_manifest`, `warn_manifest`, `manifest_sha256`, and dry-run `apply_manifest`; it never mutates durable state. The returned approval nonce is deterministically bound to schema version + manifest digest + expected base SHA. Any manifest/base change invalidates it.

- [ ] **Step 2: Implement prepare**

Return validation errors/warnings and exact manifest digest. Do not create tasks.

- [ ] **Step 3: Write approval tests**

Prove approval rejects stale digest/nonce/base SHA and delegates the accepted immutable manifest to `apply_manifest`. Repeated identical approval must return existing/unchanged rather than duplicate tasks.

- [ ] **Step 4: Implement approval**

Treat the nonce as a stale-version binding, not as authentication. Human confirmation remains a client/UI responsibility. Rely on Builder's immutable/idempotent apply contract to make replay harmless.

- [ ] **Step 5: Write pause/resume/cancel tests**

Patch canonical Builder functions and assert exact delegation, actor/reason propagation and structured failures.

- [ ] **Step 6: Implement pause/resume/cancel adapters**

Call existing `gateway.builder_initiative.pause_initiative`, `resume_initiative`, and supported queue cancellation functions; never mutate tables.

- [ ] **Step 7: Write execution-start tests**

Prove existing live/running work is returned rather than duplicated. For v1, execution start may delegate to the existing bounded Builder initiative/packet runner through an argv-only detached child process, but the response must return durable IDs promptly and later truth must come from Builder projections.

- [ ] **Step 8: Implement minimal execution start**

Prefer an existing Python API if it can detach safely; otherwise spawn `./kitty builder initiative run ...`/`run-packet ...` with a fixed argv template and no arbitrary command input. Refuse when durable state shows a collision.

- [ ] **Step 9: Run tests and confirm GREEN**

Run: `python3.12 -m pytest tests/test_mcp_builder_commands.py -q`

- [ ] **Step 10: Commit**

`git commit -m "feat(mcp): add governed Builder commands"`

---

### Task 4: FastMCP Server Surface

**Files:**
- Create: `tests/test_mcp_builder_server.py`
- Create: `mcp/builder/server.py`
- Create: `mcp/builder/requirements.txt`

**Interfaces:**
- Server name: `kittybuilder`
- Local default: stdio
- Optional deployed transport: Streamable HTTP, local bind by default

- [ ] **Step 1: Write failing server import/registration tests**

Stub `mcp.server.fastmcp.FastMCP` using the existing `tests/test_mcp_imagen.py` pattern. Assert the public tools are registered and the module imports without opening sockets or touching Builder state.

- [ ] **Step 2: Implement server registration only**

Tool functions delegate directly to `context.py`, `repo_tools.py`, and `commands.py`. `server.py` contains no queue/Git mutation logic.

- [ ] **Step 3: Add transport entry point**

`main()` defaults to stdio. An explicit environment/CLI mode may run `streamable-http`; HTTP host defaults to `127.0.0.1`. Do not expose a public bind by default.

- [ ] **Step 4: Add standalone MCP requirements**

Use the official Python SDK requirement compatible with the repo's existing Imagen MCP approach; avoid adding image-only dependencies to root requirements.

- [ ] **Step 5: Run tests and confirm GREEN**

Run: `python3.12 -m pytest tests/test_mcp_builder_server.py -q`

- [ ] **Step 6: Commit**

`git commit -m "feat(mcp): expose KittyBuilder MCP server"`

---

### Task 5: Operator Documentation and KPROOF Acceptance Harness

**Files:**
- Create: `docs/KITTYBUILDER_MCP.md`
- Add/Modify: `tests/test_mcp_builder_continuity.py`

- [ ] **Step 1: Document local install/run**

Document stdio use, Streamable HTTP local bind, MCP Inspector example, and client setup without embedding secrets.

- [ ] **Step 2: Document authority/safety model**

State plainly that MCP is an adapter, Builder remains execution truth, planning writes are scoped, merge/spend/auth/delete policies remain unchanged, and repository content is untrusted data rather than permission.

- [ ] **Step 3: Document current external ChatGPT availability as a client gate**

Keep the server standards-based and client-agnostic. Do not encode product-plan checks into runtime code.

- [ ] **Step 4: Add continuity acceptance fixture**

The test creates/uses a fresh adapter invocation with no conversation state and proves that `resume_context()` alone exposes enough durable state to identify the approved design/plan, current work, evidence/PR/blocker and next action.

- [ ] **Step 5: Run the MCP test set**

Run: `python3.12 -m pytest tests/test_mcp_builder_*.py -q`
Expected: all MCP Builder tests pass.

- [ ] **Step 6: Quality gate for touched Python**

Run: `python3.12 -m compileall -q mcp/builder`
Run: `python3.12 -m pytest tests/test_mcp_builder_*.py -q`

- [ ] **Step 7: Commit**

`git commit -m "docs: add KittyBuilder MCP operating guide"`

---

## Final Verification

- [ ] `python3.12 -m compileall -q mcp/builder`
- [ ] `python3.12 -m pytest tests/test_mcp_builder_*.py -q`
- [ ] Confirm no MCP code imports or mutates Builder SQLite directly.
- [ ] Confirm tool surface exposes no arbitrary shell/path/write/push/merge primitive.
- [ ] Confirm `resume_context()` can seed a fresh session without transcript copying.
- [ ] Confirm repeated mission approval/execution requests cannot duplicate durable Builder work.
- [ ] Confirm HTTP transport binds only to loopback unless an operator explicitly changes deployment configuration.
- [ ] Inspect final diff and PR checks; report any unavailable verification as unavailable, not passed.
