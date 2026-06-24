# UI Development Swarm — Plan

## Mission

Transform Kitty from a functional dashboard‑shell into a polished, delightful,
personal AI companion that Jacob reaches for daily. The swarm is a team of
autonomous AI agents working in parallel, each owning a slice of the surface,
coordinated through a single orchestrator.

---

## 0. Orchestrator Task Manifest & Gates

Every task lives in a machine‑readable manifest (`tasks.yaml`) that defines
dependencies, file boundaries, acceptance criteria, and completion gates. This
removes ambiguity for agents and enables automated progress tracking.

**Pre‑merge gates (applied to every agent diff):**
1. `npm run lint` (zero new errors)
2. `npm run typecheck` (tsc‑‑noEmit)
3. Unit tests for changed files pass
4. Visual snapshot diff against base (if UI changed) — *orchestrator reviews
   automatically; only rises to human if change > threshold*

The orchestrator reviews the **summary**, test report, and visual diff only —
not every line of code.

---

## 1. Preconditions (must ship before swarm launches)

These are foundational bugs/gaps that would block or waste agent work if left
unfixed. Each agent can assume these are done before they start.

| # | Item | Why it blocks | Est. effort | Resolution |
|---|---|---|---|---|
| P1 | Chat persistence — save/load chats from backend | Without it, every refresh loses state; message features built on sand | 1 session | Fully integrated & tested; not a mock |
| P2 | Backend `GET /chats` + `POST /chats/{id}/messages` | Required by P1; currently browser‑only | 1 session | Landed and verifiable with integration tests |
| P3 | Fix `TopBar.tsx` duplicate span | Visual bug that would ship | 5 min | One‑line fix, applied immediately |
| P4 | Clean 20 LSP diagnostics in `gateway/` (clerk.py, codebase_search.py) | Noise reduces agent signal and wastes time diagnosing false positives | 1 session | Scripted lint fix + manual verification; ensure it's actual errors, not false positives |

*All preconditions are completed and verified before any stream agent begins.*

---

## 2. Swarm Architecture

### 2.1 Agent Roles

The swarm runs N parallel agents, each with a focused brief. An orchestrator
agent manages the DAG, reviews output, and escalates conflicts to Jacob.

```
┌─────────────────────────────────────────────────────┐
│                  Orchestrator                        │
│  (DAG tracking, manifest, visual diff gate)         │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│  Stream  │  Stream  │  Stream  │  Stream  │  Stream │
│    A     │    B     │    C     │    D     │    E    │
│  Chat UX │  Home    │  Info    │  Infra   │  Agent  │
│          │  Dash    │  Panels  │  Quality │  UX     │
└──────────┴──────────┴──────────┴──────────┴─────────┘
```

### 2.2 Coordination Protocol

1. **Orchestrator** dispatches next ready task with contract (props/types) and
   the exact acceptance criteria from the manifest.
2. **Stream agent** works in its own git worktree, uses the shared design token
   file (`globals.css`) and component library, never writes into another
   stream's directory without a handoff.
3. **Pre‑review gate**: agent runs lint, typecheck, tests, and generates visual
   snapshots. Only passes diff to orchestrator if all pass.
4. **Orchestrator** evaluates visual diff and test summary. If acceptable,
   merges into the integration branch. Any conflict with already‑merged work
   triggers a rebase by the agent before merge.
5. **Escalation**: only design disagreements or ambiguous requirements rise to
   Jacob. All code conflicts are resolved by the orchestrator.
6. **Scope creep rule**: any addition not in the manifest must be presented as a
   **separate prototype branch** (or commented‑out alternative). The orchestrator
   may approve small, strictly‑in‑spirit additions; everything else is queued for
   a future phase.

### 2.3 Communication Surface

All agents share:

- **`src/lib/types.ts`** — type contracts
- **`src/app/globals.css`** — design tokens (read only)
- **`src/lib/gateway.ts`** — API client
- **`src/lib/queries.ts`** — hooks

No agent writes to another's component directory without an orchestrator‑mediated
handoff.

---

## 3. Phases & Streams

### Phase 1 — Core Experience (Streams A, B, C in parallel)

#### Stream A — Chat Delight

| Task | Detail | Test criterion |
|---|---|---|
| A1 | Message editing & inline deletion with undo toast | Edit via pencil icon; delete replaces with "message deleted" placeholder and undo snackbar |
| A2 | Message copy button (hover on assistant messages) | Copies plain text to clipboard |
| A3 | Code block copy button | Icon on each `<pre><code>`, copies only code |
| A4 | Streaming indicator refinement | Smooth cursor + live token/word count; fallback text if count unavailable |
| A5 | Empty‑state illustration + suggested prompts | Cute illustration, 3 contextual prompts (e.g., "Tell me a joke", "Summarise today") |
| A6 | Message grouping (consecutive same‑role) | Hides redundant avatar/name |
| A7 | Scroll‑to‑bottom FAB | Appears >200px from bottom |
| A8 | Timestamps on hover | Tooltip with localised time |
| A9 | **Error state**: message send failure | Inline error banner with retry; dead‑letter indication on the message |
| A10 | **Loading skeleton** for initial message load | Shimmer placeholders matching message bubble shape |

#### Stream B — Dashboard Stickiness

| Task | Detail | Test criterion |
|---|---|---|
| B1 | Recent chats with last‑message preview | Last 5 chats, snippet, timestamp |
| B2 | Quick‑action cards: New Chat, Continue Last, Today's Summary, Run Tasks | Accessible above the fold; each navigates correctly |
| B3 | Weather widget polish (icon, condition, brief forecast) | On‑brand icons; **empty/error state**: "Weather unavailable" with cloud icon if API fails |
| B4 | Empty states for every card (todos, loops, insights) | Friendly illustration + micro‑CTA |
| B5 | Rotating time‑based greetings | Variety across sessions; stored preference to avoid repetition |
| B6 | **Skeleton loading** for async cards | Not spinners; layout‑matching pulse shapes |

#### Stream C — Information Panels

| Task | Detail | Test criterion |
|---|---|---|
| C1 | RightPanel collapse/expand (shortcut `[` or `]`) | Animated slide; main content fills space |
| C2 | Session search sidebar (filter by title) | Real‑time text filtering |
| C3 | Session context menu (rename, delete, export) | Right‑click or `…` menu; delete with confirmation |
| C4 | RightPanel tab bar (Today / Session / Search) | Tabs remember last‑used per session |
| C5 | Session stats: message count, duration, token count | Show "— token count not yet available" fallback; backend dep noted |
| C6 | **Empty state** for no search results | "No chats found" with suggestion to create a new one |

---

### Phase 2 — Quality & Agent UX

#### Stream D — Infrastructure & Quality (runs after Phase 1 merge)

| Task | Detail | Test criterion |
|---|---|---|
| D1 | Extract `page.tsx` logic into `useChat`, `useSearch`, `useAppState` hooks | `page.tsx` <150 lines; each hook tested |
| D2 | Convert inline hover handlers to Tailwind `hover:` utilities | Zero `onMouseEnter/Leave` on presentational components |
| D3 | Unit tests — >60% coverage on `/components` | Vitest, testing state and rendering |
| D4 | Keyboard shortcut system + `?` cheat sheet | Register shortcuts declaratively; overlay accessible |
| D5 | Accessibility audit — focus, aria, roles | Tab navigation flows, screen reader announces changes |
| D6 | **Visual regression testing** — snapshot comparisons in CI | Playwright screenshots of key views; threshold‑based failure |

#### Stream E — Agent UX (parallel with Stream D if backend agents live)

| Task | Detail | Test criterion |
|---|---|---|
| E1 | AgentPanel with status indicators (idle/thinking/done/error) | Per‑agent card with icon, last action, error message |
| E2 | ImageGenPanel (inline preview, lightbox) | Mock/demo images if no live generation |
| E3 | JournalPanel search + date nav | Filter by text or date range |
| E4 | Task list drag‑to‑reorder | Drag handle, visual feedback, persistence |
| E5 | TerminalStrip follow mode | Auto‑scroll, pause on manual scroll, "Follow" button |

---

### Phase 3 — Polish & Delight (single stream F)

| Task | Detail | Test criterion |
|---|---|---|
| F1 | View transitions (Framer Motion crossfade/slide 200ms) | Consistent across all navigation |
| F2 | Kitty mood avatar — idle/thinking/success/confused/searching | SVG swaps driven by `KittyMood` state |
| F3 | Toast notification system | Top‑right, auto‑dismiss 4s, stacked, accessible |
| F4 | Loading skeletons for all async components | Global pattern from B6 and A10; consistent shimmer |
| F5 | Micro‑interactions (press, hover scale, focus ring) | 100‑200ms feedback, consistent Tailwind config |
| F6 | **Global error boundary** with friendly fallback UI | Graceful recovery, "Something went wrong" with cute illustration and reload |
| F7 | **Design token lint** — enforce no raw colors/spacing outside config | Stylelint rule or CI check to prevent visual drift |
| F8 | **What's new changelog overlay** (triggered after version updates) | Shows recent changes on first load after version bump |

---

## 4. Companion Quality Rubric

After **every phase**, Jacob rates three questions 1–5. This replaces the "all
tests pass" dopamine hit with actual product signal.

| Question | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Does this make Kitty feel smarter? | Dumber | — | Neutral | — | Smarter |
| Does this make Kitty feel more present? | Distant | — | Neutral | — | More present |
| Would you miss this if it went away? | Not at all | — | Neutral | — | Very much |

Each task in the manifest also carries a `companion_impact` field:

- **none** — pure infra/test (e.g., D6 visual regression)
- **indirect** — enables delight but doesn't deliver it directly (e.g., D4 keyboard shortcuts)
- **direct** — user-facing feel improvement (e.g., A5 empty state, F2 mood avatar)

Tasks with `direct` impact are flagged in the orchestrator's phase summary.

---

## 5. Measurement & Feedback

| Metric | Method | Purpose |
|---|---|---|
| Test pass rate | `npm test` in CI | Regression guard |
| Type safety | `tsc --noEmit` | Ensure refactors don't break contracts |
| Visual consistency | Snapshot diff (Playwright) | Catch unintended UI breakage |
| Bundle size & load | Lighthouse, Next build output | Perf regressions |
| Accessibility score | axe-core automated audit | Baseline a11y |
| Coverage | `vitest --coverage` | Track what's tested |

**Feedback cadence:**

```
Per-agent:  auto-gates + orchestrator visual review → merge
Per-phase:  full integration test → Jacob reviews summary + screenshots + rubric
Per-stream: agent writes SUMMARY.md in worktree with what was done and why
```

**What Jacob reviews at phase boundaries:**

1. **Diff summary** — what changed, file counts, insertions/deletions
2. **Before/after screenshots** (or link to running dev server)
3. **Test report** — pass counts, coverage delta
4. **Companion rubric** — Jacob's 1–5 ratings on smarter/present/missed
5. **One question** — "What should the next phase focus on?"

---

## 6. Risk Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Agents overwrite each other's work | Medium | Worktree isolation per stream + orchestrator-controlled merge |
| Low-quality UI | Medium | Pre-merge lint/type/snapshot gates; orchestrator reviews only visual diffs |
| Scope creep — agents add features not in plan | High | Manifest is strict; extra ideas go to a `proposals/` branch |
| Inline style explosion continues | High | Stream D enforces CSS hover conversion + stylelint rule (F7) |
| Backend API changes break frontend | Low | Precondition P1-P2 must be live and tested; contract tests in gateway |
| Jacob gets overwhelmed reviewing | Medium | Phase-boundary reviews only; orchestrator batches results |
| Visual disjointedness (Franken-UI) | Medium | Shared design tokens and component library enforced by lint (F7); orchestrator design-pass checklist |
| Missing backend data breaks UI | Low | Each task has explicit fallback UI (e.g., "token count unavailable", "Weather unavailable") |

---

## 7. Execution Flow

```
Phase 0: Preconditions (1 session)
    │ P1-P4
    ▼
Phase 1: Core UX — Streams A, B, C parallel (3 streams)
    │ A1-A10, B1-B6, C1-C6
    ▼ merge into integration, Jacob sign-off + rubric
Phase 2: Quality + Agent UX — Stream D (after Phase 1), Stream E (parallel if live)
    │ D1-D6, E1-E5
    ▼
Phase 3: Polish — Stream F (single stream, high touch)
    │ F1-F8
```

### Stream count guidelines

- **Phase 1**: 3 streams (A, B, C) — mostly independent, low conflict risk
- **Phase 2**: 2 streams (D, E) — D touches many files, better to isolate
- **Phase 3**: 1 stream (F) — all touch presentation, conflicts likely

---

## 8. Open Questions / Gaps (known)

These are gaps surfaced by meta-analysis that are **out of scope** for the UI
swarm but flagged for future initiatives:

- **Proactivity**: Kitty should occasionally do something unprompted (welcome
  back, flag a pattern, suggest a break). Requires backend scheduler + memory
  recall. → *Future: "Kitty Personality Pack" initiative*
- **Onboarding**: First-time experience for new users. Low ROI for single-user
  app, but a "what's new" overlay (F8) covers the update case.
- **Light/dark mode**: Full theme refactor across 30+ components. Not worth the
  churn until the UI is stable post-Phase 3.
- **In-app feedback**: No mechanism to report bugs or suggest ideas from within
  the app. → *Add as F9 if Phase 3 budget allows.*
- **Offline indicator**: Missing from the plan. → *Fold into C1 (RightPanel)
  as a network status dot.*
- **Rate-limiting feedback**: What happens when messages are sent too fast? →
  *Add to A9 error states.*

---

## 9. Next Steps

To launch, the orchestrator needs:

1. [x] Plan structure and priorities — signed off
2. [ ] Day-budget per phase (e.g., "Phase 1: 2 days, Phase 2: 2 days, Phase 3: 1 day")
3. [ ] UI inspirations — apps or sites whose feel you want to match

Once day-budget is set, I'll seed the orchestrator with the full manifest and
launch Streams A, B, and C in parallel.
