# KH-REMOTE-01 — Authenticated phone/Tailnet access matches the proxy security model

**Initiative:** none — deliberately interactive  
**Owner:** ChatGPT/Codex interactive lane after fresh collision check  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Depends on:** KH-RUNTIME-01  
**Status:** packet only — no implementation/runtime mutation performed

## Why there is no Builder manifest
This packet requires Node-only frontend verification, `.claude` compatibility-file mutation, security-sensitive live network configuration, or a combination that Builder's current packet runner cannot prove safely. Per `PACKET_STANDARD.md` F9/authority rules, it stays interactive rather than carrying fake Builder gates.

## What Jacob can do after this
Jacob can open Kitty from an iPhone over the Tailnet and use real workflows through an authenticated path without exposing the Gateway or its bearer secret.

## Verified finding
Current `./kitty ui` sets `KITTY_UI_BIND_ALL=true`, `verify-home` prints an `http://<tailscale-ip>:4000` URL, Settings still mentions tailnet development, but Next `/proxy` deliberately rejects every non-loopback Host. The old `D1-tailnet-serve` initiative describes authenticated Tailscale Serve but is not live in the current Builder DB and predates the stricter proxy boundary.

## Intended scope
- `kitty`
- `scripts/desktop/start_ui.sh`
- `gateway/routes/network.py`
- `gateway/kitty-chat/src/lib/gateway-proxy-config.ts`
- `gateway/kitty-chat/src/app/proxy/[...path]/route.ts`
- `gateway/kitty-chat/src/components/SettingsPanel.tsx`
- `gateway/kitty-chat/tests/proxyRoute.test.ts`
- `gateway/kitty-chat/tests/packageSecurity.test.ts`
- `tests/test_kitty_launcher_runtime.py`
- `tests/test_start_ui_script.py`


## Plan / hardened direction
1. Make loopback binding the normal `kitty ui` default again; an all-interface development bind must never be the supported phone path.
2. Before code changes, run a read-only Tailscale Serve probe on the current machine to capture the exact Host/origin/forwarded-identity headers reaching Next. Do not assume Serve rewrites Host.
3. Define one reviewed trust decision for remote proxy requests: only requests proven to arrive through the local authenticated Tailnet edge and matching the configured Tailnet origin may use the server-side Gateway secret. Arbitrary LAN Hosts/origins remain 403.
4. Keep Gateway and LiteLLM loopback-only. Never put `GATEWAY_SECRET` into browser JS, localStorage, URL parameters, or a user-readable config endpoint.
5. Update `/network/tailnet`, Settings, `verify-home`, and recovery copy so they advertise only the actually supported HTTPS/authenticated URL.
6. Runtime Tailscale Serve configuration is a separate explicit side effect: require Jacob confirmation immediately before applying/changing Serve state; packet implementation/tests may proceed without mutating it.


## Acceptance criteria
1. A phone reaching the supported Tailnet URL can load the shell and complete an authenticated `/proxy/health` plus one normal workflow request.
2. A direct LAN/Tailnet-IP Host that bypasses the authenticated edge remains rejected and cannot cause Next to inject the Gateway bearer secret.
3. Gateway and LiteLLM listeners remain loopback-only.
4. `kitty ui`, `verify-home`, Settings, and `/network/tailnet` agree on the supported remote-access model and URL scheme.
5. No credential is exposed to client JavaScript, URLs, logs, or user-facing error copy.
6. Service unavailable/revoked-Tailnet states fail closed with one recovery action.


## Verification
- `python -m pytest -q tests/test_kitty_launcher_runtime.py tests/test_start_ui_script.py`
- `cd gateway/kitty-chat && npx vitest run tests/proxyRoute.test.ts tests/packageSecurity.test.ts --reporter=dot`
- `cd gateway/kitty-chat && npx tsc --noEmit`
- Independent desktop + real iPhone/Tailnet PA after explicit runtime configuration approval.


The implementation must demonstrate a RED reproduction or measured baseline before production edits, then exact-head GREEN evidence. User-facing changes require desktop + iPhone-class acceptance and an independent reviewer who did not implement the change.

## Stop condition
If Tailscale Serve does not provide a verifiable local/authenticated edge signal that Next can safely distinguish from arbitrary LAN traffic, stop and design a tiny local reverse proxy/edge adapter instead. Do not weaken `isTrustedProxyRequest` to accept all private/tailnet hosts.

## Recovery / authority guard
No packet here authorizes paid provider calls, credential changes, push/PR/merge, destructive data operations, or edits to canonical while another lane owns the path. Re-read `workspace_global`, GitHub #490, current PRs/worktrees, and Builder state immediately before implementation. UNKNOWN remains UNKNOWN.
