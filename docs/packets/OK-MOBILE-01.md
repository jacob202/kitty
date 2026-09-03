# OK-MOBILE-01 — iPhone Is a First-Class Kitty Client

**Status:** draft candidate; not activated
**Roadmap phase:** 4 — reliability/recovery

## Mission
Make the real iPhone/Tailnet path good enough that Jacob can use Kitty away from the Mac without weakening the local security boundary or accepting a squeezed desktop UI.

## Depends on
- `KH-RUNTIME-01` for exact running build truth.
- `KH-REMOTE-01` for authenticated Tailnet/proxy access.
- Primary surface functionality should be substantially complete before final acceptance.

## Product acceptance moment
From the iPhone on the supported Tailnet path, open Kitty, Chat, capture/attach something, navigate Home/Work/Projects/Library/Image Lab/Automations/Settings, perform representative primary actions, reload/return later, and recover from one Gateway/provider-unavailable condition without desktop-only instructions.

## Required behavior
- Supported remote URL/auth path is explicit and does not bind private Gateway secrets to an unauthenticated LAN surface.
- Bottom navigation/composer/sheets/dialogs never obscure primary controls; no document-level horizontal overflow.
- Touch targets remain >=44px for persistent primary controls.
- File/photo attachment/capture path works from iOS where the browser supports it.
- Keyboard opening/closing and viewport resizing do not strand the composer/action bar.
- Reload/background-return preserves the state that claims continuity.
- Degraded Gateway/provider/indexing states remain actionable without “run this terminal command” as the primary user message.
- PWA/home-screen behavior is only claimed if actually verified on current iOS; otherwise use the supported browser path honestly.

## Verification
**Tier 1:** mobile layout/component/smoke regressions; no desktop-only branch silently bypasses mobile actions.

**Tier 2:** real iPhone acceptance over the supported Tailnet route plus iPhone-class Playwright coverage for deterministic layout/failure paths.

**Tier 3:** independent reviewer or Jacob completes the defined real-device journey and records exact candidate/runtime source; no claim from emulator alone satisfies secure Tailnet or iOS attachment behavior.

## Non-goals
- Native iOS app.
- Public internet hosting.
- Relaxing proxy host/origin/auth checks.

## Done when
Using Kitty from the phone feels like a supported mode, not remote debugging of the desktop app.
