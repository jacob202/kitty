# Kitty Chat — Kitty's native frontend

This is Kitty's native UI, a Next.js app in `gateway/kitty-chat/`. Per
[ADR 0039](../../docs/adr/0039-kitty-native-product-surface.md) it is Kitty's
canonical user-facing product surface — not a generic `create-next-app`
project. Open WebUI remains optional reference software only.

## Relationship to the Gateway

The frontend renders product state; the backend owns the durable truth. The
FastAPI Gateway in the parent `gateway/` directory (app entry `../app.py`) and
the LiteLLM model proxy serve it. The UI reaches the Gateway through the shared
`/proxy/*` surface and waits on `/proxy/health` before mounting app content.
Frontend state may optimistically improve responsiveness but must reconcile
back to server truth, and a reload must reconstruct important state from the
backend (ADR 0039).

## Product launch

The normal way to run Kitty is the repo launcher, which starts the Gateway,
LiteLLM, and this UI through one canonical bootstrap
(`../../scripts/desktop/start_ui.sh`) and opens the browser. From the repo
root:

```bash
./kitty            # Gateway + LiteLLM + native UI, opens browser (same as ./kitty start)
./kitty ui         # native UI only
./kitty up         # Gateway + LiteLLM only (no UI)
./kitty status     # mode, SHA, ports, freshness for every managed listener
./kitty down       # stop only this checkout's owned listeners
```

The UI is served at `http://127.0.0.1:4000` (loopback). See the
[Launcher Contract](../../docs/reference/LAUNCHER_CONTRACT.md) for the required
shared properties (build-freshness check, port-conflict handling, ownership-safe
shutdown). Remote/Tailnet serving is **not** a supported product path:
`make ui-tailnet` bypasses the canonical bootstrap and the server-side proxy
rejects non-loopback Hosts (tracked as defect `KH-REMOTE-01`), so do not
advertise remote access from here.

## Frontend development (dev-only)

These run Next directly and are **not** product-runtime evidence — they skip
the canonical UI bootstrap and cannot support source-freshness or phone-access
claims. From this directory:

```bash
npm ci             # install deps once
npm run dev        # next dev -H 127.0.0.1 -p 4000 (loopback only)
npm run build      # production build
npm run start      # serve the production build (loopback only)
```

## Test, build, and smoke targets

Run from the repo root unless noted. Full tier details are in
[`../../TESTING.md`](../../TESTING.md) and the root `../../Makefile`.

| Target | What it runs |
| --- | --- |
| `make ui-test` | Vitest unit/component suite (`npm test`) |
| `make ui-build` | production Next.js build; refuses to run while this directory has uncommitted source changes |
| `make smoke-test` | Playwright browser smoke (builds first) |
| `make smoke-test-hermetic` | Playwright against fake LiteLLM + real Gateway, end to end |

Or run directly from this directory: `npm test`, `npm run build`,
`npm run test:smoke`, `npm run test:smoke:hermetic`. Vitest specs live under
`tests/`; Playwright specs under `tests/smoke/`.

## Local security boundary

Kitty is a local-first, single-user companion on the host Mac. The native UI
binds to loopback (`127.0.0.1:4000`); the canonical bootstrap refuses to serve a
stale build and refuses to launch when a conflicting listener — including a
sibling Kitty worktree — holds a required port. There is no supported remote
product path: do not expose the UI on `0.0.0.0` or rely on Tailnet reachability
for product behavior.
