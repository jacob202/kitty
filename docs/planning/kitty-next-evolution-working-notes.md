# kitty next-evolution — working notes (2026-07-07, Fable session)

Running work log for the UX/functionality/design-alignment phase. Not polished docs.
If this session dies, start from "next recommended action" at the bottom.

## what was inspected

- `CLAUDE.md`, `.claude/STATE.md`, `.claude/HANDOFF.md`, `docs/PROJECT_STATUS.md`
- `design-system/PHILOSOPHY.md` (old warm-CRT canon), `design-system/v2-reference/HANDOFF.md` + `KITTY.md` (new crayon/paper canon)
- `gateway/kitty-chat/src/app/globals.css` (already on v2 tokens), `page.tsx` (1103-line monolith, 11 views), component sizes

## important repo facts

- **Branch hazard:** repo is checked out on `claude/packet-018-expert-packs` with a dirty tree — packet 018 is claimed by other models, STATE says **leave alone**. All work this session happens in a git worktree off `main`.
- UI = Next.js in `gateway/kitty-chat/`. `npm run` is broken on this machine (exit 194) → use `make ui-test` / `make ui-build` from repo root (fixed via `.npmrc script-shell=/bin/sh`).
- Views in `page.tsx`: home, chat, tasks, tools, terminal, projects, docs, providers, agents, images, settings. Biggest components: HomeState (932), DocumentsPanel (429), CronPanel (348), TaskPanel (344).
- Recent merges #113/#114 already moved the app onto the v2 crayon look (nav shell, crayon borders, cat eyes, day-theme contrast).
- Jacob is **phone-first** (D12); PWA seam shipped. Kitty runs headless on a broken-screen MacBook Air.
- Push auth is flaky (gh OAuth token rejected for git ops) — commit locally, don't rely on push.

## design canon — the ruling

Two philosophies exist. **v2 wins.**

1. `design-system/PHILOSOPHY.md` — old warm-ink/tabby/Space Grotesk canon. Its *palette/type are superseded*, but its **behavioral laws carry over**: lowercase everywhere, no bubbles/labels/avatars in chat, mono for data not prose, panels always collapsible, mascot = live state gauge, dry deadpan errors, no exclamation marks, motion small and alive.
2. `design-system/v2-reference/` (+ `Design system philosophy reimagine.zip`, same content) — **new canon**: manila paper day / chalkboard night, Bricolage Grotesque display + Hanken Grotesk body + JetBrains Mono data, crayon cat (`kid-cat.svg`, feDisplacementMap seed 7 — never redraw), 94px rail / 268px sidebar / 58px topbar / corner cat. `globals.css` already matches its tokens.

The cat's four states are load-bearing: `._.` idle / `o_o` working / `^_^` done / `:[` broke. State must be wired to *real* system state, never faked.

## diagnosis (current)

The skeleton is right (v2 tokens shipped, nav shell rebuilt). What's missing is **depth and consistency**:

1. **Alignment drift inside components** — v2 landed in globals.css and a few panels; older panels (CronPanel, TaskPanel, JournalPanel, AgentPanel, ImageGenPanel, RightPanel…) still use backward-compat aliases (`--text-dim`, `--surface-mid`, `--cream`) and likely violate lowercase/mono-for-data rules. The compat alias block in globals.css is a standing invitation to drift.
2. **Fonts load from Google CDN** (`@import url(fonts.googleapis.com…)` in globals.css) — a local-first app that blocks first paint on a network fetch and breaks offline/PWA. Should be `next/font` self-hosted.
3. **Chat is the core loop and is shallow** — needs message-level affordances (copy, retry), markdown/tool-call rendering in mono, cat state tied to streaming.
4. **Home is the daily driver** — the cockpit shipped (#113/#114) but tiles need to click through to their panels and reflect the benefit rails (017) + next-step navigator (016) that just landed in the gateway.
5. **Speed** — 1103-line page.tsx renders all view wiring; heavy panels aren't lazy; no measurement of gateway round-trips in UI.

## decisions made

- Work in worktree `.worktrees/fable-ux-phase` off `main`, branch `claude/fable-ux-phase`. Rationale: packet-018 checkout is claimed + dirty.
- UI-only this phase; no gateway python changes (avoids colliding with packet 018 which touches memory_graph/memory_weave).
- Treat v2-reference as design canon; PHILOSOPHY.md behavioral laws still apply.
- Order: alignment sweep → chat deepening → home click-throughs → perf. Alignment first because every later slice builds on the tokens being trustworthy.

## rejected options

- **Big-bang page.tsx refactor** — high blast radius, no user-visible gain this pass. Only extract views if a slice forces it.
- **New features (imagegen v2 / packet 025)** — explicitly next build per STATE, but it needs Jacob's local Draw Things install first; blocked on him, not on code.
- **Rewriting the compat-alias tokens out in one commit** — instead: migrate components to real tokens per-slice, delete aliases only when grep shows zero users.

## prioritized slices

1. **Slice 1 — design alignment sweep + font self-hosting.** Every component on real v2 tokens; lowercase audit; mono-for-data audit; `next/font` for the three families; cat state wired honestly. Definition of done: `grep` for compat aliases returns ~0 in components; `make ui-test` green; screenshots day+night.
2. **Slice 2 — chat deepening.** Message actions (copy/retry), markdown + tool-call mono blocks, streaming → cat `o_o`, error → `:[` with deadpan copy, session search in sidebar.
3. **Slice 3 — home cockpit click-throughs.** Every tile navigates to its panel; deadlines tile from 017 rails; next-step hero from 016.
4. **Slice 4 — perf pass.** Lazy-load panels behind `activeView`, React Query staleTime tuning, measure and display gateway latency honestly (no fake numbers).
5. **Slice 5 — mobile/PWA polish** (phone-first: input bar reachability, rail → bottom tabs on mobile, safe-area insets).

## slice 1 copy-paste prompt

> In ~/Projects/kitty, create/enter worktree `.worktrees/fable-ux-phase` on branch `claude/fable-ux-phase` off origin/main. UI-only work in `gateway/kitty-chat/`. Read `design-system/v2-reference/KITTY.md` and `design-system/PHILOSOPHY.md` first (v2 palette/type is canon; old file's behavioral laws — lowercase, no bubbles, mono-for-data, collapsible panels, cat-as-gauge — still apply).
> 1. Replace the Google Fonts `@import` in `src/app/globals.css` with `next/font/google` (Bricolage Grotesque, Hanken Grotesk, JetBrains Mono) wired in `src/app/layout.tsx` via CSS variables.
> 2. Migrate all components off the backward-compat aliases (`--text*`, `--border*`, `--surface-low/mid/high`, `--cream*`, `--error`, `--warning`, `--font-ui`) onto the real v2 tokens (`--ink`, `--ink-2`, `--line`, `--bg`, `--surface`, `--surface-2`, `--c-red`, `--c-yellow`, `--font-body`). Then delete the alias block from globals.css.
> 3. Audit every component for: capitalized UI copy (lowercase it), body text in mono (move to `--font-body`), data/timestamps/numbers NOT in mono (move to `--font-mono`), exclamation marks in product copy (remove).
> 4. Verify cat states are bound to real state (idle/working/done/broke) — no fake `^_^`.
> Run `make ui-test` and `make ui-build` from repo root (NOT npm run directly). Commit in small logical commits. Do not touch gateway python. Do not redraw the cat.

## slice 2 copy-paste prompt

> In the `claude/fable-ux-phase` worktree of ~/Projects/kitty (UI in `gateway/kitty-chat/`), deepen the chat experience per `design-system/v2-reference/KITTY.md`: flat no-bubble messages stay. Add: (1) hover actions per message — copy, retry-from-here — quiet, hairline, lowercase; (2) markdown rendering for kitty messages with code/tool-call blocks in `--font-mono` on `--surface-2`; (3) bind corner cat to stream lifecycle: `o_o` while streaming, `^_^` brief on completion, `:[` on error with deadpan inline error text ("that broke. trying again" style — no modal, no apology essay); (4) session search input in SessionSidebar filtering grouped history. Keep diffs small, add/extend vitest tests per component, run `make ui-test` and `make ui-build`. No gateway python changes.

## risks / anti-patterns

- **Do not** build on `claude/packet-018-expert-packs` or touch `memory_graph.py`/`memory_weave.py` — claimed by other agents.
- **Do not** redraw kid-cat.svg or "clean up" the wobble — the displacement filter IS the aesthetic.
- **Do not** report done from code inspection — Jacob's global rule: UI fixes verified in the running app (screenshot evidence). `make ui-test` + screenshots minimum.
- Deleting the compat aliases before all users are migrated will silently unstyle things — grep first.
- `npm run` exit-194 trap: always `make ui-test` / `make ui-build` from repo root.

## unresolved questions

- Should the old `design-system/PHILOSOPHY.md` "three systems" section be rewritten to name v2 as canon? (Recommended, small doc PR, not done.)
- Packet 018's dirty tree includes UI files (DocumentsPanel, ProjectsPanel, queries.ts) — merge conflicts possible when both land. Coordinate at PR time.

## work log

- 2026-07-07: recon complete, this file written. Next: create worktree, start Slice 1.
- 2026-07-07: **Slice 1 done** in worktree `.worktrees/fable-ux-phase`, branch `claude/fable-ux-phase` (off main 286f5be):
  - `ad840cc` — fonts self-hosted via next/font (Google CDN import removed from globals.css + layout.tsx); all 24 components migrated off compat aliases; alias block deleted.
  - `bf76538` — found ~90 usages of *undefined* old-palette vars (`--teal --mint --orange --recessed --panel --indigo --pink --tertiary…`) silently rendering unset → mapped to v2 tokens. TerminalStrip was **fabricating random log lines** ("Gateway Log" theatre) → added `GET /logs/tail` (gateway/routes/logs.py, whitelist, bounded; registered in register.py; tests/test_logs_route.py 4 passed) and rewired TerminalStrip to it with deadpan error state. Lowercase copy sweep across ~15 components. Deleted dead lib/dashboardMock.ts + its test.
  - Verified: `make ui-test` 91/91 passed, `make ui-build` green, logs-route pytest green. Full pytest suite running in background at slice-1 close.
  - Worktree note: node_modules is an APFS clone (`cp -Rc`) of the main checkout's — symlink breaks Turbopack.
- Next: Slice 2 (chat deepening — message actions, markdown/tool-call mono blocks, cat bound to stream lifecycle, session search).
- 2026-07-07 (later): **Slice 2 done + verified live.** Chat already had markdown/code-copy/typing-dots/sidebar-search (deeper than diagnosed — good). What was actually missing and got built:
  - `fa40398` — extracted `runStream` from `handleSend`; added `handleRetry` (drops trailing assistant msg, re-streams same history); cat now hits all four canon states honestly (`o_o` streaming, `^_^` 2.5s on done, `:[` on error until next send); quiet hover copy/retry action row on finished kitty messages; tests/ChatMessage.test.tsx.
  - `6c94a4f` — TopBar had two *static* "^_^ done" / ":[ broke" buttons faking state next to the real StateBadge — deleted (KITTY.md: state faces must mean something).
  - **Live verification (dev server, gateway down):** app renders v2 manila skin; fonts confirmed self-hosted (`Hanken Grotesk` computed, 0 external font requests); sent a chat message → ⚠ error bubble with the real cause, topbar badge flips to `broke`, message badge `:[`, corner cat desaturates; retry re-streamed and honestly failed again. Screenshots taken in-session.
  - Full pytest: 1310 passed / 3 failed — all 3 are missing-module env failures (mem0 ×2 in test_doctor, google.auth in test_mail_connector) unrelated to this diff; targeted re-runs confirm. UI: 95/95, build green.
  - Fixed stale `~/.claude/launch.json` (pointed at nonexistent `~/Projects/kitty-chat`, port 4000 note: kitty-chat dev script hardcodes `-p 4000`).

## remaining slices (not started)

- Slice 3 — home cockpit click-throughs (tiles navigate to panels; deadlines from 017; next-step hero from 016).
- Slice 4 — perf pass (lazy-load heavy panels behind activeView, React Query staleTime, honest latency display).
- Slice 5 — mobile/PWA polish (phone-first: bottom tabs on mobile, safe-area insets).
- Doc PR: mark v2-reference as canon inside design-system/PHILOSOPHY.md ("three systems" section is stale).

## next recommended action if session ends

Branch `claude/fable-ux-phase` in `.worktrees/fable-ux-phase` has 4 commits ready for PR (`ad840cc bf76538 fa40398 6c94a4f`). Push (auth permitting) and open the PR, then pick up **Slice 3** using the sketch above. Merge-conflict watch: packet-018's dirty tree touches DocumentsPanel/ProjectsPanel/queries.ts.
