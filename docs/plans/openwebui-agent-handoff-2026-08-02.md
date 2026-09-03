# Open WebUI onboarding handoff — 2026-08-02

> **Status: historical handoff, not current operating guidance.** All “current” and “verified” claims below are scoped to the 2026-08-02 session. For present authority and startup use `START_HERE.md`, `docs/AUTHORITY_MAP.md`, the root `README.md`, and live Git/Builder/GAR/runtime evidence. Native Kitty is now canonical; Open WebUI is optional compatibility, and legacy `.claude` checkpoints are fallback continuity rather than primary authority.

**Purpose:** verified starting context for the next Claude Code or OpenCode session. This document is a handoff input, not a replacement for live inspection.

## Read first

Follow `START_HERE.md` exactly. Before mutation, verify the checkout, branch, worktrees, dirty state, `origin/main`, open PRs, active mission, and local Builder state. Run:

```bash
pwd -P
git status --short --branch
git worktree list --porcelain
./kitty context --agent
./kitty doctor --json
./kitty builder initiative doctor --json
```

Do not fetch, switch, stash, clean, merge, or rewrite history merely to simplify the state.

## Product and architecture authority

### VERIFIED from the repository

- Kitty runs locally on Jacob's Mac.
- Canonical runtime: FastAPI Gateway on port 8000, LiteLLM on port 8001, and the existing Next.js client normally on port 4000.
- The Gateway is the product; clients should remain thin views over Gateway APIs.
- Kitty owns user intent, selective context, personal memory, life-first behavior, projects, tools, authorization, provider attribution, and the relationship with Jacob.
- KittyBuilder owns engineering execution truth: Missions, initiatives, packets, tasks, attempts, leases, recovery, budgets, review, evidence, and publication.
- Do not build a second Builder state machine or move Kitty/Builder business logic into Open WebUI.
- Current storage is mixed: Kitty SQLite, subsystem SQLite databases, JSON/JSONL, ChromaDB, and mem0. Do not add or migrate storage casually.
- Daily-use reliability and product coherence are acknowledged repository limitations despite broad backend capability.

Primary authorities:

- `START_HERE.md`
- `docs/AUTHORITY_MAP.md`
- `docs/NORTH_STAR.md`
- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/ROADMAP.md`
- `docs/PROJECT_STATUS.md`
- `docs/ACTIVE_MISSION.md`
- `.claude/STATE.md`
- `.claude/HANDOFF.md` only if its identity metadata is still valid

## Current Open WebUI implementation

### VERIFIED from GitHub

Open PR: **#384 — `feat: add tomorrow-ready Open WebUI bootstrap`**

- Branch: `feat/openwebui-tomorrow-ready`
- PR was open and mergeable when last checked.
- The implementation is additive; it does not delete or replace the existing Next.js UI.
- Open WebUI is pinned to `0.10.2` in an isolated Python 3.11 environment.
- Service root: `~/kitty-services/openwebui`
- Data directory: `~/kitty-services/openwebui/data-fresh`
- Log: `~/kitty-services/openwebui/logs/openwebui.log`
- Persistent secret: `~/kitty-services/openwebui/webui-secret`, intended mode `0600`
- Open WebUI URL: `http://127.0.0.1:3000`
- Gateway URL: `http://127.0.0.1:8000`
- OpenAI-compatible base: Gateway `/v1`
- Default model alias: `kitty-default`
- Ollama discovery is disabled.
- Open WebUI persistent configuration overrides are intended to be disabled so checked runtime environment remains authoritative.
- A macOS LaunchAgent is installed at `~/Library/LaunchAgents/com.kitty.openwebui.plist`.
- Desktop shortcut: `~/Desktop/Kitty Chat.webloc`.
- Existing rollback UI remains available.

Relevant files:

- `docs/runbooks/openwebui-tomorrow-ready.md`
- `scripts/openwebui_local.py`
- `scripts/openwebui_tool/common.py`
- `scripts/openwebui_tool/service.py`
- `scripts/openwebui_tool/system.py`
- `scripts/openwebui_tool/cli.py`
- `tests/test_openwebui_local.py`

## Host facts established during the 2026-08-02 setup session

These are **OBSERVED on Jacob's Mac through terminal output supplied in chat**. Re-verify locally before relying on them.

1. Open WebUI `0.10.2` installed successfully.
2. Gateway and LiteLLM eventually started successfully after a clean restart.
3. Gateway `/health` responded and `/v1/models` exposed `kitty-default`.
4. Open WebUI reached healthy state on `127.0.0.1:3000`.
5. The Open WebUI database migrations completed against the fresh data directory.
6. Open WebUI was reachable in the browser and Jacob entered the interface.
7. The LaunchAgent installation reported success.
8. The Desktop shortcut installation reported success.
9. Jacob's account was initially blocked on “Account Activation Pending.”
10. The active database was confirmed at:

   `~/kitty-services/openwebui/data-fresh/webui.db`

11. The `user` table uses `role` as the relevant account state. Six duplicate rows existed with:

   - email: `admin@localhost`
   - initial role: `pending`

12. A timestamped database backup was created, all six matching rows were changed to `role='admin'`, and Jacob subsequently confirmed he was inside Open WebUI.

Do not delete duplicate user rows blindly. First identify which user ID is referenced by the active auth/session records and related foreign keys, then back up and clean safely if cleanup is worthwhile.

## Defects discovered during real host execution

### 1. Stale/unhealthy service handling

**OBSERVED:** the first bootstrap trusted existing LiteLLM/Gateway PIDs even though Gateway health was failing with connection resets.

**Repository response:** commit `e1c175c5` changed bootstrap behavior to stop and restart Kitty services cleanly when Gateway is unhealthy.

**Required verification:** confirm the new logic is idempotent and works after login, after an unclean shutdown, and when stale PID files or occupied ports exist.

### 2. Python package shadowing via `PYTHONPATH`

**OBSERVED root cause:** Open WebUI crashed while importing:

```text
from mcp import ClientSession
```

Python resolved `mcp` to Kitty's local package:

```text
/Users/jacobbrizinski/Projects/kitty/mcp/__init__.py
```

instead of the MCP SDK installed inside Open WebUI's isolated environment. The shell previously had the Kitty project on `PYTHONPATH`.

**Critical required fix:** sanitize the Open WebUI process environment in checked-in code. At minimum remove `PYTHONPATH` and `PYTHONHOME` before `Popen`, `execve`, and LaunchAgent service execution. Do not rely on Jacob manually prefixing commands with `env -u`.

Add a regression test proving the child Open WebUI environment cannot inherit a repository-level `PYTHONPATH` that shadows third-party modules.

### 3. Streaming smoke is not yet trustworthy

**OBSERVED:** Gateway and Open WebUI were both healthy, but the bootstrap ended with:

```text
streaming smoke did not produce a complete SSE response
```

This is not enough evidence to conclude whether:

- content streamed but the verifier rejected Kitty's termination semantics;
- Kitty omitted `[DONE]`;
- the parser ignored valid content shape;
- an upstream/provider error was encoded in SSE;
- or no usable content arrived.

**Required work:** capture and inspect the raw SSE event sequence once, compare it with `gateway/routes/completions.py`, OpenAI-compatible expectations, and Open WebUI behavior, then repair either the Gateway contract or the verifier. Do not weaken the smoke test merely to make it green. It must prove a real response, first content arrival, clean terminal state, and surfaced error events.

### 4. Auth-disabled configuration did not produce a clean single-user state

**OBSERVED:** despite intended `WEBUI_AUTH=False`, the initialized database created/reused pending `admin@localhost` records and blocked access.

**Required work:** determine the actual Open WebUI 0.10.2 behavior and persisted configuration involved. Make bootstrap idempotently establish the intended single-user local mode without creating duplicate pending users. Prefer supported application behavior/API over direct SQL. If direct DB repair remains necessary, make it schema-aware, backed up, narrow, and tested.

## Git/local-state caution

During setup, the local checkout had diverged. A protective stash and backup branch were created before resetting to the remote feature branch.

Observed commands created artifacts with names similar to:

- stash message: `pre-openwebui-bootstrap-20260802-123047`
- backup branch prefix: `backup/openwebui-local-...`

The exact current stash list, branch names, working tree, and whether main points where expected are **UNKNOWN until inspected locally**. Do not drop or rewrite them before reviewing their contents.

## Image generation context

### VERIFIED architectural direction

Read `docs/plans/image-studio-character-first-architecture-2026-07-28.md`, but respect its status: reviewed later-phase plan, not automatic execution authority.

Important retained decisions:

- Use Kitty's existing durable `image_jobs` lifecycle; do not create another queue/gallery/history.
- Retain and extend `gateway/image_characters.py`, `gateway/image_runner.py`, and the useful recipe vocabulary.
- Treat image generation as a character-first, session-oriented, dual-lane system:
  - hosted safe lane for drafting/finals/edits;
  - private open-weight lane for persistent fictional-adult identity, LoRAs, regional editing, and lawful explicit workflows.
- Do not claim recipe rows, models, or workers are operational without end-to-end proof.
- Do not present fake previews or mock artifacts as generated outputs.
- Do not burn paid GPU time through blind retries.
- Every paid run needs a defined hypothesis, bounded attempts, evidence capture, and explicit charge authorization.
- Current preferred initial architecture limits provider adapters rather than collecting providers.
- Image quality priorities include identity stability, anatomy, natural skin and hair texture, regional preservation, multi-character control, reliability, and successful-result cost.

Inspect live code and all relevant PRs before selecting current models; the dated plan may contain time-sensitive model assumptions.

Key code to inspect:

- `gateway/image_jobs.py`
- `gateway/image_characters.py`
- `gateway/image_runner.py`
- `gateway/image_recipes.py`
- image routes and current frontend Image Studio surfaces
- RunPod/ComfyUI scripts, workflows, workers, and recent failed/successful PR evidence

## Immediate onboarding objective

The first objective is not adding features. It is proving a boring daily-driver baseline:

1. A clean login/restart starts Gateway, LiteLLM, and Open WebUI once each.
2. `Kitty Chat` opens the correct URL.
3. Jacob enters without pending-account intervention.
4. `kitty-default` appears as the deliberate default.
5. A real response streams correctly through Open WebUI.
6. Chats and settings persist across a service restart.
7. `status`, `doctor`, `logs`, backup, restore, and rollback are accurate and actionable.
8. No inherited shell environment can corrupt the isolated Open WebUI runtime.
9. Existing Next.js UI remains a verified rollback.

Do not proceed to broader model menus, agents, skills, tools, Image Studio, Tutor, or Builder integration until this baseline passes through the actual UI and a restart.

## Next-agent operating rules

- Use one execution owner. Do not run interactive implementation and Builder on the same task concurrently.
- Use frontier reasoning for architecture, root-cause debugging, security, and final reconciliation.
- Use a strong coding model for implementation and tests.
- Use cheap bounded agents for inventories and read-only classification.
- Do not use subagents for trivial greps or overlapping edits.
- Work one vertical slice at a time; define acceptance criteria first and do not move on until it passes in the real UI.
- Maintain `docs/plans/openwebui-onboarding-progress.md` and a machine-readable acceptance checklist.
- Preserve backups and rollback throughout.
- Never expose or commit secrets, runtime databases, logs, personal content, model weights, or absolute local paths.
- Stop for new charges, destructive data risk, unavailable credentials, or publication/merge beyond authorization.

## First concrete task

After live inspection and canonical reading, fix the onboarding baseline defects above in this order:

1. sanitize Open WebUI child/LaunchAgent environment (`PYTHONPATH`, `PYTHONHOME`, and any other verified contaminant);
2. make account/bootstrap behavior idempotent and remove the pending-account trap without unsafe duplicate deletion;
3. inspect and repair the real SSE contract/smoke test;
4. verify cold login, daily launch, persistence, diagnostics, backup, and rollback;
5. update PR #384 with evidence and only then begin capability onboarding.

The next agent must replace every OBSERVED/UNKNOWN statement with fresh evidence as it works.