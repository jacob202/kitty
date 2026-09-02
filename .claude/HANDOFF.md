<!-- kitty-handoff: schema=v1 -->
# Handoff — Polish, SM-2, and Heist Launch



**Date:** 2026-09-01
**Head SHA:** 8a735903d3aaf15798cb671b64eba631f35a6aac
**Branch:** main
**Services:** Gateway ✓, LiteLLM ✓, UI ✓

## What Got Done

### Full stack running
First time this session. `./kitty health` shows all green: Gateway(:8000), LiteLLM(:8001), UI(:4000).

### SM-2 Spaced Repetition in Tutor
Replaced the fixed-interval scheduling (e.g. "correct → wait 3 days") with Anki's proven SM-2 algorithm:
- Each vocabulary term now tracks easiness factor (EF), repetition count, and interval
- Correct answer → interval grows (1→6→15→... days based on EF)
- Incorrect answer → interval resets to 1 day, EF decreases
- All 11 tutor tests pass
- Changes in `gateway/tutor.py`: +67 lines (SM-2 functions + columns + integration)

### CLI polish
- `./kitty up`: progress spinners, LiteLLM wait, summary dashboard with completion
- `./kitty health`: fast diagnostic showing all services + data dir + phone access

### UI improvements
- StatusBar green "connected" indicator when all healthy
- Home greeting uses preferredName + "home is quiet" instead of dead-end "not enough signal yet"

### Two scouting agents
1. First scout completed: `docs/scout-report.md` — 20 recommendations across 7 domains
2. Second heist agent (still running): looking for specific code to steal — SM-2 (done), optimistic updates, rich CLI, skeleton animations, hybrid search

## Files changed
- `kitty`: +127/-19 (startup polish + health command)
- `gateway/tutor.py`: +67 lines (SM-2 algorithm + columns)
- `gateway/kitty-chat/src/components/StatusBar.tsx`: +14 (connected indicator)
- `gateway/kitty-chat/src/components/HomeState.tsx`: +2 (greeting fix)
- `.claude/HANDOFF.md`: updated

## What to do next
1. Collect heist agent results when it finishes
2. Make the "connected" StatusBar indicator show on Home page (currently only on chat view)
3. Fix the ./kitty UI start script to not refuse uncommitted builds
4. The OpenRouter 429 rate limit means chat won't actually stream — needs paid credits or local MLX
