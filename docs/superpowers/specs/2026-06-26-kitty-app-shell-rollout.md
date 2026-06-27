---
date: 2026-06-26
topic: Kitty app shell rollout
status: IN_PROGRESS
---

# Kitty App Shell Rollout

Goal: turn Kitty from "a dev stack plus a browser tab" into a daily-use app
without adding native shell weight before the product loop earns it.

## Stage 1 - Approaches

**Approach A (recommended): prove the thin app stack first.**
Keep the existing gateway and Next.js UI as the product surface. Land the
mobile/PWA shell, keep Slice 1 launchd as the macOS reliability layer, and use
the browser/PWA until reboot survival and daily use are boring.

Does well: fastest path to value, minimal new dependencies, keeps app logic in
the gateway. Trades off: no tray icon or global shortcut yet. Depends on:
launchd Slice 1, PWA/mobile UI, and clear install/runbook docs.

**Approach B: add Tauri now.**
Wrap the existing local URL in a Tauri 2 app for a native window, tray, and
future shortcuts.

Does well: feels like a real Mac app sooner. Trades off: adds Rust/Tauri,
capability config, signing/build concerns, and another failure surface before
the usage loop is proven. Depends on explicit dependency approval.

**Approach C: native iOS/macOS rewrite.**
Build SwiftUI clients over the gateway API.

Does well: best native feel eventually. Trades off: second UI codebase,
significant duplication, and mobile auth/networking design before the web app is
fully proven. Depends on a product reason stronger than "app-shaped."

## Stage 2 - Design

**Architecture:** gateway remains the product. Clients stay thin:
`kitty-chat` for web/PWA, launchd for local service lifecycle, and Tauri later
only as a capability-limited wrapper around the existing UI.

**Data flow:** browser/PWA/Tauri shell -> Next.js UI -> `/proxy/*` -> gateway ->
LiteLLM/tools/stores. The UI proxy must target `127.0.0.1:8000` and fail loudly
if the gateway secret is missing.

**Error handling:** no silent app fallback. Missing secrets return visible
errors; launchd logs to `logs/desktop/`; install/runbook steps surface exact
commands and endpoints. Optional native shell work must preserve the
least-privilege capability split proven in Gate 0.

**Testing:** use targeted UI tests for PWA/proxy behavior, `npm run build` for
the production UI, `tests/test_desktop_launchd.py` for plist safety, and a real
macOS acceptance pass for `bootstrap all`, service restart, logout/login, and
reboot.

**Scope in:** PWA/mobile shell, launchd Slice 1 validation, runbook alignment,
and a clear go/no-go gate for Tauri.

**Scope out:** native iOS app, cloud sync, push notifications, Tauri dependency
installation, signing/notarization, and broad storage migration.

## Stage 3 - Grill

Weakest assumption: launchd Slice 1 is already good enough for daily use.

If wrong: the app can look polished while still failing after reboot. Mitigation:
do not start Tauri until Slice 1 passes the real Mac acceptance checklist.

Unhandled edge case: a launchd-started UI with a stale build. Mitigation:
runbook keeps `npm run build` as a prerequisite; later standalone/staleness
manifest work belongs to the Tauri/status slice.

Forgotten risk: docs can drift after the proxy/PWA work. Mitigation: keep the
runbook's follow-ups current as part of this branch, and cite exact files.

Simpler version: no native shell yet. The smallest useful app is launchd plus a
PWA/mobile-width UI at `http://127.0.0.1:4000`.

## Stage 4 - Go Decision

Go for the thin app stack: PWA/mobile branch plus launchd Slice 1 cleanup.

No-go for adding Tauri in this pass. It needs a separate explicit dependency
approval and should start only after the launchd reboot proof and PWA smoke pass
are boringly green.

First action: align stale desktop runbook notes with the fixed proxy/PWA branch,
then rerun launchd and focused UI checks.
