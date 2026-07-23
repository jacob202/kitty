# Handoff — Branch Cleanup + KX Shell/Surfaces + Builder Queue Complete

## What was done

### Repository cleanup
- Closed 4 stale PRs (#230, #232, #233, #234)
- Deleted all 132 remote branches — only `origin/main` remains
- 10 branches merged into main, 1 reverted (img01 — broken API migration)

### KX Endgame (UI/UX)
- **KX-03** (4 packets): View registry, 14→7 surface collapse, design clutter cleanup, SVG cat mascot with real state hook
- **KX-04** (6 packets): Shared primitives refit across Work, Studio, Library, Settings
- **KX-05** (5 packets): All implemented end-to-end:
  - KX-05-01: Onboarding persists to gateway `app_settings` table (cross-device), import wizard step for ChatGPT conversations.json
  - KX-05-02: `/repairs` endpoint with plain-English titles, T0 action-queue fix buttons, Home card, chat intent detection ("what's wrong")
  - KX-05-03: `/builder/action` endpoint (run/pause/resume/cancel/cleanup through T0 action queue), BuilderControls component, fixed `packetNeedsAttention` to exclude cancelled
  - KX-05-04: `/knowledge/experts` from books_manifest (5 experts: builder 81, mind 53, wisdom 52, body 25, voice 8), ExpertStrip on Home
  - KX-05-05: ActiveTaskCards capped at 3 + test-data filter, StatusBar 3-consecutive-fail threshold, memory evidence smalltalk suppression, session resume heading fix, CLI copy purged (7 places)

### Backend new files
- `gateway/onboarding.py` — persist onboarding state in app_settings
- `gateway/routes/onboarding.py` — GET/POST /onboarding
- `gateway/routes/import_chatgpt.py` — file upload → extraction pipeline
- `gateway/routes/builder_control.py` — POST /builder/action
- `gateway/actions/repair_check.py`, `repair_dismiss.py` — T0 repair executors
- `gateway/actions/builder_*.py` (5 files) — T0 builder executors
- `config/action_tiers.json` — added 7 new T0 action kinds

### Builder Queue
- 15 initiatives resolved: 11 completed, 4 failed
- Builder actions wired to CLI (no longer stubs)
- B1 preflight evidence, B2 gap register, B8 initiative progress cards

### Cross-tool kb
- Skill audit of 22 Kitty repo skills
- Built `add-new-resource` and `improve-system` skills in `~/kb/.claude/skills/`
- Verification language added to CLAUDE.md
- Expert swarm review skill at `.agents/skills/expert-swarm/SKILL.md`

### Expert Swarm Review
- 8 experts (6 core + 2 wildcard) reviewed live UI
- 22 issues identified across UX, visual, perf, mobile, a11y, onboarding
- P0-P1 consensus fixes built (personalized greeting, mobile bottom nav, a11y labels, cat animations)

### Self-repairs
- `GET /repairs` endpoint with actionable fix suggestions
- Surfaced on Home via RepairsCard
- Chat intent: "what's wrong" injects repair feed into system context

### Verification
- Frontend TypeScript clean
- 66/66 affected tests pass (HomeState, BuilderSurface, OnboardingModal, StatusBar)
- 19/19 BuilderSurface tests pass
- 130/132 backend tests pass (2 fail on LiteLLM being down locally)
- Python imports verified: onboarding, repairs, builder_control all import clean

## Lessons learned this session

1. **Builder workers were stuck as `[blocked]`** — initiatives need their top-level gate cleared before packets can flow. Manual builds in OpenCode are faster than debugging the worker ladder.
2. **Action executors must exist before action kinds are registered** — the action queue fails on `UnknownActionKind` if a kind is in `action_tiers.json` but no executor file exists. Keep them paired.
3. **Test assertions by exact text are brittle** — changing CLI copy (./kitty up → plain English) broke 4 test assertions. Consider snapshot patterns for user-facing strings.
4. **StatusBar flapping was a render-count issue, not a polling issue** — the fix is a render-side ref counter, not a polling debounce. `useEffect` on a stable prop only fires once — use raw ref increment in the function body.

## Files changed
140+ files across gateway/, docs/, kb/, config/

## Blockers
None.

## Invalidation
HEAD beyond `72f0e85`.
