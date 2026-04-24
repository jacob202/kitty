# Phase 4: Reliability + Eval Platform
**Date:** 2026-04-23  
**Goal:** Build a deterministic, append-only eval platform around the stable web surface. No swarm dependency.  
**Depends on:** Phase 2 capability platform and Phase 3 memory/reasoning surfaces  
**Primary test command:** `/opt/homebrew/bin/python3.12 -m pytest tests/test_reliability_platform.py -q`

---

## Current State

The repo already has enough stable primitives to support a real eval platform:

- working Flask app factory in `web.py`
- stable test client paths for:
  - `/api/capabilities`
  - `/api/chat`
  - `/api/transcribe`
  - `/`
- existing smoke-level regression tests already cover chat and voice basics
- persona-related building blocks already exist:
  - `src/modules/persona_engine.py`
  - performance metrics utilities
- reporting utilities already exist in `src/utils/performance_monitor.py` via `DashboardGenerator`

The repo also has unstable or misleading surfaces that must **not** be the backbone of this phase:

- `/api/swarm/*` is hidden by default and not dependable
- `/api/eval/scorecard` is internal-only and not the source of truth
- some prior reporting wrappers are broken or orphaned

That means Phase 4 must build a plain Python eval system using:

- test client checks
- append-only JSON artifacts
- optional persona fixtures
- explicit API triggers

Not:

- swarm orchestration
- hidden internal routes as core dependencies
- external browser/agent infrastructure as the primary implementation path

---

## What Phase 4 Still Needs

`docs/TASKS.md` says Phase 4 still needs:

1. eval domain model
2. targeted pytest eval suite
3. browser smoke flows
4. persona scripts with consistent scoring
5. artifact capture + daily summaries
6. self-improving eval loop
7. revisit swarm only after all of the above are stable

This plan should implement the foundation for items 1-5 and define the interfaces needed for 6, without trying to build autonomous optimization in the same pass.

---

## Task 1: Eval Domain Model

**Files**
- Create: `src/core/eval_domain.py`
- Create or extend: `tests/test_reliability_platform.py`

### Required types

Create small serializable dataclasses:

- `EvalRun`
- `EvalCheck`
- `EvalCheckResult`
- `EvalScore`
- `EvalResult`

Required behavior:

- `EvalRun.start(suite: str)` creates unique run ids
- `EvalCheck.record(...)` returns an `EvalCheckResult`
- `EvalScore.rate` returns `passed / total`
- `EvalScore.meets_baseline(...)` compares against a float threshold
- `EvalResult.to_dict()` must be JSON-serializable

Keep the names `Eval*`, not `Suite*`, so the model matches the phase language in `TASKS.md`.

### Tests to add first

- unique run ids
- pass/fail check recording
- score baseline comparison
- full result serialization

---

## Task 2: Smoke Eval Runner

**Files**
- Create: `evals/smoke_suite.py`
- Create: `evals/artifacts/.gitkeep`
- Extend: `tests/test_reliability_platform.py`

### Required checks

The smoke suite should use Flask test client only in this phase.

Checks:

- `/api/capabilities` returns `200` with expected shape
- `/api/transcribe` returns `400` for missing file, not `500`
- `/` contains the voice button
- `/` does not contain `/voice_poll`
- `/api/chat` is reachable and does not return `500` or `503`

Optional additional safe checks:

- internal-only routes are hidden by default
- `/api/capabilities/explain` returns `200` once Phase 2 lands

### Artifact requirements

- write append-only JSON artifacts to `evals/artifacts/`
- one artifact per run
- do not overwrite old artifacts

Expected artifact shape:

```json
{
  "run_id": "...",
  "suite": "smoke",
  "started_at": 123.0,
  "scores": {
    "smoke": {"passed": 5, "total": 5, "rate": 1.0}
  },
  "checks": [...]
}
```

### Tests to add first

- smoke suite runs without external network/browser dependency
- smoke suite writes exactly one artifact in a temp artifact directory
- smoke suite raises when it drops below baseline

---

## Task 3: Regression Detection

**Files**
- Create: `evals/compare_runs.py`
- Extend: `tests/test_reliability_platform.py`

### Required behavior

Implement:

- `detect_regression(prev_artifact_dir: Path, current_scores: dict, *, suite: str = "smoke", threshold: float = 0.05) -> dict`

Behavior:

- compare current run against the most recent artifact for the suite
- return structured regression metadata
- no previous artifact should be a non-regression with a reason string

Expected return shape:

```json
{
  "is_regression": true,
  "delta": -0.2,
  "prev_rate": 1.0,
  "curr_rate": 0.8,
  "prev_run_id": "abcd1234"
}
```

### Tests to add first

- score drop > threshold is a regression
- score drop <= threshold is not
- no prior artifact returns non-regression with a reason

---

## Task 4: Eval Trigger Route

**Files**
- Create: `src/api/eval_routes.py`
- Modify: `src/api/__init__.py`
- Modify: `web.py`
- Extend: `tests/test_reliability_platform.py`

### Route

Add:

- `POST /api/eval/run`

This route is public product infrastructure, not an internal-only route.

### Request body

```json
{
  "suite": "smoke"
}
```

### Response behavior

For known suites:

- `200` on success with score payload
- `422` when the suite runs but fails its baseline
- `400` for unknown suite
- `500` only for unexpected execution errors

Expected success response:

```json
{
  "ok": true,
  "run_id": "abcd1234",
  "score": {
    "passed": 5,
    "total": 5,
    "rate": 1.0
  }
}
```

### Tests to add first

- smoke suite trigger returns score payload
- unknown suite returns `400`
- baseline failure returns `422`

---

## Task 5: Persona Fixtures and Daily Summary Hook

**Files**
- Create: `evals/personas/basic.json` or `evals/personas/basic.yaml`
- Create: `evals/persona_suite.py`
- Optionally use: `src/modules/persona_engine.py`
- Extend: `tests/test_reliability_platform.py`

### Required scope for this phase

Do not build the full multi-week scheduler here.

Instead, build the minimal interfaces that make it possible:

- persona fixture format
- persona suite runner that produces append-only artifacts
- daily summary generator that can call `DashboardGenerator.generate_daily_report(...)`

Persona fixture requirements:

- at least one beginner/confused persona
- at least one urgent/frustrated persona
- deterministic prompts and expected checks

Persona suite output must include:

- persona id
- prompt
- pass/fail
- reason
- run id

### Tests to add first

- persona fixture loads
- persona suite produces structured results
- daily summary hook returns a report path or structured success value

---

## Implementation Notes

- Keep this platform browser-free by default in-repo; real browser-agent tests can be layered on later
- Use existing app factory and stable routes
- Keep artifacts append-only
- Use `DashboardGenerator` only as a reporting helper, not as the sole source of truth
- Do not resurrect swarm as a dependency
- Do not rely on hidden internal routes for normal eval operation

---

## Acceptance Criteria

- [ ] `EvalRun`, `EvalCheck`, `EvalScore`, and `EvalResult` exist and are tested
- [ ] `run_smoke_suite()` runs entirely from stable in-repo primitives
- [ ] append-only JSON artifacts are written to `evals/artifacts/`
- [ ] `detect_regression()` works against the latest artifact
- [ ] `POST /api/eval/run` triggers a smoke eval and returns structured results
- [ ] persona fixture loading and persona result serialization exist
- [ ] no swarm API is used anywhere in this phase
- [ ] All tests pass:
  - `/opt/homebrew/bin/python3.12 -m pytest tests/test_reliability_platform.py -q`
  - `/opt/homebrew/bin/python3.12 -m pytest tests/test_capability_pruning.py tests/test_web_chat_phase1.py tests/test_voice_routes.py tests/test_voice_ui_template.py tests/test_voice_transcriber.py -q`

---

## Suggested Commit

```bash
git add src/core/eval_domain.py evals/smoke_suite.py evals/compare_runs.py evals/persona_suite.py evals/personas/basic.json evals/artifacts/.gitkeep src/api/eval_routes.py tests/test_reliability_platform.py docs/plans/2026-04-23-phase4-eval-platform.md
git commit -m "feat: build eval platform foundation"
```
