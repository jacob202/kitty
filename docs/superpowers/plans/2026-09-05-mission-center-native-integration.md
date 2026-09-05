# Mission Center Native Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the accepted Mission Center backend nucleus into the smallest real native Kitty Mission journey without creating competing state, scheduling, execution, or authorization systems.

**Architecture:** Mission semantics remain Gateway-owned in `memory_mission` / `context_mission`; Builder remains execution authority; GAR remains collaboration authority; Automation/cron remain wake authority. Add only thin Gateway API/startup adapters and extend the existing Chat→Builder handoff so one user-stated outcome gains durable Mission identity, bounded execution locators, review/acceptance state, restart continuity, and truthful controls.

**Tech Stack:** Python, FastAPI, SQLite, existing Kitty Automation/cron/Builder/GAR seams, Next.js/React Query, pytest/Ruff/mypy/Vitest/Playwright.

**Spec:** Project Source `Kitty Mission Center Protocol`; live repository authority from `START_HERE.md`, Constitution, Architecture, ADR 0017, Active Mission, and current Git/KX/GAR/Builder state.

## Global Constraints

- Do not add a second queue, scheduler, Mission database, authorization model, router, or supervisor framework.
- Do not duplicate Builder, GAR, Automation, Git/GitHub, KX, or provider truth into Mission state; store locators/digests and refresh mutable truth before reliance.
- No paid provider/model calls without separate authorization.
- Preserve worker/reviewer independence and bind plan review and acceptance to exact digests/candidates.
- User-facing completion requires a real running-product journey and truthful failure/recovery behavior.
- Respect current KX ownership; no mutation to a path while another valid semantic owner holds it.

---

### Task 1: Freeze the Mission state engine and expose a thin Gateway API

**Files:**
- Modify after current owner releases: `gateway/memory_mission.py`
- Create: `gateway/routes/missions.py`
- Modify: `gateway/routes/register.py`
- Test: `tests/test_missions_routes.py`

**Interfaces:**
- Consumes existing `create_mission`, `get_mission`, `pause_mission`, `resume_mission`, `stop_mission`, plan/candidate review bindings.
- Produces `POST /missions`, `GET /missions`, `GET /missions/{id}`, and pause/resume/stop commands. API returns Mission-owned state plus external locators, never copied Builder execution truth.

- [ ] Write a failing route test proving create → reload/list/get preserves objective, definition of done, status, and supervisor identity in the existing Kitty SQLite database.
- [ ] Run only that test and verify RED because the Mission route/list API does not exist.
- [ ] Add the smallest `list_missions()` store query and thin FastAPI route; do not add another service/store.
- [ ] Add failing tests for pause/resume/stop and stale/unknown IDs, then implement only the required route behavior.
- [ ] Run focused pytest, Ruff, mypy, and diff-check.

### Task 2: Bind existing Chat→Builder proposals to durable Mission identity

**Files:**
- Modify: `gateway/conversation_handoff.py`
- Modify: `gateway/routes/conversation_handoff.py`
- Test: `tests/test_conversation_handoff.py`
- Test: `tests/test_conversation_handoff_routes.py`

**Interfaces:**
- `propose()` continues to use the one existing Builder `mission_prepare` contract.
- A successful proposal creates/updates one Gateway Mission with plan artifact locator+digest; Builder remains untouched until explicit approval.
- An approved Builder job stores only its durable Builder mission/task locator in the Gateway Mission checkpoint; resume always rereads Builder through the existing supported projection.

- [ ] Write a failing test proving one conversation proposal yields one durable Gateway Mission ID and no Builder queue job.
- [ ] Verify RED, then bind proposal metadata to Mission state without changing Builder approval semantics.
- [ ] Write a failing test proving approval retains the same Gateway Mission ID while storing only the Builder locator, and idempotent replay does not create a second Mission.
- [ ] Verify RED, implement the binding, and preserve the existing explicit `confirmed=True` human approval boundary.
- [ ] Write and pass interruption/reload tests: lost client receipt recovers the same Gateway Mission + Builder locator rather than recompiling duplicate work.

### Task 3: Use existing Automation/GAR seams for Mission wake and review evidence

**Files:**
- Create: `gateway/mission_runtime.py`
- Modify: `gateway/app.py`
- Test: `tests/test_app_lifespan_hermetic.py`
- Test: `tests/test_mission_runtime.py`

**Interfaces:**
- Registers Mission actions through `automation_actions.register_action`; does not create a Mission scheduler or new action-grant scope.
- Uses explicit source bindings such as `observe_global_thread()` and supported Builder projections; source failures remain unavailable/blocked rather than guessed.
- Delegated effects continue through existing Builder/Automation authorization boundaries.

- [ ] Write a failing lifespan test proving startup registers the Mission action through the existing Automation registry and does not seed a parallel scheduler.
- [ ] Verify RED, add a small registration helper, and keep cron/Automation as the only wake authority.
- [ ] Write failing runtime tests for changed source, unchanged source, paused/stopped Mission, source unavailable, and restart/resume.
- [ ] Implement only the adapter needed to make those tests pass; no provider-specific architecture.
- [ ] Run focused Mission + Automation + lifespan tests, Ruff, mypy, and diff-check.

### Task 4: Show Mission continuity in existing native surfaces

**Files:**
- Modify: `gateway/kitty-chat/src/lib/gateway.ts`
- Modify: `gateway/kitty-chat/src/lib/queries.ts`
- Modify the existing Chat proposal component and/or Home state component selected from the exact current candidate; do not add a new rail/page merely for Mission Center.
- Test the exact component(s) changed.

**Interfaces:**
- Chat remains where Jacob states the outcome and approves consequential Builder execution.
- Home/Work projects Mission-owned status and the next human decision; Builder details remain Builder-owned.

- [ ] Write failing UI tests proving a proposed outcome shows durable Mission status and survives component reload/remount without requiring an internal ID from Jacob.
- [ ] Verify RED, then add the minimal query/client projection and existing-surface UI.
- [ ] Add failing tests for paused/blocked/needs-Jacob/degraded source states and implement truthful copy/actions.
- [ ] Run focused Vitest and TypeScript checks.

### Task 5: Exact-candidate product acceptance and publication boundary

**Evidence required:**
- Exact branch/head/tree identity and clean-state evidence.
- Focused backend/UI tests, Ruff, mypy, TypeScript, and relevant CI.
- Running Gateway/native UI evidence for: state outcome → durable Mission → bounded proposal → explicit approval → Builder locator/progress → interruption/reload → resume → independent acceptance binding or truthful non-DONE state.
- Failure case with unavailable dependency and no false success.
- Independent reviewer who did not implement the candidate.

- [ ] Run the actual desktop and iPhone-class journey against the exact final candidate.
- [ ] Restart/reload during active work and prove Mission identity + authoritative external locators recover without duplicate execution.
- [ ] Obtain independent exact-head review/acceptance using a zero-cost path unless Jacob separately authorizes paid review.
- [ ] Repair any actionable finding, change candidate identity, and rerun affected evidence.
- [ ] Push the non-main branch and open/update its PR. Do not merge without separate merge authorization.

**Definition of done:** This integration slice is complete only when Jacob can state one supported outcome through normal Kitty, receive one durable Mission identity without becoming dispatcher, approve only the action class that genuinely requires him, survive reload/restart/worker replacement without duplicated work, and see truthful Mission progress/result backed by exact-candidate evidence. If independent acceptance or the real journey is unavailable, report `PARTIALLY_COMPLETE` / `completed_unreviewed`, never DONE.