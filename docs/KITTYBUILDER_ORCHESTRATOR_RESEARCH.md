# KittyBuilder Orchestrator Research

Status: research/design only. Do not treat this as approval to build Phase 1.
Date: 2026-07-09

## Scope Guard

This document surveys existing agent-orchestration systems before implementing
KittyBuilder's local queue. It intentionally does not implement a daemon,
worker, UI, or PR automation.

Important correction: GitHub issue
[#127 "KittyBuilder Queue"](https://github.com/jacob202/kitty/issues/127)
is only the temporary bridge inbox while KittyBuilder has no local
orchestrator. The long-term source of truth should be KittyBuilder's local
daemon/database. GitHub should remain the PR, review, audit, and optional sync
surface.

## Executive Recommendation

Build KittyBuilder as a local-first queue daemon with SQLite as the
authoritative task store, explicit state-machine transitions, worktree-aware
runs, and GitHub as an integration layer rather than the queue.

The best proven pattern is a hybrid of:

- OpenAI Symphony's `WORKFLOW.md` contract, bounded dispatch loop, per-task
  workspace model, and structured logs.
- Agent Orchestrator's local daemon, SQLite durable facts, observer loops,
  "durable facts -> derived status" read model, and local app-state directory.
- Agent Kanban's explicit task/session state machines, atomic dispatch claims,
  ordered daemon tick phases, and single-writer session manager.
- Claude Squad's simple tmux/worktree/session supervision model for the first
  usable worker surface.
- Workstream and nerkoman/agent-kanban's boring FastAPI + SQLite + localhost
  deployment shape.

Do not copy the high-autonomy parts first. No auto-merge, no autonomous worker
spawning, no multi-agent delegation, no cloud control plane, and no GitHub issue
as permanent source of truth in the first implementation branch.

## Systems Reviewed

### 1. OpenAI Symphony

- Repo URL: <https://github.com/openai/symphony>
- Key docs: [SPEC.md](https://github.com/openai/symphony/blob/main/SPEC.md),
  [Elixir README](https://github.com/openai/symphony/blob/main/elixir/README.md)
- Language/framework: Elixir/OTP reference implementation; language-agnostic
  spec.
- Local-first: Mostly local runtime, but tracker-first. The spec targets Linear
  as the tracker reader.
- Queue/source of truth: Symphony polls an issue tracker for candidate work and
  owns a single in-memory orchestrator state for dispatch, claims, retries, and
  reconciliation. The spec explicitly says restart recovery can be driven by
  tracker/filesystem state without a persistent DB.
- Worker execution model: Creates a workspace per issue and runs Codex app
  server turns inside that workspace.
- Workspace isolation model: Per-issue workspace directories, sanitized issue
  identifiers, hooks for create/run/remove, optional SSH workers.
- GitHub/PR integration: Not built in as core business logic. Ticket writes and
  PR/comment behavior usually live in the workflow prompt and agent tools.
- Lifecycle model: Active/terminal issue states, claimed/running/retry/blocked
  in-memory state, continuation turns, and exponential-ish retry scheduling.
- Concurrency/locking: Global max concurrent agents, optional per-state limits,
  claimed set in orchestrator state.
- Dashboard/UI approach: Optional Phoenix LiveView dashboard and JSON state API
  in the reference implementation.
- Logs/observability: Structured lifecycle logs with stable fields such as
  `issue_id`, `issue_identifier`, and `session_id`.
- Safety/approval model: The spec deliberately does not mandate one posture.
  The reference README warns it is prototype software for trusted environments,
  but uses safer Codex defaults when omitted.
- What KittyBuilder should copy: `WORKFLOW.md` front matter plus prompt body,
  explicit active/terminal states, workspace hooks, bounded concurrency,
  structured logs, and "scheduler/runner, not business-logic god object."
- What KittyBuilder should avoid: Tracker-first authority, in-memory-only
  blocked state, and high-trust approval assumptions. KittyBuilder should make
  SQLite the durable queue and keep #127 as bridge/audit only.

### 2. Mission Control

- Repo URL: <https://github.com/MeisnerDan/mission-control>
- Language/framework: TypeScript, Next.js, local JSON data files, Vitest.
- Local-first: Yes. The README says all data is stored in local JSON files with
  no cloud dependency.
- Queue/source of truth: Local JSON files under `mission-control/data/` for
  tasks, agents, inbox, decisions, missions, and daemon config.
- Worker execution model: Can spawn Claude Code sessions from task cards or a
  daemon. The product is broader than coding: ideas, research, MVP build,
  launch, approvals, and "field ops."
- Workspace isolation model: More task/project-management oriented than
  git-worktree oriented in the README. It is not primarily a PR/worktree
  supervisor.
- GitHub/PR integration: Present indirectly through developer dashboard and AI
  review features, but not the core queue model.
- Lifecycle model: Task states, inbox reports, decisions queue, continuous
  missions, loop detection after repeated failures, and daemon runs.
- Concurrency/locking: Uses local JSON with `async-mutex` guarding file writes.
- Dashboard/UI approach: Rich local Next.js dashboard with kanban, priority
  matrix, inbox, agent crew, decisions, and safety panels.
- Logs/observability: Activity log, failure reports to inbox, cost/token
  tracking, active run endpoints.
- Safety/approval model: Approval workflows, spend limits, encrypted vault,
  autonomy levels, circuit breaker, emergency stop.
- What KittyBuilder should copy: Human decision queue, emergency stop, process
  tree kill, credential scrubbing, explicit spend/risk gates, and "reports land
  in an inbox."
- What KittyBuilder should avoid: JSON as authoritative queue storage for
  concurrent worker claims, catch-and-default read paths, and broad external
  action scope. Kitty's prime directive is fail loud, so queue reads must not
  silently become empty state.

### 3. Agent Orchestrator / AO

- Repo URL: <https://github.com/AgentWrapper/agent-orchestrator>
- Related trail: older Composio/AO references and the mirror
  <https://github.com/mnemom/composio-ao> point toward this current repo.
- Key docs:
  [architecture.md](https://github.com/AgentWrapper/agent-orchestrator/blob/main/docs/architecture.md),
  [stack.md](https://github.com/AgentWrapper/agent-orchestrator/blob/main/docs/stack.md),
  [daemon-environment.md](https://github.com/AgentWrapper/agent-orchestrator/blob/main/docs/daemon-environment.md)
- Language/framework: Go daemon, Electron + React frontend, SQLite, chi,
  WebSocket/SSE, tmux/conpty, git CLI.
- Local-first: Yes. Current docs say app state, daemon data, running state,
  worktrees, and Electron data live under `~/.ao`.
- Queue/source of truth: Local SQLite store with durable session, project, PR,
  and review facts. Display status is derived at read time rather than stored.
- Worker execution model: Local daemon creates sessions, worktrees, runtime
  handles, and agent launches; supports many agent adapters.
- Workspace isolation model: Git worktree adapter; each session has its own
  workspace, branch, terminal/runtime, and PR state.
- GitHub/PR integration: GitHub SCM observer, PR/check/comment facts, merge and
  review actions, nudges for CI failures, review feedback, and merge conflicts.
- Lifecycle model: Observe external facts, update durable facts, derive display
  status or act. Lifecycle reducer plus runtime reaper.
- Concurrency/locking: SQLite with WAL, explicit process/runtime management,
  observer loops, and local daemon ownership. It avoids distributed systems for
  v1.
- Dashboard/UI approach: Electron control panel with projects, sessions,
  terminal, PR state, reviews, and browser preview.
- Logs/observability: Structured Go logging, SQLite change-log CDC, SSE event
  stream, terminal WebSocket.
- Safety/approval model: Local-only daemon. Docs emphasize environment
  correctness, path/data-dir boundaries, and not storing high-volume terminal
  output in SQLite.
- What KittyBuilder should copy: Durable facts + derived status, SQLite WAL,
  CDC/event stream, loopback HTTP daemon, observer/action separation, app-state
  directory, and real git CLI rather than reimplementing Git.
- What KittyBuilder should avoid: Full desktop app, 20+ agent adapters, plugin
  framework, and PR action engine in Phase 1.

### 4. Claude Squad

- Repo URL: <https://github.com/smtg-ai/claude-squad>
- Language/framework: Go, Bubble Tea TUI, tmux, git worktrees.
- Local-first: Yes.
- Queue/source of truth: Local TUI/session state rather than a durable task
  queue. The user creates and manages sessions.
- Worker execution model: Starts multiple local terminal agents such as Claude
  Code, Codex, Gemini, Aider, OpenCode, or Amp.
- Workspace isolation model: Each task/session gets its own git worktree and
  branch; tmux manages terminals.
- GitHub/PR integration: `gh` is a prerequisite; UI can commit and push a
  branch, but the repo is not a full PR lifecycle daemon.
- Lifecycle model: Instances/sessions persisted in local state JSON with title,
  path, branch, status, dimensions, program, worktree, and diff stats.
- Concurrency/locking: Human-supervised TUI, tmux sessions, and worktree
  isolation. It does not solve durable task claiming.
- Dashboard/UI approach: Terminal UI with session list, diff/preview tabs, and
  attach/resume controls.
- Logs/observability: Live tmux attach plus diffs; simple local state.
- Safety/approval model: Human review before applying/pushing; optional
  `--autoyes` mode exists but should not be a KittyBuilder default.
- What KittyBuilder should copy: tmux/worktree minimalism, branch-name
  sanitization, base commit capture, "review changes before push," and keeping
  early UX terminal-native.
- What KittyBuilder should avoid: JSON state as the authoritative queue,
  aggressive cleanup patterns, and auto-accept as a default.

### 5. Vibe Kanban

- Repo URL: <https://github.com/BloopAI/vibe-kanban>
- Docs/site: <https://www.vibekanban.com/>
- Language/framework: Rust workspace with TypeScript/React web packages,
  SQLite via sqlx, local server, npm launcher.
- Local-first: Mostly local/self-hostable, with cloud/self-host surfaces. The
  README currently says Vibe Kanban is sunsetting.
- Queue/source of truth: Kanban issues/tasks, workspaces, sessions, execution
  processes, execution logs, PR tracking, and migrations in SQLite.
- Worker execution model: Creates workspaces where coding agents run with a
  branch, terminal, and dev server.
- Workspace isolation model: Git worktree/workspace manager; later schema
  separates workspaces from sessions.
- GitHub/PR integration: Create PRs, review diffs/comments in UI, track PRs and
  merges.
- Lifecycle model: Board issues -> workspaces -> sessions -> execution
  processes/logs -> review/PR/merge.
- Concurrency/locking: Rust async services and SQLite-backed state. It is more
  mature than Phase 1 needs.
- Dashboard/UI approach: Rich kanban/workspace web UI with diff review,
  comments, built-in browser/devtools, device emulation, and supported agent
  switching.
- Logs/observability: Execution process logs, activity, sessions, browser
  preview, status UI.
- Safety/approval model: Strong human review UX; PR creation/merge controls
  exist. README says "review on GitHub, and merge."
- What KittyBuilder should copy: Separation of task/workspace/session/process,
  storing logs separately from structured state, PR lane UX, and browser
  preview as a later feature.
- What KittyBuilder should avoid: Building a rich UI first, depending on a
  sunsetting project, and adopting its whole Rust workspace complexity.

### 6. Agent Kanban

- Repo URL: <https://github.com/saltbo/agent-kanban>
- Language/framework: TypeScript monorepo, React UI, Hono/Cloudflare style web
  app, CLI daemon, D1/SQLite-like migrations.
- Local-first: Not purely local-first. The README starts with hosted signup at
  `agent-kanban.dev`, but it has self-hosting/source availability.
- Queue/source of truth: Board tasks in DB with statuses `todo`,
  `in_progress`, `in_review`, `done`, `cancelled`; agents, sessions, machines,
  task actions, identities.
- Worker execution model: Leader agents create/assign tasks; daemon polls
  assigned tasks, prepares repo/workspaces/skills, and spawns workers.
- Workspace isolation model: Repo workspaces for worker sessions, skills and
  subagents installed per workspace.
- GitHub/PR integration: Workers open PRs; daemon detects merge and completes
  tasks; GitHub App/installations are modeled.
- Lifecycle model: Explicit task transition map and session state machine.
  Session states include active, rate_limited, in_review, completing, closed,
  terminal.
- Concurrency/locking: Atomic dispatch claim, runtime pool, per-runtime
  capacity checks, rate-limit pause/resume, circuit breaker, single-writer
  session manager with per-session async mutexes.
- Dashboard/UI approach: Live agent-first kanban board, agent identities,
  chat, roles, skills, and SSE updates.
- Logs/observability: Task actions, session state files, usage/cost tracking,
  daemon logs.
- Safety/approval model: Role-based identities (user, machine, worker, leader,
  maintainer), Ed25519/JWT identity, GPG signing support, explicit allowed
  transitions.
- What KittyBuilder should copy: Transition maps that throw on illegal moves,
  atomic claim semantics, ordered daemon phases (`cancel/reap/review/resume`
  before dispatch), session single-writer pattern, and rate-limit persistence.
- What KittyBuilder should avoid: Agent self-organization, hosted/cloud
  requirement, cryptographic identity in Phase 1, and leader-agent auto-merge.

### 7. Workstream

- Repo URL: <https://github.com/happybhati/workstream>
- Language/framework: Python FastAPI, SQLite via aiosqlite/sqlite3, single-page
  static frontend, local CLI/LaunchAgent.
- Local-first: Yes. Runs locally at localhost and stores data in SQLite.
- Queue/source of truth: Not an agent task queue. Stores PRs, Jira issues,
  calendar data, review intelligence, readiness scans, telemetry, registered
  agents, and status history.
- Worker execution model: Observability and review/scanning dashboard, not a
  coding worker runner.
- Workspace isolation model: None for code execution.
- GitHub/PR integration: PR dashboard, CI/review state, AI code review, review
  intelligence, readiness scanner that can create draft PRs.
- Lifecycle model: Pollers update external data into SQLite; agents dashboard
  tracks health/status over time.
- Concurrency/locking: Local single-user SQLite; ADR notes SQLite is not meant
  for multi-user concurrent writes.
- Dashboard/UI approach: FastAPI + static single-page dashboard; agents tab,
  telemetry, health checks, live activity stream.
- Logs/observability: SSE-style in-memory activity stream plus SQLite status
  history/telemetry.
- Safety/approval model: AI code review requires human approval before posting.
  Registry scrubs secret-looking env values before display.
- What KittyBuilder should copy: Python/FastAPI/SQLite stack simplicity,
  localhost CLI/service shape, SSE for visible activity, telemetry tables, and
  secret scrubbing in observability.
- What KittyBuilder should avoid: In-memory-only event history as authoritative
  log, health-probe error swallowing for queue writes, and broad dashboard scope
  before the queue is real.

### 8. nerkoman/agent-kanban

- Repo URL: <https://github.com/nerkoman/agent-kanban>
- Language/framework: Python 3.12, FastAPI, SQLite, MCP, OpenAPI, uvicorn.
- Local-first: Yes. README describes "SQLite, FastAPI, no auth, no cloud."
- Queue/source of truth: Local SQLite `tasks.db` with projects, tasks,
  task_links, task_history, task_blockers, project_sources, and meta.
- Worker execution model: Agents interact through MCP tools or REST/OpenAPI.
  It does not spawn coding workers itself.
- Workspace isolation model: Project path binding exists, but no git worktree
  runner/PR automation.
- GitHub/PR integration: Links can be stored; GitHub importer is roadmap.
- Lifecycle model: Nine columns from backlog through approved, analyst,
  in_progress, testing, UAT, done, blocked, cancelled.
- Concurrency/locking: Thread-safe store with `RLock`, SQLite WAL, explicit
  transactions. `pull_task` atomically claims an approved task and moves it to
  analyst.
- Dashboard/UI approach: Local FastAPI board with drag/drop, themes, inbox
  watcher, automation rules, webhooks, MCP tools.
- Logs/observability: Task history table and webhooks; not a run log system.
- Safety/approval model: Local/no-auth by default, agent-facing MCP returns
  structured ok/error payloads.
- What KittyBuilder should copy: Minimal local FastAPI + SQLite store, task
  history table, WAL, atomic claim transaction, MCP/OpenAPI-friendly API, and
  inbox watcher as a later bridge.
- What KittyBuilder should avoid: No-auth beyond loopback, generic kanban
  statuses that do not model PR/run/session facts, and MCP error wrapping as the
  only failure surface.

### 9. Automagik Forge

- Repo URL: <https://github.com/automagik-dev/forge>
- Language/framework: TypeScript primary with some Rust, Shell, JavaScript, and
  MCP integration.
- Local-first: Self-hostable/local developer-tool posture; exact queue storage
  was not deeply audited in this pass.
- Queue/source of truth: Persistent kanban with tasks and multiple attempts.
- Worker execution model: Human chooses provider and agent; attempts execute in
  isolated environments.
- Workspace isolation model: Git worktree isolation per attempt.
- GitHub/PR integration: README advertises GitHub OAuth and repository
  management.
- Lifecycle model: Wish -> Forge -> Review with multiple attempts per task.
- Concurrency/locking: Parallel attempts/tasks; implementation details not
  deeply reviewed.
- Dashboard/UI approach: Browser dashboard, MCP control, visual context,
  progress, diffs.
- Logs/observability: Real-time progress and diffs per attempt.
- Safety/approval model: Strong human-in-control framing: choose provider,
  review, understand, then ship.
- What KittyBuilder should copy: Attempt model later, provider/agent selection
  as an operator decision, and "review before merge" UX.
- What KittyBuilder should avoid: Multiple attempts and provider matrix in
  Phase 1.

### 10. AgentsKanban

- Repo URL: <https://github.com/abuiles/agents-kanban>
- Language/framework: TypeScript, React/Vite, Cloudflare Workers, Durable
  Objects, D1, R2, KV, Workflows, Cloudflare Containers.
- Local-first: No. It is self-hostable on Cloudflare, but the architecture is a
  cloud control plane.
- Queue/source of truth: Durable Objects and D1 for board/repo/task/run state,
  R2 for artifacts, KV for secret metadata.
- Worker execution model: Background Workflows launch sandboxed run phases and
  retries.
- Workspace isolation model: Cloudflare Containers-backed sandbox.
- GitHub/PR integration: GitHub and GitLab repositories, review posting,
  review findings, reruns, Slack/Jira/GitLab loop.
- Lifecycle model: INBOX, READY, ACTIVE, REVIEW, DONE, FAILED plus run
  timeline/checkpoints.
- Concurrency/locking: Durable Object leases and workflow/idempotency patterns.
- Dashboard/UI approach: Kanban UI with logs, artifacts, previews, retry and
  operator controls.
- Logs/observability: Run events, command history, artifacts, evidence capture,
  live terminal.
- Safety/approval model: Operator can step in; Slack reruns can require
  explicit approval.
- What KittyBuilder should copy: Artifact/evidence model, deterministic phase
  checkpoints, dependency-aware scheduling, and explicit FAILED lane.
- What KittyBuilder should avoid: Cloudflare-specific infrastructure,
  multi-tenant/auth complexity, and containers in Phase 1.

### 11. Flightdeck

- Repo URL: <https://github.com/jcashell1989/flightdeck>
- Language/framework: Electron 41, React 19, TypeScript, electron-vite,
  Vitest, Playwright.
- Local-first: Yes, desktop-oriented.
- Queue/source of truth: Session dashboard rather than task queue.
- Worker execution model: Full control for opencode via HTTP/SSE; monitor-only
  for Claude Code via file watching.
- Workspace isolation model: Projects view can initialize/manage project dirs;
  no documented worktree-per-task queue.
- GitHub/PR integration: Not primary in README.
- Lifecycle model: Session states and attention tracking.
- Concurrency/locking: Adapter-specific; not a durable claim queue.
- Dashboard/UI approach: Desktop dashboard grouped by project, attention badge,
  command palette dispatch, analytics.
- Logs/observability: Live session state via SDK/file watching.
- Safety/approval model: Surfaces sessions that need approval or answers.
- What KittyBuilder should copy: Attention-state dashboard and adapter split:
  full control where APIs exist, monitor-only where they do not.
- What KittyBuilder should avoid: UI-first implementation before durable queue
  semantics.

## Architecture For KittyBuilder

### Authority Model

KittyBuilder's authoritative queue should be a local SQLite database. GitHub
issue #127 remains a bridge inbox until Phase 1 exists. After Phase 1, GitHub
issues/comments may sync into the local queue, but local task rows and event rows
decide claim, state, retry, and stop behavior.

### Components

1. Queue daemon: loopback-only HTTP API over a SQLite store. It owns every state
   mutation. Workers and CLI never write the DB directly.
2. CLI: thin `./kitty builder queue ...` commands over the daemon API, plus
   existing `brief` and `contract validate`.
3. Store/state machine: tasks, runs, leases, PR links, events. All task
   transitions go through one function that rejects illegal transitions.
4. Worker runner: later phase. Creates git worktrees, runs a selected agent,
   sends heartbeats, records logs, opens PRs. Not required in the first
   implementation branch.
5. GitHub adapter: later phase. Writes PR comments/reports and optionally syncs
   bridge inbox tasks. It is not the source of truth.
6. Dashboard: later phase. Reads derived status and events. It should not drive
   hidden queue writes outside the daemon API.

### State Model

Recommended initial task states:

- `queued`: local task is ready to claim.
- `claimed`: a worker/runner has a lease but has not started execution.
- `running`: a run is active and heartbeating.
- `pr_opened`: a branch/PR exists.
- `awaiting_review`: final report posted; waiting for checks or human review.
- `blocked`: cannot continue without input, credits, auth, or policy approval.
- `done`: task completed and archived.
- `failed`: unrecoverable or retry budget exhausted.
- `cancelled`: intentionally stopped.

Recommended run states:

- `starting`
- `running`
- `rate_limited`
- `needs_input`
- `completed`
- `failed`
- `cancelled`
- `cleanup_pending`

The display status should be derived from durable facts, not written as a
separate truth. For example, "needs attention" can be computed from
`blocked`, missing heartbeat, failed checks, or `awaiting_review`.

### SQLite Patterns

Use SQLite because this is a local single-user daemon. Use:

- `PRAGMA journal_mode = WAL`
- `PRAGMA busy_timeout = 5000`
- `PRAGMA foreign_keys = ON`
- `BEGIN IMMEDIATE` for atomic claims
- An append-only `events` table for every state mutation

Do not use `SELECT ... FOR UPDATE`; SQLite does not support it the way Postgres
does. The claim operation should be a conditional update inside a write
transaction:

```sql
BEGIN IMMEDIATE;
UPDATE tasks
SET state = 'claimed',
    lease_owner = :worker_id,
    lease_expires_at = :expires_at,
    updated_at = :now
WHERE id = :task_id
  AND state = 'queued';
-- success only if rowcount == 1
INSERT INTO events (...);
COMMIT;
```

### Observability

Store durable structured events in SQLite. Store large logs as files under a
known local data directory and record pointers/checksums in the DB. Expose:

- `GET /status`: queue counts, daemon health, current leases.
- `GET /tasks`: filtered task list.
- `GET /tasks/{id}/events`: audit trail.
- `GET /events`: recent event stream cursor.
- Later: SSE for dashboard invalidation.

### Safety Defaults

- Phase 1 never auto-merges.
- Phase 1 never self-selects from #127 without an explicit import/approval
  command.
- Phase 1 never touches secrets or writes tokens to logs.
- Workers cannot mark tasks `done` unless the state machine allows it.
- Failed cleanup becomes `cleanup_pending`, not silent deletion.
- Queue errors should fail loudly. Health probes may degrade to `unknown`; task
  writes may not.

## Patterns To Borrow Or Adapt

- Symphony: workflow file front matter plus Markdown prompt body. Use this for
  concurrency, test commands, blocked paths, and final report shape.
- Symphony: log context must include local `task_id`, bridge issue/comment id if
  present, PR number if present, and run/session id.
- Agent Orchestrator: "observe -> update durable facts -> derive status/act."
  This prevents dashboards from storing misleading secondary status fields.
- Agent Orchestrator: local daemon app-state directory and SQLite WAL. Keep
  terminal/log bulk out of SQLite.
- Agent Kanban: transition maps and state-machine helpers that throw/reject on
  illegal transitions.
- Agent Kanban: daemon tick order should clean/reconcile before dispatching new
  work.
- Agent Kanban: persist rate-limit/resume-after data before notifying in-memory
  schedulers.
- Claude Squad: use real `git` CLI and git worktrees. Preserve base commit and
  existing-branch flags.
- Mission Control: process-tree kill, credential scrubbing, decision queue,
  emergency stop.
- Workstream: FastAPI + SQLite + local LaunchAgent style is enough for a local
  dashboard/service.
- nerkoman/agent-kanban: minimal SQLite schema with task history, MCP/OpenAPI
  friendliness, and atomic claim transaction.
- Vibe Kanban/Forge: later UX ideas: workspaces, sessions, attempts, diff
  review, browser preview.

License caution: do not copy code from AGPL/FSL projects into Kitty without a
license review. Borrow architecture and tests as inspiration; prefer Apache/MIT
or original implementation.

## Revised Phase 1 Plan

The earlier Phase 1 plan tried to build daemon, CLI, worker script, worktree,
GitHub PR creation, and final report posting at once. After surveying existing
systems, that is too large for the first branch. The safer first branch should
make the local queue trustworthy before it tries to run workers.

### Phase 1A: Local Queue Authority

Goal: create the durable local queue and explicit state machine. No agent
spawning. No PR creation. No auto-merge.

Deliver:

- Local SQLite store for tasks, runs, leases, PR links, and events.
- Atomic task claim/release/complete/fail/cancel transitions.
- Loopback-only daemon API or route module with a documented contract.
- `./kitty builder queue add/list/show/claim/complete/fail/events` as thin CLI
  commands.
- Tests for create, list, invalid transition, double claim, lease expiry,
  event append, and restart persistence.
- Bridge metadata fields (`bridge_source`, `bridge_issue`, `bridge_comment_url`)
  but no automatic #127 ingestion yet.

Exit criteria:

- Two concurrent claim attempts cannot both win.
- Restarting the process does not lose queued/claimed/running task facts.
- Every mutation appends an event.
- `docs/WORKFLOW.md` still says #127 is the bridge inbox, not final source of
  truth.

### Phase 1B: Manual Worker Handoff

Goal: prove a worker can take a local task without the daemon spawning agents.

Deliver:

- A `builder brief`/handoff generator that renders a worker prompt from the
  local task plus `WORKFLOW.md`.
- Worker can post progress/final report back through API/CLI.
- Manual PR number/head SHA can be attached to the task.
- No autonomous worktree creation yet unless Phase 1A is already stable.

### Phase 1C: Worktree Runner And PR Adapter

Goal: add controlled execution after the queue is stable.

Deliver:

- Worktree creation under `.worktrees/kittybuilder/<task_id>`.
- Worker process runner with timeout, heartbeat, cleanup-pending state.
- GitHub PR creation/report posting through `gh` or API.
- Still no auto-merge.

## Implementation Prompt For Next Worker Branch

Use this only after the research PR is reviewed.

```text
Branch: feat/kittybuilder-local-queue-phase1a

Goal:
Implement KittyBuilder Phase 1A: a local SQLite-backed queue that becomes the
authoritative source of truth for KittyBuilder tasks. Do not implement agent
spawning, worktree execution, GitHub PR creation, #127 auto-sync, UI, or
auto-merge.

Context:
- GitHub issue #127 is only the temporary bridge inbox.
- Local KittyBuilder daemon/database is the final source of truth.
- Existing `./kitty builder` Layer 1A already supports `brief` and
  `contract validate`; run/loop/repl/delegate are intentionally disabled.
- Keep existing behavior intact.

Recommended stack:
- Python 3.12
- SQLite through the standard library or SQLAlchemy only if it clearly reduces
  boilerplate
- FastAPI only for the loopback daemon/API layer
- pytest for tests
- No new heavy dependencies without explicit explanation

Scope:
1. Add a queue store and state-machine layer. Prefer a small new
   `gateway/builder_queue.py` module unless the file becomes too large; do not
   mutate legacy autonomous `gateway/builder.py` except for safe reuse if
   necessary.
2. Schema:
   - tasks: id, title, description, state, priority, lease_owner,
     lease_expires_at, bridge_source, bridge_issue, bridge_comment_url,
     created_at, updated_at
   - runs: id, task_id, state, worker_id, started_at, heartbeat_at,
     finished_at, error
   - pr_links: task_id, pr_number, pr_url, head_sha, state
   - events: id, task_id, run_id, type, payload_json, created_at
3. Implement explicit transitions:
   queued -> claimed -> running -> pr_opened -> awaiting_review -> done
   queued/claimed/running/awaiting_review -> failed
   queued/claimed/running/awaiting_review/blocked -> cancelled
   running -> blocked
   claimed/running -> queued only through explicit release/lease-expiry logic
   Illegal transitions must return a clear error and must not mutate state.
4. Atomic claim:
   - Use SQLite WAL, busy_timeout, foreign_keys.
   - Use `BEGIN IMMEDIATE` plus conditional update so double-claim returns
     conflict.
   - Append an event in the same transaction.
5. Expose a loopback API contract:
   - POST /builder/tasks
   - GET /builder/tasks
   - GET /builder/tasks/{id}
   - POST /builder/tasks/{id}/claim
   - POST /builder/tasks/{id}/release
   - POST /builder/tasks/{id}/transition
   - GET /builder/tasks/{id}/events
   - GET /builder/status
   If adding FastAPI routes is too much for the first commit, implement the
   store and CLI first, then open a follow-up issue for routes.
6. Extend `gateway/builder_cli.py` under `./kitty builder queue ...`:
   - queue add "title" --description "..."
   - queue list [--state queued]
   - queue show <id>
   - queue claim <id> --worker <name>
   - queue release <id> --worker <name>
   - queue transition <id> <state> --payload-json '{...}'
   - queue events <id>
7. Tests:
   - task creation persists
   - list filters by state
   - valid claim changes state and appends event
   - second claim returns conflict/error
   - illegal transition fails loudly and appends no event
   - release/lease-expiry returns task to queued through explicit path
   - restart/reopen DB preserves tasks/events
8. Documentation:
   - Add a short section to the new module docstring or a small docs note
     explaining that #127 is bridge metadata only.
   - Do not change `docs/WORKFLOW.md` unless the current wording is wrong.

Validation:
- `python3.12 -m pytest tests/test_builder_cli.py tests/test_builder_contract.py -q --tb=short`
- New queue tests with pytest.
- `git diff --check`

Stop:
Open a PR and post a final report with head SHA, changed files, tests, and
"Stopping here, not merging. Awaiting approval."
```

## Open Design Decisions

- Store location: recommended `data/kittybuilder/builder.db` or a path constant
  under `gateway/paths.py`, but the implementation branch should inspect
  existing path conventions first.
- API hosting: start loopback-only. It can be mounted in the existing Gateway or
  run as a separate daemon; choose the smaller implementation that preserves
  queue ownership.
- Dependency choice: standard-library sqlite is enough for Phase 1A. SQLAlchemy
  is acceptable if migrations/typing make it materially clearer.
- Worker command: keep disabled until Phase 1A passes. Add manual `queue`
  operations first.
- GitHub sync: record bridge metadata now, import/sync later. Never make #127
  final authority.

## Research Limits

This was a source survey, not a security or performance audit. Some repos are
moving quickly; details reflect the public repositories as checked on
2026-07-09. No code was copied into Kitty in this PR.
