# Fix Kitty UI Wiring

## Goal

Make a clean Kitty startup readable and truthful, keep transient gateway latency from turning connected features into permanent offline/empty states, and prove the primary chat path plus navigation surfaces against the live local stack.

## Files

- [MOD] `gateway/kitty-chat/src/app/globals.css` — stop the day-theme `:root` defaults from overriding the cosmic theme.
- [MOD] `gateway/kitty-chat/src/lib/gateway.ts` — give gateway reads a realistic shared timeout and preserve explicit errors at the feature boundary.
- [MOD] `gateway/kitty-chat/src/lib/queries.ts` — retry/refetch bootstrap queries so one cold-start timeout does not pin the UI offline.
- [MOD] `gateway/kitty-chat/src/components/ImageGenPanel.tsx` — make renderer loading/offline state explicit and actionable.
- [MOD] `gateway/kitty-chat/tests/gatewayIntegration.test.tsx` — cover the live-model timeout/error contract used by the top bar.
- [MOD] `gateway/kitty-chat/tests/HomeState.test.tsx` — cover truthful gateway recovery states where the home cockpit depends on them.
- [MOD] `gateway/kitty-chat/tests/ImageGenPanel.test.tsx` — cover the offline retry affordance.

## Steps

- [x] Fix the theme cascade in `globals.css` so `cosmic`, `day`, and `night` each own their variables without selector-order bleed.
- [x] Raise the shared gateway read timeout from the observed 2.5s ceiling and remove the 1.5s brief-specific false-offline threshold; keep abort/error text visible.
- [x] Add bounded retry/refetch behavior to the model, brief, todo, deadline, and state queries so transient proxy cold starts recover without a manual reload.
- [x] Add regression coverage for live model responses, timeout/error reporting, the home cockpit's connected/offline distinction, and Image Lab status loading.
- [x] Re-run the live app from a clean frontend process, smoke chat send/persist, and exercise projects, docs, providers, agents, image lab, and settings.

## Verification

- `npm test -- --run --maxWorkers=1` — all frontend tests pass (106 tests).
- `npm run build` — production frontend build passes.
- `./kitty status` and `./kitty doctor --json` — gateway/LiteLLM remain healthy.
- Browser smoke: clean load has readable contrast; health settles to live; `Reply with exactly: PONG` produces and persists a response; each visible rail surface renders its own panel without `coming soon`.
- Remaining failures are recorded as explicit feature blockers with the exact route/component, not converted into empty fallback data.

## Approach

This is a walking skeleton: repair the shared CSS and gateway seams first because every panel depends on them. A broad panel rewrite before those seams are stable would create noisy diffs and hide the actual integration failures.
