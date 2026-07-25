# Kitty Session Status — 2026-07-24

**Roadmap authority: `docs/INITIATIVES_OPTIMIZED_2026-07-24.md`** (per
`docs/AUTHORITY_MAP.md`). That file owns feature sequencing, layered
priority (F0-V4), and what's explicitly rejected. `docs/SESSION_META_2026-07-24.md`
is the analysis that fed into it, not a competing plan.

This file is a status tracker, not the roadmap: what's shipped this session,
what's blocked, and where things live. If this file and the roadmap
disagree on priority or sequencing, the roadmap wins.

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

**2026-07-25:** the dispositions below were executed, not just recorded — see
`docs/archive/ARCHIVE_MANIFEST_2026-07-25.md` for what actually moved (5
files) and what was checked and kept despite looking like a candidate (2
files were still "Ready to implement," not stale).

From `docs/planning/`:
- `brainstorm-kitty-evolution-2026-07-24.md` — Jacob's raw brainstorm (18 sections) → **absorbed into this doc's future sections; archived 2026-07-25**
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
- `skill-improvement-queue.md` — Skill improvements → **retained** (file not found on disk as of 2026-07-25; likely renamed or already merged elsewhere)
- `migration-health.md`, `chore-workspace-cleanup-2026-07-12.md`, `pr164-archaeology.md` — **archived 2026-07-25**, confirmed stale
- `image-runner-and-recipe-cleanup.md`, `memory-graph-contract-enforcement.md` — checked 2026-07-25, both still say "Status: Ready to implement" → **not stale, kept**
- `chore-master-fix-and-deepen.md`, `t1-upload-smoke-ci.md` — not short, not clearly done → **left for a real review, not archived on a guess**

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
- **Owned by a different tool session, not this roadmap.** Plan lives at
  `docs/planning/kittybuilder-redesign-2026-07-24.md`; tracked in `~/kb` for
  cross-tool visibility, not here.

### Lane 4 — Image Studio
- Cloud compute via airforce.ai ($10 credit)
- Character system (cards, reliable recreation)
- Image import/upload
- **Owned by a different tool session, not this roadmap.** Plan lives at
  `docs/planning/image-studio-character-system-2026-07-24.md`; tracked in
  `~/kb` for cross-tool visibility, not here.

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

---

## Competitive Analysis — AI Assistant Slickness Gap (2026-07-25)

**Method:** Deep-dived 6 top open-source AI assistants (Open WebUI 146k⭐, Goose 51k⭐,
LibreChat 41k⭐, Khoj 36k⭐, Chatbot UI 33k⭐, AionUi 31k⭐) — examined their actual
frontend code, backend structure, config patterns, and deployment UX. Not a feature
checklist. A design-decision and code-pattern analysis.

### Why Kitty isn't "slick" yet

The core problem: **Kitty tries to do everything but doesn't polish any one thing.**
The other projects do less, but what they do feels complete. Every action has a loading
state, an error state, a success state, keyboard shortcuts, and mobile support.

### 7 Initiatives Derived from the Gap Analysis

**Priority: P0 = immediate (next 2 weeks), P1 = near-term (this month), P2 = backlog**

#### Initiative UX — Core UI Patterns (P0)

| Packet | What | Why | From | Effort |
|--------|------|-----|------|--------|
| UX-01 | Onboarding wizard (first-run) | Users see a blank page with no guidance | Open WebUI OnBoarding.svelte | 2d |
| UX-02 | Keyboard shortcut system | `Cmd+K` search, `Ctrl+Enter` send | Open WebUI shortcuts.ts | 1d |
| UX-03 | Notification toast system | Centralized success/error/info toasts | Open WebUI NotificationToast.svelte | 1d |
| UX-04 | Loading skeletons | Placeholder UI during load, not spinners | Open WebUI, LibreChat | 2d |
| UX-05 | Error boundary + error page | Graceful errors instead of tracebacks | Open WebUI +error.svelte | 1d |
| UX-06 | Changelog modal | Show what's new after update | Open WebUI ChangelogModal.svelte | 0.5d |

#### Initiative MOB — Mobile Experience (P0)

| Packet | What | Why | From | Effort |
|--------|------|-----|------|--------|
| MOB-01 | Dedicated mobile stylesheet | Mobile is primary access point | LibreChat mobile.css | 2d |
| MOB-02 | Touch-friendly interactions | Buttons, inputs sized for touch | Various | 1d |
| MOB-03 | Bottom navigation for mobile | Thumb-friendly nav | Various | 1d |
| MOB-04 | PWA / service worker | Offline support, app-like feel | LibreChat sw/ | 2d |

#### Initiative ARCH — Architecture Cleanup (P1)

| Packet | What | Why | From | Effort |
|--------|------|-----|------|--------|
| ARCH-01 | Organize gateway/ into domain subdirs | 160+ flat files is unmanageable | Khoj processor/, Open WebUI routers/ | 3d |
| ARCH-02 | Single config file (kitty.example.yaml) | Config is scattered everywhere | LibreChat librechat.example.yaml | 2d |
| ARCH-03 | Data provider layer | Abstract API calls from components | LibreChat data-provider/ | 3d |
| ARCH-04 | Store layer for state management | Centralized state, not ad-hoc | LibreChat store/, Open WebUI stores/ | 2d |
| ARCH-05 | Pre-commit hooks | Lint/format/typecheck before commit | AionUi, Open WebUI | 1d |

#### Initiative A11Y — Accessibility (P1)

| Packet | What | Why | From | Effort |
|--------|------|-----|------|--------|
| A11Y-01 | A11y audit | Find all issues systematically | LibreChat a11y/ | 2d |
| A11Y-02 | Focus management | Keyboard navigation works | LibreChat a11y/ | 1d |
| A11Y-03 | Screen reader support | aria labels, roles, live regions | LibreChat a11y/ | 2d |

#### Initiative I18N — Internationalization (P2)

| Packet | What | Why | From | Effort |
|--------|------|-----|------|--------|
| I18N-01 | Extract strings to locale files | English-only limits reach | Open WebUI i18n/, LibreChat locales/ | 3d |
| I18N-02 | Add i18n framework | Foundation for translations | Open WebUI, LibreChat | 1d |

#### Initiative FEAT — Feature Parity (P2)

| Packet | What | Why | From | Effort |
|--------|------|-----|------|--------|
| FEAT-01 | Research pipeline | Deep research with citations | Khoj research.py | 3d |
| FEAT-02 | Code interpreter (pyodide/sandbox) | Run code in-browser | LibreChat, Open WebUI pyodide | 5d |
| FEAT-03 | Artifact rendering | Rendered outputs (charts, code) | LibreChat | 4d |
| FEAT-04 | Automation/schedules UI | Scheduled research digests | Khoj api_automation.py | 2d |
| FEAT-05 | Obsidian plugin | Reach users where they work | Khoj obsidian/ | 3d |
| FEAT-06 | Emoji picker | Inline emoji | Open WebUI | 1d |

#### Initiative DEVOPS — Deployment & DevOps (P2)

| Packet | What | Why | From | Effort |
|--------|------|-----|------|--------|
| DEVOPS-01 | Docker compose profiles | GPU, API-only, data variants | Open WebUI (10+ compose files) | 1d |
| DEVOPS-02 | One-liner install script | `curl | bash` or `docker run` | Goose, Open WebUI | 1d |
| DEVOPS-03 | Justfile for dev tasks | Single command file for everything | AionUi (16KB Justfile) | 1d |
| DEVOPS-04 | Codecov + Playwright | Coverage metrics + E2E tests | AionUi | 2d |

### Key files to reference in each project

**Open WebUI** (best UI patterns):
- `src/lib/components/OnBoarding.svelte` — Onboarding wizard
- `src/lib/components/NotificationToast.svelte` — Toast system
- `src/lib/components/ChangelogModal.svelte` — Changelog
- `src/lib/shortcuts.ts` — Keyboard shortcuts
- `src/lib/components/chat/` — Chat UI components
- `src/lib/components/common/` — Shared UI components
- `src/lib/stores/` — Svelte stores
- `src/lib/workers/` — Web workers
- `src/lib/i18n/` — Internationalization
- `src/routes/+error.svelte` — Error boundary

**LibreChat** (best architecture):
- `client/src/data-provider/` — API client abstraction
- `client/src/store/` — State management
- `client/src/hooks/` — Custom hooks
- `client/src/a11y/` — Accessibility
- `client/src/mobile.css` — Mobile styles
- `client/src/locales/` — Translations
- `librechat.example.yaml` — Single config file

**Khoj** (best multi-surface):
- `src/khoj/processor/` — Pipeline architecture
- `src/khoj/routers/` — Domain-organized routers
- `src/khoj/routers/research.py` — Research pipeline
- `src/khoj/routers/api_automation.py` — Automation
- `src/khoj/routers/api_phone.py` — Mobile API
- `src/khoj/interface/` — Multi-surface interfaces

**Goose** (best desktop):
- `crates/` — Rust modular architecture
- `ui/` — React/Tauri frontend
- `workflow_recipes/` — Pre-built workflows

**Open WebUI** (best deployment):
- `docker-compose*.yaml` — 10+ compose files
- `docker-run.sh` — One-liner run
- `Dockerfile` — Build
