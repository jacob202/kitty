# Kitty Dashboard Shell Implementation Brief

## Mission

Build Kitty as an alternate dashboard UI shell for Open WebUI capabilities. Do
not theme Open WebUI. Do not fork or rewrite Open WebUI. Preserve normal Open
WebUI access and make rollback easy.

Use this Orca workspace:

```bash
/Users/jacobbrizinski/orca/workspaces/kitty/Nautilus
```

## Current Runtime Facts

- Kitty Chat is a separate Next.js app in `gateway/kitty-chat`.
- `npm run dev` serves Kitty Chat on port `4000`.
- Open WebUI is a pip/venv-launched service, not a local Open WebUI source
  checkout.
- Live Open WebUI was verified at `http://127.0.0.1:3001/health`.
- Live Kitty Gateway was verified at `http://127.0.0.1:8000/health`.
- `src/app/proxy/[...path]/route.ts` defaults to `http://127.0.0.1:8000`
  (the gateway's port); override with `KITTY_GATEWAY_URL` if the gateway
  runs elsewhere.

## Preflight Status

Dependencies were installed with:

```bash
npm ci
```

Verification now passes:

```bash
npm test
npm run build
```

The only setup patch made before handoff was excluding Vitest config/tests from
the production Next TypeScript build in `tsconfig.json`.

## First Implementation Scope

Use mock data only. Do not add real Gmail, calendar, memory, plugin, function,
pipeline, or server-side Open WebUI integrations.

Replace the chat-first empty state with a dashboard-first home screen. The chat
composer remains as the Command surface, but it is not the product center.

Required dashboard zones:

- Now
- Continue
- Signals
- Command

Required hero modules:

- Last Session + Suggested Fix
- Reality Check
- Insights + Fixes
- Context Kitty Found
- Agent Console / Command

Reality Check must separate:

- Life Priority
- Coding Session Priority
- Chat Session Priority

Reality Check tone modes:

- Gentle
- Balanced
- Blunt
- Auto

Auto should explain its choice and default to Balanced unless mock state clearly
supports Gentle or Blunt.

## Visual Direction

Use Executive Indigo:

- charcoal canvas
- indigo/purple structure
- yellow data highlights
- green success
- teal interactions
- orange only for Kitty identity

Use the existing mascot assets as small identity/state badges:

- `public/mascots/kitty-mission.png` is 1024 x 1024.
- `public/mascots/kitty-states.png` is 2048 x 2048.
- `public/mascots/kitty-states-b.png` is 2048 x 2048.

Do not make Kitty large. The mascot is a state indicator, not the layout.

## Suggested Files

- `src/lib/dashboardMock.ts` for mock data and types.
- `src/components/BriefPanel.tsx` for the dashboard home refactor.
- `src/app/page.tsx` only as needed to pass dashboard props/state.
- `src/app/globals.css` for shared design tokens.
- `src/components/MoodAvatar.tsx` if adding the full state list.

## Acceptance Criteria

- Normal Open WebUI remains available.
- Kitty Dashboard runs separately on port `4000`.
- Dashboard shows Now / Continue / Signals / Command.
- Last Session + Suggested Fix is visible above the fold.
- Reality Check is a hero card with Life / Coding / Chat priorities.
- Tone toggle works with Gentle / Balanced / Blunt / Auto.
- Static and dynamic Kitty states are present and small.
- Terminal styling is contained to Agent Console / code / logs.
- No real integrations or Open WebUI plugins are added.
- `npm test` passes.
- `npm run build` passes.
