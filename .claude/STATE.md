# Session State — 2026-07-12

## Branch
- `main` @ `07c901f` — TL-01 through TL-05 all merged.
- Working on: `fix/search-route-query-param` (PR #151) and `claude/kittybuilder-dogfood-preflight-bif2qb` (PR #150)

## Landed this session

### Fable branch integration (done)
- `docs/fable-context` fast-forwarded into `main` (already on Jacob's Mac + origin).
- All 5 trust-lane-v1 packets implemented and merged into main:
  - TL-01 (`1df1eee`): What's Next error state + retry button in HomeState
  - TL-02 (`68249b4`): gateway freshness check in doctor.py
  - TL-03 (`00c7590`): Enter-to-send / Shift+Enter tests for InputBar
  - TL-04 (`7aedd18`): mascot aria-hidden + pointer-events:none
  - TL-05 (`07c901f`): memory read paths raise MemoryError, routes re-raise as HTTP 500

## Open PRs

### PR #151 — fix/search-route-query-param
- `/search` route param renamed `query`→`q` to match UI and `/knowledge/search`
- Rebased onto current main; lint fixes included

### PR #150 — claude/kittybuilder-dogfood-preflight-bif2qb
- UI Phase 1: hide unwired nav, conditional sidebar, remove dev notes, empty states, GlyphIcon/MoodAvatar deleted, dashboard tile config
- Rebasing onto main in progress

## Known lint debt on main
The E402/I001/F401 issues in memory.py, register.py, test_doctor_freshness.py, test_memory_fail_loud.py are fixed on PR #151 but not yet on main (waiting for merge). PR #150 also carries those fixes independently.

## T2 (Jacob/Codex only — do not touch)
- Card A: UI binds 0.0.0.0 in ./kitty + proxy injects gateway secret; SSRF in capture/knowledge routes
- Card B: agent_runner.py / task_runner.py can false-complete tasks; stop() unreliable
