# KT-UI-MOUNT-01 — Mount the two panels that are already built

**Initiative:** none — deliberately not a Builder manifest, see below
**Owner:** interactive (Codex or an interactive session)
**Depends on:** none
**Base:** `origin/main` `295b92fc33a3f1b93da86f3c6bb5fbb54e367105`
**Findings:** `XCUT-B001`, `XCUT-B002`

## Why this has no manifest
A Builder worktree is a git worktree and `node_modules/` is gitignored, so it is absent, and the runner exposes a Python toolchain but no Node one (`PACKET_STANDARD.md` F9, decision `D-007`). This packet changes only frontend files, so there is no Tier-1 gate Builder could execute. Giving it a manifest would hand Builder work it cannot prove. It goes to a person or to Codex instead.

## What Jacob can do after this
See and manage his todos and his monitors inside Kitty, instead of two finished screens that nothing links to.

## Why this is the next thing
Both components are complete and unreachable.

- `gateway/kitty-chat/src/components/TodoPanel.tsx` implements add, complete, and delete. The gateway already exposes `/todos/add` at `gateway/routes/extended.py:116`. Tasks routes the user to Work instead of mounting it.
- `gateway/kitty-chat/src/components/MonitorPanel.tsx` owns list, add, and remove, and `gateway/kitty-chat/src/lib/queries.ts:406` already has the monitor polling query.

Grepping the whole of `gateway/kitty-chat/src` for either name finds no importer outside the component files themselves. Verified at the base SHA above: both files exist, neither is mounted.

This is the cheapest real value in the slate — no invention, only wiring — which is also why it ranks below the three truthfulness packets.

## Plan
1. Confirm PR #716 does not own the file that routes Tasks. It owns `WorkView.tsx`; if its changed-file list has grown to include the routing file, stop and wait for it to land.
2. Read both components and the view/navigation registry.
3. Mount `TodoPanel` where Tasks currently redirects to Work, and give `MonitorPanel` a reachable destination.
4. Extend `gateway/kitty-chat/tests/` with a test per panel: it renders, and its primary control is enabled and does its thing.
5. Check both at an iPhone-class width — no horizontal overflow, no control under the tab bar.

## Not in scope
Redesigning either panel. Changing the todo or monitor backends. Touching `WorkView.tsx` or `work.ts` — PR #716 owns those. Adding new navigation destinations beyond what these two need.

## Verification
**Tier 1 — mechanical.** Not available to Builder. For a person or Codex: `cd gateway/kitty-chat && npx vitest run tests/TodoPanel.test.tsx tests/MonitorPanel.test.tsx --reporter=dot` and `npx tsc --noEmit`.

**Tier 2 — running app.** A smoke spec under `gateway/kitty-chat/tests/smoke/` reaching both panels and exercising one control on each. The suite runs every spec at both the desktop and iPhone-14 projects, so mobile is covered automatically.

**Tier 3 — product acceptance.** Required (D-008). An independent reviewer adds a todo, completes it, adds a monitor, and removes it, on the running product at both widths.

## Stop condition
If mounting either panel needs a backend change, stop. The finding is that the backends already exist; if that turns out to be false for monitors, that is a different packet.

## Recovery
Frontend-only and fully reversible. If the run fails part-way, revert the working tree and restart at step 2.
