# Kitty — Eval Scores

**Purpose:** Append-only record of eval runs, baselines, and what changed. If a score drops, record why and what fixed it.

---

## Baseline

| Suite | Pass Rate | Set On | Notes |
|-------|-----------|--------|-------|
| smoke | 95–100% | 2026-04-23 | 5 checks: capabilities 200, transcribe 400, index has voice button, no /voice_poll, chat not 500 |

**Never lower the baseline without explicit decision.** If a legitimate architectural change causes a drop, update both the baseline and this table with a reason.

---

## How to Run

```bash
# Quick smoke check (pytest only):
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short

# Full eval loop (pytest + route + regression detection):
/opt/homebrew/bin/python3.12 scripts/eval_loop.py

# Eval route directly (app must be running on 8000):
curl -s -X POST http://localhost:8000/api/eval/run \
  -H "Content-Type: application/json" \
  -d '{"suite":"smoke"}'
```

Route responses:
- `200` → suite passed, score in body
- `422` → baseline regression detected
- `400` → unknown suite name

---

## Regression History

| Date | Suite | Score | Delta | Cause | Fix |
|------|-------|-------|-------|-------|-----|
| 2026-04-23 | smoke | 100% | — | Baseline established | — |
| 2026-04-24 | smoke | 100% (5/5) | 0 | No regression — run_id d4d8016d | 92 tests passed; model defaults changed to openrouter/free |

---

## What Triggers a Required Eval Run

Run evals (not just pytest) after any of these:
- Changes to `evals/smoke_suite.py` or `evals/compare_runs.py`
- Changes to `src/api/dispatcher.py`, `streaming_routes.py`, or `reasoning_routes.py`
- Changes to `src/core/context_manager.py` or `context_budget.py`
- Changes to ChromaDB integration
- Any specialist config changes in `config/specialists/`
- Any change to the eval route (`src/api/eval_routes.py`)

---

## Smoke Suite Checks (v1)

1. `GET /api/capabilities` → 200
2. `POST /api/transcribe` with no file → 400 (not 500)
3. `GET /` index page contains `voice-toggle` in HTML
4. No route `/voice_poll` exists (was removed — SSE replaced polling)
5. `POST /api/chat` → not 500 (endpoint alive)

---

## Persona Suite

Fixtures in `evals/personas/basic.json`:
- `beginner_confused` — vague short queries, expects guidance
- `urgent_frustrated` — frustrated tone, expects direct action
- `power_user` — technical detail, expects precise answers

Run with `evals/persona_suite.py → run_persona_suite()`.

---

<!-- Append new run records to the Regression History table above -->
