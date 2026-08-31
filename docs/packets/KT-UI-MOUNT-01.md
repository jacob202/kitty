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

**This is not pure wiring. Two defects make both panels non-functional as they stand**, and mounting them unchanged would ship exactly the read-only-dashboard failure Jacob has already ruled out.

- **Monitors cannot be removed.** The `watches` table's primary key is `id` (`gateway/web_monitor.py:48`) and `list_watches()` returns `SELECT *`, so every row carries `id`. `MonitorPanel.tsx:41` keys rows on `m.watch_id` and line 50 sends `m.watch_id` to the delete mutation. Every existing monitor renders with an undefined key and every remove targets `undefined`.
- **Completing a todo is labelled "retry".** `TodoPanel.tsx:41` passes the completion mutation through `WorkCard`'s `onRetry` prop, and `WorkCard.tsx:194` renders that prop as a rotate icon labelled `retry`. There is no control on the screen that says it completes anything.

Both must be fixed in this packet. It is still the cheapest real value in the slate, but it is not free, which is part of why it ranks below the three truthfulness packets.

## Plan
1. Confirm PR #716 does not own the file that routes Tasks. It owns `WorkView.tsx`; if its changed-file list has grown to include the routing file, stop and wait for it to land. (As of 2026-08-31 #716 is closed unmerged, so this is likely already clear.)
2. Read both components, `WorkCard.tsx`, and the view/navigation registry.
3. Fix the monitor identifier so rows key on and delete by the identifier the gateway actually returns.
4. Give completion its own control with an accessible label that says "complete", rather than borrowing `onRetry`.
5. Mount `TodoPanel` where Tasks currently redirects to Work, and give `MonitorPanel` a reachable destination.
6. Extend `gateway/kitty-chat/tests/` with a test per panel: it renders; removing a monitor calls the delete endpoint with the real identifier; the completion control exposes an accessible name containing "complete" and fires the completion mutation.
7. Check both at an iPhone-class width — no horizontal overflow, no control under the tab bar.

## Not in scope
Redesigning either panel beyond the two defects above. Changing the todo or monitor backends — the identifier fix belongs on the frontend, which is where the mismatch is. Touching `WorkView.tsx` or `work.ts`. Adding new navigation destinations beyond what these two need.

## Verification
**Tier 1 — mechanical.** Not available to Builder. For a person or Codex: `cd gateway/kitty-chat && npx vitest run tests/TodoPanel.test.tsx tests/MonitorPanel.test.tsx --reporter=dot` and `npx tsc --noEmit`.

**Tier 2 — running app.** A smoke spec under `gateway/kitty-chat/tests/smoke/` reaching both panels and exercising one control on each. The suite runs every spec at both the desktop and iPhone-14 projects, so mobile is covered automatically.

**Tier 3 — product acceptance.** Required (D-008). An independent reviewer adds a todo, completes it, adds a monitor, and removes it, on the running product at both widths.

## Stop condition
If mounting either panel needs a backend change, stop. The finding is that the backends already exist; if that turns out to be false for monitors, that is a different packet.

## Recovery
Frontend-only and fully reversible. If the run fails part-way, revert the working tree and restart at step 2.
