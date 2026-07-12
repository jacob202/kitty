# Handoff — 2026-07-12

## TL;DR
Fable's `docs/fable-context` branch integrated. All 5 trust-lane-v1 packets (TL-01 through TL-05) implemented and merged to main. Two PRs open awaiting CI green + Jacob's merge:
- PR #151: `/search` param fix (`query`→`q`) — simple 1-line fix + lint cleanup
- PR #150: UI Phase 1 polish (unwired nav hidden, conditional sidebar, dashboard tile config) — rebased, resolving 2 SettingsPanel conflicts

## Resume
1. Check CI on #151 and #150 — both should be green (ruff clean locally)
2. Merge when green — #151 first (it's the simpler/safer one), then #150
3. Once both merged: Audit Card C remainder — `gateway/brief.py` and others still have silent `except Exception → return []`; do a fail-loud sweep across remaining modules

## Watch out
- PR #150 commit `20986db` removed the personality/models/usage sections from SettingsPanel in favour of a dashboard tile config UI. If Jacob wants personality editing back in Settings, that's a separate follow-up — the commit was intentional.
- The lint issues (E402, I001, F401) are in main right now. They'll be fixed once either PR merges. Don't open a third PR just for lint — redundant.
- trust-lane-v1 builder store is reconciled (all 5 tasks `done`). No builder state cleanup needed.

## T2 (Jacob/Codex only)
- Card A: UI binds 0.0.0.0; proxy injects gateway secret; SSRF in capture/knowledge
- Card B: agent_runner.py / task_runner.py false-complete states; stop() unreliable
