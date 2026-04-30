# Phase 4 Merge Gate

Date: 2026-04-30
Status: active integration checklist
Scope owner: mainline integrator

Purpose:
Provide a deterministic acceptance gate for parallel Phase 4 workers before any merge/checkpoint into release baseline.

## Current In-Flight Signals

- Modified: `src/core/specialists/registry.py`
- New file: `src/core/specialists/news.py`
- Modified log row: `docs/iteration_log.md` (includes one failed/unreachable eval row)

These changes are not auto-accepted. They must pass this gate.

## Required Acceptance Criteria

1. No regression in existing core routes:
   - `/api/brief`
   - `/api/command`
   - `/api/chat`
2. No specialist-registry import/runtime breakage.
3. Any new specialist has at least minimal test coverage.
4. `docs/iteration_log.md` entries reflect actual command evidence.
5. Full baseline suite remains green.

## Required Commands

Canonical runner:

```bash
scripts/run_phase4_merge_gate.sh --project /Users/jacobbrizinski/Projects/kitty-system/kitty-app --port 5001
```

Expanded/manual equivalent:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
/opt/homebrew/bin/python3.12 -m pytest tests/test_web_chat_phase1.py tests/test_brief_route.py tests/test_commands_route.py -q --tb=short
./kitty status
curl -fsS http://localhost:5001/api/brief
curl -fsS -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
curl -fsS -X POST http://localhost:5001/api/chat -H "Content-Type: application/json" -d '{"message":"phase4 merge gate","domain":"chat"}'
```

## Phase 4-Specific Test Additions Required If `NewsFeedSpecialist` Ships

Add/verify tests for:

- registry wiring includes `News`
- specialist can be instantiated
- prompt/safety output returns expected shape

Suggested test path:

- `tests/test_specialist_registry.py`
- `tests/test_news_specialist.py`

## Rejection Conditions

Reject Phase 4 merge if any of the following is true:

- adds runtime capability without tests
- alters specialist registry and breaks existing specialist lookup
- introduces unverifiable eval log claims
- causes full suite regression

## Completion Report Template

Every Phase 4 merge request must include:

- files changed
- commands run
- test results
- smoke route results
- known risks
