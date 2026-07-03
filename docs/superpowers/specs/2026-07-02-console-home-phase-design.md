# Phase plan — Console Home (packet 004) + ground repair

**Date:** 2026-07-02 · **Status:** GO · **Feature spec:** `docs/packets/004-state-home.md` (already complete — this doc is the execution plan around it, not a rewrite)

## Stage 1 — Approaches

- **A (chosen): Packet 004 — console home**, with a step-0 toolchain repair and
  the §16.2 mail decision queued to Jacob in parallel. P1–P3 of the spine are
  shipped; P4 is the only piece left. OPERATOR_STRATEGY §19 names the
  alternative failure mode exactly: "another lap of internal polish instead of
  the spine."
- **B: Packet 008 remainder (expert retrieval).** Deepens knowledge, but the
  front door stays a chat box — the §19 trap.
- **C: Packet 007 (delegation generator).** High leverage, but its output
  (proposed packets awaiting approval) has no surface until the console's
  "Needs you" queue exists. Correct order is 004 → 007.

## Stage 2 — Design (execution wrapper around packet 004)

### Step 0 — ground repair (acceptance criteria are unverifiable without it)

Found during 2026-07-02 planning preflight:

1. **`npm run <script>` is broken in this repo** — exits 194 silently
   (node 26.4.0 / npm 11.17.0; works in a clean dir, fails here; not the
   sandbox, not NODE_OPTIONS, not npmrc, not `Icon\r` in the walk path).
   Workarounds proven to work:
   - tests: `./node_modules/.bin/vitest run`
   - build: `node node_modules/next/dist/bin/next build`
     Either root-cause it or codify the direct invocations (Makefile targets)
     so agents stop tripping on it.
2. **6 UI tests already fail** (`SessionSidebar` ×5, `TopBar` offline
   indicator ×1) — invisible until now because CI never runs kitty-chat tests
   and `npm run` was broken locally. Fix before 004 starts.
3. **Add a kitty-chat CI job** (vitest + next build). Today's incident — #70
   merged red and broke main — is what happens when a gate doesn't exist.

### Step 1 — hygiene batch (~30 min, needs Jacob's deletion sign-off)

Prune 8 merged worktrees + branches · delete `tests/test_llm_client_alt_ua.py`,
`tests/fakes/`, `.kitty/swarm-status.json`, orphaned `data/loops.db` · commit
the workflow configs (`.pre-commit-config.yaml`, `.prettierrc`,
`.prettierignore`, `dependabot.yml`, `eslint.config.mjs`) · move `hermes-webui/`
out of the repo · push `backup-local-main-0628` to origin.

### Step 2 — build 004 v1 (one branch, one PR)

Per the packet: `HomeState.tsx` default view — **What changed**
(`/state/changes`) · **Needs you** (`/actions?status=proposed` with
approve/reject live — 003 shipped, so the buttons are wired from day one, not
deferred) · **Open loops** · **Today** · **Capture** · chat via the existing
CommandPalette drawer. `LoopWatch`/`InsightFeed` bind to the now-real `/loops`

- `/insights` (post-#79) or don't render.

### Step 3 — screenshot review with Jacob (packet requires it), polish, merge.

### Parallel — decision Jacob owes: §16.2 mail path

Apple Mail via AppleScript (fully local, brittle, Mac-only — matches the
calendar precedent) vs Gmail API read-only (robust, Google OAuth + cloud in
the loop). Read-only either way. Answering unblocks packet 005.

### Scope

**In:** packet 004 exact scope + step 0 repairs. **Out:** chat redesign,
settings UI, mobile/PWA rework, drawer-vs-split-pane revisit, packets 007/008
(they're the phase after).

## Stage 3 — Grill (gaps found, fixes applied)

1. **Weakest assumption: the console has data on day one.** Signals only
   started flowing today (#77). If `/state/changes` is near-empty, the console
   feels dead and Jacob bounces off his own product. Mitigation: before the
   layout review, run the brief scheduler + web_monitor + triage against real
   inbox data; "Today" (calendar/todos) carries the first screen if signals
   are thin.
2. **Toolchain**: acceptance unverifiable until step 0 — which is why it's
   step 0, not a footnote.
3. **Approve/reject races**: packet already covers (disable on submit,
   refetch after).
4. **Gateway-down edge**: every card must show an honest error state, not a
   spinner — test it explicitly with the gateway stopped.
5. **Forgot-in-a-rush check**: changing the default route can break the PWA
   `start_url` / cached shell for the installed app. Verify manifest + service
   worker after the swap.
6. **Simpler version that still delivers**: v0 = Needs you + Capture + chat
   drawer only. If 004 drags, ship v0 first — it's the half that carries verbs.
7. The two Python test-isolation leaks (`test_action_queue`,
   `test_state_composer`) are unrelated to 004 — hygiene list, not this phase.

## Stage 4 — Zoom out

- Matches `AGENT_HANDOFF.md` (004 named next), OPERATOR_STRATEGY §20 (P4 =
  last spine piece). Nothing touches the §18 do-not-build list.
- Smallest shippable slice: v0 above.
- YAGNI cuts: no new gateway endpoints (packet forbids — split a packet if a
  read gap appears), no design-token changes, no mobile work.
- **GO.** First action: step 0 — fix the 6 UI tests and codify the build/test
  invocations, then branch `feat/console-home`.
