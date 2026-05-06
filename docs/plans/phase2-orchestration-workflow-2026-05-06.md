# Phase 2 Orchestration Workflow v2

Date: 2026-05-06
Scope: Phase 2 rollout execution protocol (`2A.1`, `2B`, `2C`)
Status: active workflow baseline

## Purpose

Remember and standardize the delegated Phase 2 execution workflow so follow-on lanes run with lower token cost, faster cycle time, and fewer integration failures.

## Effectiveness Evaluation (Run: 2026-05-06)

Measured signals from the active run:

1. Parallel delivery:
   - `SourceLedger` lane and `QuarantineQueue` lane delivered in one wave.
   - Both lanes completed with scoped ownership and no write-set conflict.

2. Test signal quality:
   - `10/10` targeted tests passed with `--noconftest`.
   - Repo-level strict command was blocked by existing `Icon` metadata guard.

3. Cost efficiency:
   - Cheap delegated models were used for execution lanes.
   - Actual token telemetry was extracted from Codex session logs and scored below.

4. Decision throughput:
   - Phase `2A` execution and scoring captured.
   - Phase `2A.1` foundation implementation started with concrete artifacts.

Overall effectiveness score (after real token audit): `6.7/10`.

### Actual Token Usage Audit (from session telemetry)

Source: `~/.codex/sessions/2026/05/06/*.jsonl`, using final `payload.info.total_token_usage` snapshots and first->last deltas per session.

Per delegated worker lane (Wave: `2A.1` implementation):

- Worker A (`019dfd68-1b8a-7381-a20b-dec6dfa8da1f`):
  - `delta total_tokens`: `466,643`
  - `delta input_tokens`: `452,898`
  - `delta cached_input_tokens`: `431,360`
  - estimated uncached prompt tokens (`input-cached`): `21,538`
- Worker B (`019dfd68-46d2-7e23-ba27-456f42329b22`):
  - `delta total_tokens`: `824,267`
  - `delta input_tokens`: `813,336`
  - `delta cached_input_tokens`: `779,904`
  - estimated uncached prompt tokens (`input-cached`): `33,432`
- Combined delegated lane usage:
  - `delta total_tokens`: `1,290,910`
  - estimated uncached prompt tokens: `54,970`

Related earlier delegated doc lanes (same day, bake-off documentation wave):

- Worker C (`019dfd49-a30d-7eb2-9e7f-5badc0c6edca`): `delta total_tokens` `5,302,290`
- Worker D (`019dfd49-c8d5-7231-b54e-8bab1296bc21`): `delta total_tokens` `5,216,312`
- Combined doc-lane usage: `10,518,602` total tokens

Parent orchestrator window for the `2A.1` worker wave (`13:09:11Z` to `13:15:03Z`):

- `delta total_tokens`: `3,296,533`
- `delta input_tokens`: `3,287,145`
- `delta cached_input_tokens`: `3,014,144`
- estimated uncached prompt tokens (`input-cached`): `273,001`

Conclusion: parallel execution succeeded technically, but token usage is high relative to task size because context payloads were large.

## What Worked

- Disjoint lane ownership prevented merge collisions.
- Delegating concrete bounded tasks to cheaper agents worked.
- For blocked strict tests, fallback verification captured useful signal without stalling execution.
- Closing agents immediately after completion prevented idle burn.

## What Failed / Friction

- Strict pytest gate blocked on unrelated `Icon` metadata files (`tests/memory/Icon` and `tests/memory/__pycache__/Icon`).
- Environment drift caused candidate execution asymmetry (module availability differed by interpreter).
- Candidate prototypes with large dependency surfaces (e.g., Cognee) increased maintenance burden and runtime setup cost.

## Improvements Applied

1. Add mandatory preflight checks before any delegated wave:
   - interpreter/module matrix (`homebrew` vs `venv`)
   - metadata guard scan (`find tests -name 'Icon*'`)
   - dirty-tree snapshot

2. Add two-tier verification policy:
   - Tier 1: strict command (default gate)
   - Tier 2: scoped fallback (`--noconftest`) when strict gate is blocked by unrelated repo hygiene
   - Always record blocker path and exact guard failure

3. Add lane contract template:
   - ownership files
   - forbidden files
   - validation command
   - final report fields (`files changed`, `tests`, `blockers`)

4. Add dependency policy for prototype candidates:
   - install only in isolated venv
   - record package footprint
   - score maintenance burden explicitly from actual install/runtime evidence

5. Add closure rule:
   - close all completed agents immediately
   - no idle agent carry-over across phases

6. Add hard token budget controls (new):
   - set lane budget before dispatch (`target <= 250k total_tokens` per code lane)
   - fail lane if over budget without proportional artifact value
   - report both `total_tokens` and uncached prompt estimate (`input-cached`)

7. Minimize delegated context payload (new):
   - default `fork_context=false` for workers unless required
   - pass only task brief + owned file list + exact validation command
   - do not delegate broad summary/doc writing unless it is a blocked critical path

8. Force cheaper inference settings (new):
   - delegated model: `gpt-5.4-mini`
   - reasoning effort: `low` for bounded implementation lanes
   - escalate model/reasoning only after failing validation attempts

9. Add low-capability deterministic execution mode (new):
   - use fixed micro-brief format for worker dispatch
   - one worker per atomic task card
   - bounded read set (no broad exploratory scans)
   - explicit stop conditions to prevent low-quality guesswork

## Workflow v2 (Execution Template)

### Stage 0: Preflight

- Capture `git status --short`.
- Scan metadata blockers.
- Record module availability in both interpreters.
- Record blocked files outside owned lane.

### Stage 1: Lane Design

- Break work into disjoint write sets.
- Put high-risk shared-file tasks in later waves.
- Assign cheap model workers to bounded lanes.
- Decompose lanes into atomic task cards with single validation commands.

### Stage 2: Delegated Execution

- Dispatch lanes with explicit ownership and test command.
- Use minimal context payload and explicit token budget per lane.
- Poll and capture outputs.
- Do not overlap lanes on same files.
- Use fixed worker micro-brief template from `docs/superpowers/plans/2026-05-phase2-low-capability-execution.md`.

### Stage 3: Verification

- Run strict test command.
- If blocked by unrelated global guard, run scoped fallback and record blocker.
- Integrate only after local review of changed files.
- Reject completion claims that omit command output or owned-file evidence.

### Stage 4: Integration

- Update build trackers (`TASKS.md`, `docs/TASKS.md`, handoff).
- Keep decision/report/plan artifacts aligned.
- Close completed agents.

### Stage 5: Next-Wave Handoff

- Publish:
  - completed lanes
  - blockers
  - exact next wave tasks
  - file ownership map for the next dispatch

## Next Use

Use this workflow for:
- Phase `2C` delegated rollout

Reference execution packet:
- `docs/superpowers/plans/2026-05-phase2-low-capability-execution.md`
- `docs/plans/phase2-build-plan-meta-analysis-2026-05-06.md`
