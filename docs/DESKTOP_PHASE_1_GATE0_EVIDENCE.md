# Desktop Phase 1 Gate 0 Evidence

**Date:** 2026-06-14  
**Machine:** Jacob's MacBook Air  
**Result:** Passed with production follow-ups recorded below.

Gate 0 used disposable files and temporary LaunchAgents. No Gate 0 service,
plist, secret, inbox, or Tauri app remains installed.

## Evidence

| Proof | Result | Evidence |
|---|---|---|
| Clean baseline | Pass | Python: `534 passed, 2 deselected`; kitty-chat: `72 passed`; TypeScript and production build passed. |
| Login service lifecycle | Pass | A per-user LaunchAgent exited with code `42`, restarted, served health on run 2, and booted out cleanly. |
| Standalone UI | Pass | Next.js standalone runtime served `/`, `/_next/static/*`, `/proxy/health`, and an SSE stream. Staged runtime was about 49 MB. |
| Least-privilege Tauri | Pass | A compiled Tauri 2 app allowed the bundled `capture` window to invoke one command. The external localhost `main` window produced no native invocation. |
| Durable capture | Pass | Eight concurrent writers produced eight complete, schema-valid, uniquely identified JSONL records while Kitty services were stopped. Each append used an advisory lock and `fsync`. |
| Full LaunchAgent chain | Pass | LiteLLM, gateway, and standalone UI reached ready state in 16 seconds when activated in dependency order. A real streamed completion traversed UI proxy → gateway → LiteLLM → provider and ended with `[DONE]`. |
| Auth boundary | Pass | Direct unauthenticated access to a protected gateway route returned `401`; the UI proxy succeeded with its private temporary secret. |

## Decisions From Running Code

1. Use absolute executable and working-directory paths. The GUI login
   environment supplied only `/usr/bin:/bin:/usr/sbin:/sbin`.
2. Use LiteLLM `/health/readiness`, not `/health`. The latter requires auth and
   performs provider checks, so it is unsuitable as a lifecycle probe.
3. Activate services in dependency order: LiteLLM, gateway, then UI. They
   remain independently owned by `launchd`, but the installer should avoid a
   cold-start resource stampede.
4. Set `ProcessType` to `Interactive` for the user-facing local services.
5. Run installed services from a staged, known build. The mutable development
   checkout contained unrelated prototype changes that prevented gateway
   startup.
6. Generate or require `GATEWAY_SECRET` during installation and keep it out of
   plists. The current machine environment does not define one.
7. Keep the Tauri main window capability-free. Privileged bundled windows must
   also verify their caller label in Rust.
8. Keep capture independent from HTTP and AI availability.

## Defects Found

- The Next.js proxy defaulted to dead port `5001`. Gate 0 added a regression
  test and corrected the canonical fallback to `127.0.0.1:8000`.
- `gateway.paths.validate_env()` still claimed missing-secret auth was
  disabled. The middleware now fails closed, so the warning and its regression
  test were corrected.
- Next.js standalone output was not enabled. Gate 0 enabled it and proved the
  required asset-copy shape.
- A real chat took about 74 seconds because optional context backends can block
  prompt assembly before LiteLLM is called. This does not invalidate the
  desktop architecture, but Slice 1 must bound optional context retrieval so a
  healthy desktop app does not appear frozen.
- Finder `Icon` metadata had entered a Python package directory and broke
  `jsonschema` discovery. The metadata was removed; production capture should
  not depend on runtime JSON Schema package discovery.

## Provider Observation

LiteLLM itself was ready, and the configured fallback produced the streamed
response. Not every configured upstream provider passed LiteLLM's active
provider health check. Desktop status must distinguish local service health
from provider availability rather than calling the entire product "down."

## Gate 0 Exit

The selected `launchd` + standalone Next.js + least-privilege Tauri
architecture is viable on the target Mac. Proceed to Slice 1 with the startup,
health, secret, and bounded-context findings above encoded as production tests.

## Post-Gate 0 Verification

The first production hardening checkpoint encoded the proxy, authentication,
standalone-build, and bounded-context findings. Verification on 2026-06-14:

- Python: `538 passed, 2 deselected, 4 warnings`.
- kitty-chat: `74 passed`.
- TypeScript: passed.
- Next.js production build: passed and emitted `.next/standalone/server.js`.
