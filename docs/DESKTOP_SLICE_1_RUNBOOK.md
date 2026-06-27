# Kitty Desktop — Slice 1: Survive Reboot (launchd)

**Goal of this slice:** Kitty's three local services start automatically after
login and recover from crashes — no Terminal required. This is the headline
benefit of the desktop work, delivered before any Tauri shell exists. Open
`http://127.0.0.1:4000` in a browser and Kitty is there.

This slice is macOS-only. The plist generator and its tests run anywhere (and
in CI); the steps below that call `launchctl` must run on the Mac.

## What ships in this slice

| Piece | File |
|---|---|
| LaunchAgent generator + fixed lifecycle commands | `scripts/kitty_desktop_launchd.py` |
| UI service wrapper (loopback, pins gateway URL) | `scripts/desktop/start_ui.sh` |
| Unit tests (plist safety + label allowlist) | `tests/test_desktop_launchd.py` |

The LiteLLM and gateway services reuse their existing canonical scripts
(`gateway/start_litellm.sh`, `gateway/start_gateway.sh`) — no new wrappers.

| Service | Label | Endpoint |
|---|---|---|
| LiteLLM | `com.kitty.desktop.litellm` | `127.0.0.1:8001` |
| Gateway | `com.kitty.desktop.gateway` | `127.0.0.1:8000` |
| UI | `com.kitty.desktop.ui` | `127.0.0.1:4000` |

## Safety properties (enforced by tests)

- **Absolute paths** in every plist (launchd's GUI-login environment is stripped).
- **Loopback pinned in the plist environment** (`*_HOST=127.0.0.1`), so a service
  cannot bind to the network even if a wrapper default changes.
- **No secrets in plists** — the bearer/keys load from `.env` via the wrappers.
- **Crash throttle** (`ThrottleInterval=10`) so a bad key cannot spin a tight
  restart loop.
- **Fixed launchctl argv against a label allowlist** — `restart`/`bootout` reject
  any service name that is not one of the three.

## Install (on the Mac)

Prerequisites: the UI must be built once so `next start` has output to serve —
`cd gateway/kitty-chat && npm run build`.

```bash
cd ~/Projects/kitty

# 1. Render the three plists into ~/Library/LaunchAgents (idempotent).
python3.11 scripts/kitty_desktop_launchd.py install

# 2. Bootstrap + enable all three launchd jobs.
python3.11 scripts/kitty_desktop_launchd.py bootstrap all

# 3. Confirm each endpoint answers.
curl -s http://127.0.0.1:8000/health        # {"status":"ok","service":"kitty-gateway"}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4000   # 200
```

Inspect a plist before trusting it:

```bash
python3.11 scripts/kitty_desktop_launchd.py generate | less
plutil -lint ~/Library/LaunchAgents/com.kitty.desktop.gateway.plist
```

The installer refuses linked git worktrees by default because launchd stores
absolute paths. Run it from the canonical checkout (`~/Projects/kitty`) so the
login services do not point at a disposable branch worktree.

## Daily commands

```bash
python3.11 scripts/kitty_desktop_launchd.py status all
python3.11 scripts/kitty_desktop_launchd.py restart gateway   # one service
python3.11 scripts/kitty_desktop_launchd.py restart all
python3.11 scripts/kitty_desktop_launchd.py bootout all       # stop + unload
```

Service logs: `logs/desktop/<service>.log` and `<service>.err.log`.

## Acceptance — the only proof that matters

1. `bootstrap all`, then confirm all three endpoints answer.
2. Kill one service's process; confirm launchd restarts it within the throttle
   window and the endpoint recovers (`status`, then re-`curl`).
3. **Log out and back in** — confirm all three come up without a Terminal.
4. **Reboot.** After login, with no Terminal, open `http://127.0.0.1:4000`, send
   one chat message, and get a streamed reply.

Step 4 is the real bar. If chat fails after reboot while the gateway and UI are
healthy, the suspect is LiteLLM under launchd's reduced environment — check
`logs/desktop/litellm.err.log` first.

## Known follow-ups (not in this slice)

- **CI council tests:** now that `langgraph` is declared in `requirements.txt`,
  the two `--ignore` lines in `.github/workflows/tests.yml`
  (`test_council_graph.py`, `test_mcp_council_server.py`) are redundant and can
  be dropped so those tests run in CI.
- **Proxy default:** resolved by the app-shell branch. The UI proxy now defaults
  to `127.0.0.1:8000`, can read the repo `.env`, and returns a loud `503` when
  no gateway secret is available. The UI wrapper still exports
  `KITTY_GATEWAY_URL=http://127.0.0.1:8000` so launchd never depends on a
  fallback.
- **Standalone UI runtime:** this slice uses `next start`. The design's
  `output: 'standalone'` runtime is a later hardening (Tauri slice).
- **Status surface / "restarted N times" diagnostic** belongs with the Tauri
  status window.
