# Kitty Current Plans — 2026-07-24

**Canonical single source.** For the post-meta-analysis optimized plan, see
`docs/INITIATIVES_OPTIMIZED_2026-07-24.md`. For the session analysis of what
went wrong and what to do differently, see `docs/SESSION_META_2026-07-24.md`.

This file is the reference map. The other two are the action plan.

## Active Mission

**KFX-001: Frontend + Product-Experience Harvest** (running)
- Audit all Kitty surfaces, produce coherent product-experience plan
- Cross-product spike, KX initiative manifests
- See `docs/ACTIVE_MISSION.md`

## Immediate (this session, in progress)

Done in 2026-07-24 OpenCode session:

1. ✅ **Home has chat** — InputBar + messages on home view, no forced nav to chat tab
2. ✅ **Mobile chat usable** — InputBar on home, clutter (ThreadGoal/SignalFeed/TaskCards) hidden on mobile
3. ✅ **Chat speed** — parallel pre-processing in completions route, TTFT logging
4. ✅ **Model switch** — DeepSeek V4 Pro primary, Flash fallback, Mistral Small vision (`litellm_config.yaml`)
5. ✅ **Safe-area** — InputBar bottom inset + BottomNav fallback
6. ✅ **Testing capability** — expanded visual-diff (14 routes), swarm-review script (`make swarm-review`)
7. ✅ **Backend-frontend audit** — 12 unwired + 4 partially unwired routes found
8. ⚠️ **Blocked:** LiteLLM needs restart with `DEEPSEEK_API_KEY` for new model config
9. 📝 **Pending:** Fix 100vh → dvh in page.tsx (2 instances)
10. 📝 **Pending:** Wire Deep Tutor learn/review/grade to frontend
11. 📝 **Pending:** Fix 39 a11y issues found by swarm-review

## Stray Plans Consolidated

From `docs/planning/`:
- `brainstorm-kitty-evolution-2026-07-24.md` — Jacob's raw brainstorm (18 sections) → **absorbed into this doc's future sections**
- `kitty-next-evolution-working-notes.md` — Fable UX phase (Slice 3-5 remaining) → **retained, referenced below**
- `feature-reference-map.md` — feature↔repo map → **retained**
- `image-studio-character-system-2026-07-24.md` — Image studio redesign → **for other Orca instance**
- `kitty-vision-gap-analysis-2026-07-24.md` — Vision + gap analysis → **for other Orca instance**
- `kittybuilder-redesign-2026-07-24.md` — Builder redesign → **for other Orca instance**
- `agent-prompts-2026-07-24.md` — Agent prompts research → **for other Orca instance**

From `docs/plans/`:
- `KITTYBUILDER_DAILY_DRIVER_PLAN.md` — Builder UI plan → **retained**
- `KITTY_PRODUCT_EXPERIENCE_V1.md` — Product experience V1 → **retained**
- `KX_COHERENCE_AUDIT.md` — KX coherence audit → **retained**
- `fix-kitty-ui-wiring.md` — UI wiring fixes → **partially done, partially stale**
- `fix-council-ux-all.md` — Council UX fixes → **retained**
- `call-llm-error-contract.md` — Error contract → **retained**
- `feat-kittybuilder-follow-on-roadmap.md` — Builder roadmap → **retained**
- `skill-improvement-queue.md` — Skill improvements → **retained**
- 8 others are short/dated/single-purpose → **archive candidates**

## Feature Lanes (ordered by user impact)

### Lane 1 — Chat & Home (highest priority, actively shipping)
- ✅ Chat on home — done
- ✅ Mobile usable — done
- ✅ Speed improvements — done (parallel pre-processing + model switch)
- 📝 100vh → dvh viewport fix
- 📝 P2 polish: typography scale audit, pull-to-refresh, loading skeletons (from fable-ux-phase Slice 3+)

### Lane 2 — Deep Tutor (backend exists, frontend missing)
- 📝 Wire `/tutor/learn` — document ingestion from UI
- 📝 Wire `/tutor/review` — due review display
- 📝 Wire `/tutor/grade` — grading from UI
- 📝 Wire `/tutor/term/{term}` — mastery tracking display
- 📝 Tutor needs its own view (currently in Settings > Skills as text)
- See `docs/audit/backend-frontend-gap-2026-07-24.md`

### Lane 3 — KittyBuilder (needs redesign)
- Builder needs its own brain (system prompt)
- Chat interface to talk to Builder
- Initiative + task creation flow
- Graphical build progress map
- Builder should launch work through Orca/Ghostty/Claude Code
- See `docs/planning/kittybuilder-redesign-2026-07-24.md` (other Orca instance)

### Lane 4 — Image Studio
- Cloud compute via airforce.ai ($10 credit)
- Character system (cards, reliable recreation)
- Image import/upload
- See `docs/planning/image-studio-character-system-2026-07-24.md` (other Orca instance)

### Lane 5 — Documents
- Groups and folders (currently flat)
- Specialists with personality + persistent context
- See `docs/planning/brainstorm-kitty-evolution-2026-07-24.md` §6

### Lane 6 — Unwired Backend Routes
- Calendar, council, feedback, voice, integrations — backend exists, no frontend
- See `docs/audit/backend-frontend-gap-2026-07-24.md`

## Future Capabilities (not started)

- News tab (AI news, GitHub, Reddit, Substack, NYT, biohacking, music, audiophile)
- Journaling with pre-built prompts + auto-journal
- Marketplace / research agent
- Proactive insights ("did you know?")
- Life OS (money, doctors, dentist, benefits, emails)
- Computer control (run things locally, control apps/browsers)
- Small local model for personal data
- Recurring planning routine + dedicated future-thinker specialist
- Customer swarm / fake beta release
- Repo landscape research (Fabric, DSPy, Mastra, Onlook, etc.)

## Testing / Quality (shipping now)

- ✅ `make swarm-review` — automated a11y/design/mobile code audit
- ✅ `make visual-diff` — expanded to 14 routes (7 surfaces × 2 viewports × themes)
- ✅ `make ui-test` — 267 tests (1 pre-existing timeout flake)
- 📝 Need Playwright E2E test for core flows (home→chat→response)

## File Map

| What | Where |
|---|---|
| Current plans (canonical) | `docs/PLANS.md` (this file) |
| North Star | `docs/NORTH_STAR.md` |
| Blueprint | `docs/BLUEPRINT.md` |
| Architecture | `docs/ARCHITECTURE.md` + `docs/codemap/` |
| Future capabilities | `docs/FUTURE_CAPABILITIES.md` |
| Active mission | `docs/ACTIVE_MISSION.md` |
| Raw brainstorm | `docs/planning/brainstorm-kitty-evolution-2026-07-24.md` |
| Backend-frontend gap | `docs/audit/backend-frontend-gap-2026-07-24.md` |
| Architecture honesty audit | `docs/audit/architecture-honesty-2026-07-24.md` |
| Session state | `.claude/STATE.md` |
| KB project file | `kb/projects/kitty.md` |
| KB NOW | `kb/NOW.md` |

---

*This file supersedes: `docs/planning/brainstorm-kitty-evolution-2026-07-24.md` as the
actionable plan. The brainstorm remains as raw input. Other `docs/plans/` files
with stale/done content should be moved to `docs/archive/`.*
