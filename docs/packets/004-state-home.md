# Packet 004 — State home surface

- **Status:** ready — 001–003 all shipped, §16.1 decided. **Do packet 014
  first** (the UI test suite and CI gate this packet's acceptance criteria
  depend on are broken until then). Execution plan:
  `docs/superpowers/specs/2026-07-02-console-home-phase-design.md` (GO).
- **Best executor:** Claude Code (UI + design-system taste).
- **Purpose:** Make the front door show the operating layer instead of a chat
  box. The home screen answers "what changed, what needs me, what's open"
  the instant it opens.

## Decision §16.1 (resolved 2026-07-02) — home = state console

Home is the **state console**. Chat is demoted to a **summonable drawer**
(existing CommandPalette / drawer), always one tap away, never the main event.
This follows directly from D9: chat is one interface to the operating layer,
not the product.

The load-bearing constraint, and the reason this is a console and not a
dashboard: **every surface must carry a verb, not just a number.** A panel that
only displays is the failure mode D9 warns about — you glance once and never
return. "Needs you" outranks every visualization. If a section can't offer an
action, it earns its place only as honest context (Today, What changed), never
as filler.

**Phasing (updated 2026-07-03 — 003 shipped, so no split needed):**

- **v1 (this packet):** console home wired to `/state/now` and
  `/state/changes`, "Needs you" bound to `/actions?status=proposed` with
  **approve/reject live from day one**, the `needs_jacob` triage bucket as a
  real queue, capture input, chat in the drawer.
- **If it drags, v0 first:** Needs you + Capture + chat drawer only — the
  half that carries verbs (per the phase plan's grill).
- Revisit drawer-vs-split-pane for chat only after v1 exists to judge against.

## Exact scope (as specified in OPERATOR_STRATEGY §15 P4)

- New `HomeState.tsx` as the default view in `gateway/kitty-chat`, composed of:
  - **What changed** — from `GET /state/changes`.
  - **Needs you** — action cards from `GET /actions?status=proposed` with
    approve/reject wired (post-003); plus `needs_jacob` triage items.
  - **Open loops** — untriaged count from triage, proposed actions,
    `needs_jacob` items.
  - **Today** — calendar / todos, reusing existing panels' fetch logic.
  - **Capture** — the existing quick-capture input.
  - **Chat** — via the existing CommandPalette / drawer.
- Remove fake-data rendering: `LoopWatch` and `InsightFeed` either bind to a
  real endpoint or do not render at all (D9: no panel serves fabricated data).
- Keep the v2 design tokens; cat state is driven by the queue + doctor, not
  invented.

## Files likely touched

- `src/app/page.tsx`, new `src/components/HomeState.tsx` + card components,
  demotion/removal of `DashboardHome.tsx` wiring, UI tests.

## Files not to touch

- Gateway Python — **except** a tiny read-endpoint gap; if one appears, stop
  and split a packet rather than growing this one.
- Design tokens.
- Chat internals (redesigning chat is out of scope — this packet only moves
  it into a drawer).

## Acceptance criteria

- `make ui-test` and `make ui-build` green (`npm run` exits 194 on Jacob's
  machine — the Makefile targets from packet 014 are the invocation path).
- Home renders with the gateway up; shows honest empty / error states with the
  gateway down (no spinners-forever, no fabricated rows).
- Zero hardcoded data anywhere in the view.
- "Needs you" reads clearly enough to approve an action without opening chat.

## Verification

```bash
make ui-test && make ui-build
# manual: ./kitty up, open the app, walk What changed / Needs you / capture
# manual: stop the gateway, reload — every card must show an honest error
#         state, no spinners-forever
# manual: verify PWA manifest start_url + cached shell still resolve after
#         the default-route swap (phase plan grill #5)
```

## Risks / rollback

- **Design churn:** one review round with Jacob on a screenshot before polish.
- **Approve-button races:** disable on submit, refetch after.
- **Rollback:** revert PR; the old `DashboardHome` path is restorable from git.

## Too broad if

It redesigns chat, adds a settings UI, or touches mobile PWA behaviour.

## Jacob reviews

The layout (one screenshot approval) and that "Needs you" reads clearly enough
to approve actions without opening chat.
