# KittyBuilder Orchestrator — Historical Phase 1A Build Plan

**Status:** Superseded historical baseline. Phase 1A shipped and Builder advanced
beyond the constraints below. Current architecture is owned by
`docs/ARCHITECTURE.md`; the Kitty → Mission → KittyBuilder decision is ADR 0017.
**Date:** 2026‑07‑09

## 1. Executive Summary

KittyBuilder currently relies on manual coordination via GitHub issue #127 and PR comments. This is brittle and does not scale.

We have surveyed major agent‑orchestration systems and converged on a **local‑first, SQLite‑backed orchestrator** that uses GitHub as an integration layer only.

This document records the **original Phase 1A architecture**. It separated the
durable local queue foundation from capabilities deferred at that time. Those
constraints describe that historical slice, not current Builder capability.
Phase 1A was intentionally minimal: a library-mode SQLite queue with a strict
state machine, fencing tokens, CLI, and no worker spawning, GitHub automation,
UI, or frameworks in that phase.

---

## 2. Design Principles & Constraints

### 2.1. Operating Assumptions (Phase 1)

- **Single user, single machine** — the authoritative queue lives locally.
- **Single forge** — GitHub is the supported PR/review surface.
- **Single repo first** — the Kitty repository.
- **Local‑first** — SQLite is acceptable because the queue is not shared across machines.
- **Human‑approved** — workers never merge, self‑approve, or broaden scope.
- **Coordination‑first** — Phase 1A provides durable task truth, not automation.

### 2.2. Operator‑Fit Constraints

KittyBuilder must solve Jacob’s real pain points:

- Copy/paste relay between LLM chats and GitHub
- Confusion around issue/PR/branch numbers
- Agent credit exhaustion mid‑task
- Stale branches and lost context
- Over‑broad prompts causing scope drift
- Uncertainty about which source of truth is current

Therefore the system enforces:

- One authoritative local row per task.
- One current state per task.
- One owner/lease or none.
- One current branch/PR link when applicable.
- Every mutation is legal, explicit, and logged.
- Every worker stop produces a final report, blocked reason, failed reason, or cancellation.
- No worker self‑selects broad work, silently expands scope, or self‑merges.
- GitHub comments never override local queue state after Phase 1A.

### 2.3. Hard Constraints for Phase 1A

Phase 1A **must not** include:

- Worker spawning or agent execution
- Worktree runner
- GitHub PR creation or merge automation
- UI / mission control dashboard
- HTTP daemon (library‑mode only)
- Docker or other sandboxing
- Any external framework (CrewAI, AutoGen, LangGraph, etc.)
- Reuse of the generic task runner (`gateway/task_runner.py`) or the old autonomous builder (`gateway/builder.py`)

---

## 3. Phase 1A Scope — Durable Local Queue Foundation

Phase 1A delivers a small, trustable core:

- **SQLite database** with explicit schema, stored at `data/kittybuilder/builder_queue.db` (separate from the generic `task_queue.db`).
- **Strict state machine** with legal transitions and event logging.
- **Atomic claim** with fencing tokens (`lease_token` + `claim_version`) to prevent stale writes.
- **Acceptance criteria** stored per task from day one.
- **CLI integration** under the existing `./kitty builder queue ...` namespace.
- **Comprehensive unit tests** covering creation, claims, state transitions, fencing, and concurrency.

No HTTP API or daemon is required — the CLI will import the queue module directly.

---

## 4. Detailed Phase 1A Architecture

### 4.1. Module & File Placement

- New module: `gateway/builder_queue.py` (or a small `gateway/builder_queue/` package if needed).
  Must **not** modify `gateway/builder.py` (autonomous pipeline) or `gateway/task_runner.py` (generic tasks).
- CLI extension: `gateway/builder_cli.py` gains a `queue` subcommand group.
- DB path: `data/kittybuilder/builder_queue.db` (use a new constant `BUILDER_QUEUE_DB` in `gateway/paths.py`, not the existing `TASK_DB`).

### 4.2. Data Model

**Phase 1A implements only the `tasks` and `events` tables.**
`runs`, `pr_links`, and `artifacts` are documented future tables and must **not** be created in Phase 1A.

```sql
-- Tasks
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,                  -- Time‑sortable ID (ULID‑like, no external dependency)
    title TEXT NOT NULL,
    description TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER DEFAULT 0,
    lease_owner TEXT,
    lease_token TEXT,
    lease_expires_at TIMESTAMP,
    claim_version INTEGER DEFAULT 0,
    acceptance_criteria_json TEXT,        -- JSON array of strings
    bridge_source TEXT,                   -- e.g., 'github_issue'
    bridge_issue TEXT,                    -- e.g., '#127'
    bridge_external_id TEXT,              -- e.g., GitHub comment ID (used for idempotency)
    bridge_comment_url TEXT,              -- kept for human reference, not used as unique key
    workflow_ref TEXT,                    -- future
    workflow_sha TEXT,                    -- future
    repo_path TEXT,                       -- future
    allowed_paths_json TEXT,              -- future file allowlist
    blocked_reason TEXT,
    last_error TEXT,
    final_report_json TEXT,               -- future
    archived_at TIMESTAMP,                -- soft‑archive timestamp for terminal tasks
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance index for claim query
CREATE INDEX idx_tasks_claim ON tasks(state, priority DESC, id ASC);

-- Idempotency: prevent duplicate bridge tasks (one per external comment ID)
CREATE UNIQUE INDEX idx_tasks_bridge_external
    ON tasks(bridge_source, bridge_external_id)
    WHERE bridge_source IS NOT NULL AND bridge_external_id IS NOT NULL;

-- Event Log (mandatory from Phase 1A)
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    run_id TEXT,                         -- NULL in Phase 1A
    type TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Append‑only enforcement
CREATE TRIGGER prevent_event_updates BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'Event log is append-only'); END;
CREATE TRIGGER prevent_event_deletes BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'Event log is append-only'); END;

-- Future tables (documented, NOT created in Phase 1A):
-- runs, pr_links, artifacts
```

**SQLite pragmas** to be set on every connection:

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;
```

**ID generation rule:**
Task IDs must be time‑sortable and unique (ULID‑style) but **must not introduce a third‑party dependency**. A tiny local helper (`kb_<unix_ms>_<random_hex>`) or standard UUID4 + `created_at` ordering is acceptable. The `id` column is still `TEXT PRIMARY KEY`.

### 4.3. State Machine — Corrected

Legal task states and transitions:

```
queued → claimed → running → pr_opened → awaiting_review → done

queued/claimed/running/awaiting_review/blocked → failed
queued/claimed/running/awaiting_review/blocked → cancelled
running → blocked
blocked → running (resume with same valid lease)
blocked → queued (operator release)
blocked → failed
blocked → cancelled
```

**Important restrictions:**

- `claimed → queued` is allowed only:
  - via explicit **worker release** with valid `lease_token` and `claim_version`, or
  - via **operator release** with reason, or
  - via claimed-lease expiry **before any execution starts** (recovery scan).
- `running → queued` is **never** allowed directly. A running task must first be moved to `blocked` (with reason `stale_heartbeat` or cleanup‑pending) and then released by an operator.
- `claimed → running` is allowed only with valid `lease_token` and `claim_version`, and appends a `running` event.
- **Terminal state lease clearing**: When a task transitions to `failed`, `cancelled`, or `done`, the `lease_token` and `lease_expires_at` are set to `NULL`. This prevents a rogue worker from updating a completed task.

**Transition rules:**

- Every successful state change appends an `events` row in the same transaction.
- Illegal transitions (e.g., `done → queued`) must raise an error and log nothing.
- Failed conditional updates, double‑claim conflicts, and stale‑token mutations must **not** append any event. The event log must never record a state change that did not happen.
- Transitions can include optional `payload_json` (e.g., reason for block, acceptance verification).

### 4.4. Atomic Claim & Fencing Model

The queue supports two claim methods: **specific claim** (`claim_task(id, worker)`) and **priority claim** (`claim_next(worker)`). Both use the same transaction shape.

**Specific claim (claim by ID):**

```sql
-- Worker claims a specific task; ID supplied by operator or prior listing.
BEGIN IMMEDIATE;
SELECT id, claim_version FROM tasks
WHERE id = :task_id AND state = 'queued'
AND (lease_expires_at IS NULL OR lease_expires_at < datetime('now'));

UPDATE tasks SET
    state = 'claimed',
    lease_owner = :worker_id,
    lease_token = :new_token,
    claim_version = claim_version + 1,
    lease_expires_at = datetime('now', '+30 minutes'),  -- Phase 1A manual lease
    updated_at = CURRENT_TIMESTAMP
WHERE id = :task_id
  AND state = 'queued'
  AND (lease_expires_at IS NULL OR lease_expires_at < datetime('now'));

-- Check rowcount = 1; if 0 → conflict (already claimed or stale).

INSERT INTO events (task_id, type, payload_json)
VALUES (:task_id, 'claimed', json_object('worker', :worker_id, 'lease_token', :new_token, 'claim_version', :new_version));
COMMIT;
```

**Priority claim (claim next available):**

```sql
-- Select the highest‑priority, oldest queued task
SELECT id, claim_version FROM tasks
WHERE state = 'queued'
AND (lease_expires_at IS NULL OR lease_expires_at < datetime('now'))
ORDER BY priority DESC, id ASC
LIMIT 1;
-- Then proceed with the same atomic UPDATE as above.
```

**Lease duration note:**
Phase 1A uses a **30‑minute manual lease** because no automatic heartbeat exists. Phase 1C will introduce a shorter, heartbeat‑based lease (e.g., 30 seconds with 10‑second renewals). The lease duration is configurable; the claim function accepts a `lease_seconds` parameter.

**Owner‑scoped mutations** (all later state changes by the worker) must include a check for `lease_token` and `claim_version`:

```sql
UPDATE tasks SET
    state = :new_state,
    ...
WHERE id = :task_id
  AND lease_token = :token
  AND claim_version = :version;

-- If rowcount = 0, the worker is stale → reject with "stale lease or version".
```

**Lease expiry handling:**

- `claimed` state + expired lease → return to `queued` (recovery scan or explicit release).
- `running` state + expired lease → do **not** auto‑requeue. Mark as `blocked` with reason `stale_heartbeat` (or `failed` if unrecoverable). Operator must inspect and decide.

### 4.5. CLI Commands — Corrected

All new commands reside under `./kitty builder queue`. Commands returning data support a `--json` flag.

**Core commands:**

- `queue add "title" --description "..." --acceptance '["criterion"]'`
- `queue edit <id> [--priority <int>] [--description "..."]`
  *(Allowed only when state = `queued`; editable fields: title, description, priority, acceptance_criteria_json, allowed_paths_json. Bridge metadata is read‑only.)*
- `queue list [--state queued] [--json]`
- `queue show <id> [--json]`
- `queue claim <id> --worker <name> [--json]`
  (Returns `lease_token` and `claim_version`; claims a specific task.)
- `queue claim-next --worker <name> [--json]`
  (Claims the highest‑priority queued task.)
- `queue release <id> --worker <name> --lease-token <token> --claim-version <version>`
  (Worker‑initiated release; requires fencing.)
- `queue operator-release <id> --reason "..."`
  (Privileged, manual release; logs reason.)
- `queue transition <id> <state> --payload-json '{...}' --lease-token <token> --claim-version <version>`
  (For worker‑scoped mutations: `claimed → running`, `running → blocked`, etc. Automatically clears the lease on terminal states.)
- `queue events <id> [--json]`
- `queue status` (summary of queue length per state)
- `queue archive --state <done|cancelled|failed> --older-than <days>`
  *(Soft‑archive terminal tasks by setting `archived_at`; does **not** delete rows or events.)*

In Phase 1A, the CLI imports the queue store module directly — no HTTP daemon.

### 4.6. Required Tests

Phase 1A must include unit tests (using `pytest`) for:

- Task creation persists and returns expected fields.
- Listing tasks with state filter.
- Valid state transition updates state and appends an event.
- Illegal transition raises error and appends no event.
- Atomic claim: first claim succeeds; second claim on same task returns conflict.
- Both `claim <id>` and `claim-next` work correctly.
- Claim returns `lease_token` and `claim_version`.
- Worker‑scoped transition with valid token/version succeeds.
- Stale token/version transition is rejected (rowcount 0).
- Explicit worker release with valid token returns task to `queued`.
- Operator release without token returns task to `queued`.
- Lease expiry on `claimed` task returns to `queued` (via recovery function).
- `claimed → running` transition requires valid token/version.
- `running → queued` is **not** allowed — test confirms failure.
- Terminal states (`failed`, `cancelled`, `done`) clear the lease fields.
- `blocked` task can be resumed, failed, cancelled, or operator‑requeued via legal paths.
- Restart (re‑open DB) preserves tasks and events.
- Acceptance criteria are stored and retrievable.
- Double‑claim, illegal transitions, and stale mutations produce **no** events.
- **Concurrency:** spawn 10+ threads claiming the same task simultaneously — exactly one wins, others get conflict.
- Bridge idempotency: inserting the same `(bridge_source, bridge_external_id)` twice raises a unique constraint error; different tasks from the same issue but different comment IDs are allowed.
- `queue archive` sets `archived_at` without deleting rows or events.
- Event log triggers prevent UPDATE/DELETE on `events`.

---

## 5. Deferred Phases — Corrected

### Phase 1B — Manual Worker Handoff

- A `builder brief` generator that turns a local task into a worker prompt.
- Workers manually attach a final report and PR number.
- No automated worktree or PR creation.

### Phase 1C‑alpha — Runner Shadow Mode

- Git worktree creation under `.worktrees/kittybuilder/<task_id>`.
- Worker process runner with timeout, heartbeat, cleanup.
- **Records** planned commands and reports but does **not** push branches or open PRs.
- After validation, proceed to Phase 1C‑beta.

### Phase 1C‑beta — PR Adapter

- GitHub PR creation and report posting via `gh` or API **only after explicit operator command**.
- Still no auto‑merge.

### Phase 1D (or Phase 2‑prep) — Loopback `/builder/...` API

- Add a lightweight FastAPI loopback server exposing the same queue operations.
- This API will be used by the mission‑control UI in Phase 2.

### Phase 2 — Mission Control UI

- Kitty UI dashboard showing task board, worker status, PR lane, logs, approval buttons.
- No auto‑merge.

### Phase 3 — Safe Auto‑Merge & Advanced Verification

- Automatic merging of low‑risk changes (docs, styling) only after tests pass and policy gates are satisfied.
- Spec‑driven verification with structured acceptance criteria.
- GitHub merge queue integration.

### Phase 4 — Advanced Coordination

- Task DAG and dependency scheduling.
- Intelligent worker selection (model/provider based on task type).
- Full sandboxing (Docker).

---

## 6. Explicit Rejections

The following ideas have been considered and **rejected** for KittyBuilder’s current and near‑future scope:

| Rejected Idea | Reason |
| :--- | :--- |
| Multi‑agent delegation, hierarchical teams (CrewAI) | Requires agents and conversation state — Phase 3+ only. |
| Autonomous dispatch without human approval | Violates “operator‑fit” principle; Phase 1A is coordination‑first. |
| Cloud control plane or hosted auth | Local‑first design; cloud adds complexity and risk. |
| LangGraph or other heavy frameworks | Event log provides same durability with zero new dependencies. |
| Docker sandboxing in Phase 1A/1B/1C | Adds macOS permission issues; worktrees + process limits suffice initially. |
| Using `gateway/builder.py` or generic task runner | These are legacy/autonomous; Phase 1A must not tangle with them. |
| Storing artifacts as DB blobs | Blobs on filesystem with DB pointers is cleaner and more performant. |
| Auto‑merge in Phase 1 or 2 | Dangerous without human oversight and battle‑tested runner; deferred to Phase 3. |
| Treating GitHub issue #127 as authoritative queue | #127 is a bridge inbox only; local SQLite is the source of truth. |
| Separate `kitty-builder` binary | All commands live under the existing `./kitty builder` namespace. |
| Reusing `TASK_DB` (`data/task_queue.db`) | Separate DB path avoids collisions. |
| `running → queued` transition | Dangerous; must go through `blocked` with operator confirmation. |
| Worker release without token/version checking | Allows stale worker to release and cause race conditions. |
| Deleting tasks or events | Events are append‑only; tasks are soft‑archived. |

---

## 7. Phase 1A Implementation PR Breakdown

Phase 1A should **not** be implemented as one giant PR. Break it into these focused pull requests:

1. **PR 1 — Queue store and schema**
   - Add `BUILDER_QUEUE_DB` constant in `gateway/paths.py`.
   - Add `gateway/builder_queue.py` with DB init helpers (ULID‑style ID generation, claim performance index, bridge‑external idempotency index, append‑only event triggers).
   - Implement task creation, `get_task`, list tasks by state (with `--json` support in CLI later).
   - Implement event append helper.
   - Tests for persistence, exactly‑once bridge insert (idempotency index), and event log immutability (trigger enforcement).

2. **PR 2 — State machine and transitions**
   - Define legal transition map.
   - Implement `transition(task_id, new_state, ...)` with validation.
   - Ensure `lease_token` and `lease_expires_at` are `NULL`ed on terminal state transitions (`failed`, `cancelled`, `done`).
   - Raise clear errors for illegal transitions.
   - Ensure no event is appended on failure.
   - Tests for all valid transitions, terminal state lease dropping, illegal attempts, and no‑event guarantee.

3. **PR 3 — Claim, fencing, release, expiry**
   - Implement `claim_task(id, worker)` and `claim_next(worker)`, both using `BEGIN IMMEDIATE` with `lease_token` (UUID4) and `claim_version`.
   - Support configurable lease duration (default 30 minutes for Phase 1A).
   - Implement worker release (requires token/version).
   - Implement operator release (no token; logs reason).
   - Implement expiry recovery: `claimed` → `queued`, `running` → `blocked` (stale_heartbeat).
   - **Concurrency Testing:** Spawn 10+ concurrent threads claiming the same task via `claim_next` to prove exactly‑one ownership.
   - Tests for double‑claim, stale token, valid release, operator release, and no event on conflict.

4. **PR 4 — CLI integration**
   - Extend `gateway/builder_cli.py` with `queue` subcommand group.
   - Commands: `add`, `edit`, `list`, `show`, `claim`, `claim-next`, `release`, `operator-release`, `transition`, `events`, `status`, `archive`.
   - Implement `--json` flags on data‑returning commands.
   - Ensure existing `brief` and `contract validate` remain unchanged.
   - Tests for CLI argument parsing, JSON output format, and dispatch logic.

5. **PR 5 — Docs and handoff examples**
   - Add a quickstart guide (`docs/kittybuilder-quickstart.md`).
   - Document backup and recovery procedures.
   - Provide an example task lifecycle walkthrough using CLI commands and the `--json` flag to extract the lease token.

---

## 8. Rollout & Recovery Plan

### Rollout Strategy

1. **Current state**: #127 bridge mode; no local queue.
2. **Phase 1A**: Local queue available manually; CLI works; no automatic import.
3. **Phase 1A.5**: Optional dry‑run import from #127 comments (preview only, no mutation).
4. **Phase 1B**: Manual handoff/report attachment.
5. **Phase 1C‑alpha**: Runner shadow mode (records actions, no GitHub effect).
6. **Phase 1C‑beta**: PR adapter with explicit operator command to push/open PRs.
7. **Phase 1D/2‑prep**: Loopback API added.
8. **Phase 2**: Mission‑control UI.
9. **Phase 3**: Safe auto‑merge (after runner and policy gates are proven).
10. **Phase 4**: Advanced coordination.

### Backup & Recovery

- **Backup**: `sqlite3 builder_queue.db "VACUUM INTO 'backups/builder_queue_YYYYMMDD.db'"`
- **Integrity check**: `PRAGMA integrity_check;` (should return “ok”)
- **Crash simulation**: `kill -9` on any process using the DB, then reopen; verify WAL recovery and no lost data.
- **Stale task recovery**: Daemon startup (when added) will run a recovery scan as defined in Section 4.4.

### Daemon‑not‑Running UX (Future)

For Phase 1C+, if the daemon is unavailable, the CLI will display:

```
Error: Cannot connect to KittyBuilder daemon at localhost:9001.
Is the daemon running?

Try:
  ./kitty builder daemon start
  ./kitty builder daemon status
```

---

## 9. Open Questions (all resolved for Phase 1A)

| Question | Decision |
| :--- | :--- |
| CLI namespace | `./kitty builder queue ...` |
| Store location | `data/kittybuilder/builder_queue.db` |
| API hosting | None in Phase 1A (library‑mode); loopback API in Phase 1D/2‑prep |
| Lease duration (Phase 1A) | 30 minutes (manual coordination) |
| Lease duration (Phase 1C) | 30 seconds with 10‑second heartbeat |
| Stale `running` tasks | Mark `blocked` with reason `stale_heartbeat`, never auto‑requeue |
| Auto‑merge | None until Phase 3 |
| Task ID format | ULID‑style, no external dependency |
| Bridge idempotency key | `(bridge_source, bridge_external_id)` |
| Task archival | Soft‑archive via `archived_at`; no deletes |

---

## 10. Sources

- OpenAI Symphony — spec, workspaces, WORKFLOW.md
- Mission Control — local‑first JSON queue, concurrency
- Agent Orchestrator — durable facts, derived status
- Agent Kanban — atomic claim, FastAPI + SQLite
- CrewAI — task descriptions, expected output, guardrails
- AutoGen — human‑in‑the‑loop modes, tool registration
- LangGraph — checkpointing, interrupt/resume
- SWE‑agent — worktree isolation, trajectory logging
- Docker & sandboxing documentation
- GitHub API rate limits & merge queue docs
- SQLite best practices (WAL, busy timeout, fencing tokens)

---

**This document is the final architecture baseline. Phase 1A may proceed only after the implementation PR breakdown is approved.**

## 11. Implementation Notes From Final Review

These notes clarify implementation details without expanding Phase 1A scope.

### 11.1. Task ID Format

Task IDs should remain short enough to appear in future branch names, PR titles, and logs.

Preferred no-dependency format:

`kb_<base36_unix_ms>_<hex4>`

The ID must be locally unique, roughly time-sortable, and generated without adding a third-party ULID dependency.

### 11.2. Backup Discipline

The local SQLite queue is authoritative, so backup discipline matters.

Phase 1A does not need an automatic backup daemon, but docs should make backup/recovery visible. A later CLI/status PR should warn if no recent backup exists.

Future warning behavior:

`./kitty builder queue status`

should eventually warn if the newest `backups/builder_queue_*.db` file is older than 48 hours.

### 11.3. Kill Switch

A later CLI PR should support a simple local kill switch:

`KITTY_BUILDER_QUEUE_ENABLED=0`

When disabled, mutating queue commands should refuse to touch the DB and print a clear message. This is a safety valve if KittyBuilder becomes noisy or untrusted during rollout.

### 11.4. Bridge Divergence Rule

GitHub bridge metadata is advisory after Phase 1A.

The only bridge field that should affect idempotency is `bridge_external_id`. Re-adding the same `(bridge_source, bridge_external_id)` must fail or return the existing task, but GitHub comments must not mutate local task state.

Local SQLite remains authoritative.

### 11.5. Transition Event Names

PR 2 should define explicit event types for state changes.

Recommended event types:

- `created`
- `claimed`
- `running`
- `blocked`
- `released`
- `operator_released`
- `failed`
- `cancelled`
- `done`
- `archived`

Every successful state mutation appends one corresponding event. Failed mutations append no success event.

### 11.6. Concurrency Test Meaning

The PR 3 concurrency test proves the transaction and conditional-update model, not merely the claim index.

The critical safety properties are:

- `BEGIN IMMEDIATE`
- conditional update by current state
- rowcount check
- event appended only after successful mutation
- commit

Do not "optimize" the claim path in a way that bypasses these properties.

### 11.7. #127 Cutover Note

PR 5 should document when Jacob should stop using GitHub issue #127 as the primary task inbox.

Until then, #127 remains a bridge inbox. After local queue dogfooding succeeds, #127 should become bridge metadata/audit only, otherwise Jacob will double-track work in both places.
