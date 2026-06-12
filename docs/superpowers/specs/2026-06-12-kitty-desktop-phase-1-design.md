# Kitty Desktop Phase 1 Design

**Date:** 2026-06-12

**Status:** Hardened after adversarial review

## Executive Decision

Build a macOS-first desktop product with two deliberately separate layers:

1. macOS `launchd` owns the always-on local services.
2. Tauri owns the native desktop experience.

The always-on service set is:

- LiteLLM on `127.0.0.1:8001`
- Kitty FastAPI gateway on `127.0.0.1:8000`
- Kitty Next.js UI on `127.0.0.1:4000`

Tauri provides:

- menu bar presence
- `Command+Shift+K`
- launch at login
- main Kitty window
- Quick Capture
- status and recovery controls

Quick Capture writes directly to `data/inbox.jsonl` and therefore does not
depend on LiteLLM, the gateway, the UI server, a network connection, or a model
provider.

Mobile remains design-only in `docs/MOBILE_COMPANION_PHASE_1_5.md`.

## Why This Architecture

The previous draft used a custom PID-based supervisor started by Tauri. That
would make the desktop app responsible for process adoption, PID reuse,
orphaned children, app crashes, restart loops, and login timing. Those are
operating-system service-management problems.

`launchd` already provides the required macOS behavior:

- start after login
- keep long-running processes alive
- throttle crash loops
- collect stdout and stderr
- restart individual services
- survive the desktop shell crashing
- report loaded job state through `launchctl`

Tauri should not act as an init system. It should be a native client and
control surface for services managed by macOS.

## Product Goal

After a reboot and macOS login:

1. Kitty's local services start without Terminal.
2. Kitty Desktop appears in the menu bar.
3. `Command+Shift+K` opens and focuses Kitty.
4. Quick Capture saves locally even when AI chat is unavailable.
5. Status explains failures and provides bounded recovery actions.

## Success Criteria

- No manual server startup is required after installation.
- Open WebUI is not started or required for daily desktop use.
- The main Kitty interface uses the existing `gateway/kitty-chat` product.
- Chat works after reboot, including the LiteLLM dependency.
- Quick Capture creates durable, schema-valid JSONL records.
- Window close leaves Kitty available in the menu bar.
- Launch at login can be enabled and disabled from Kitty Desktop.
- A failed service does not crash or disable Quick Capture.
- The user can identify and restart a failed Kitty service without Terminal.
- A real logout/login and reboot acceptance test passes.

## Non-Goals

- Full mobile application
- Mobile sync implementation
- Cloud authentication or hosting
- Push notifications
- App Store distribution
- Cross-platform desktop support
- Full chat rewrite
- Memory editor
- Agent dashboard
- Always-listening voice mode
- TELOS, PAI, specialist, agent, or MCP expansion
- Bundling Python, Node, LiteLLM, or model weights into a portable installer
- Automatic background rebuilding after every repository change

## Current Runtime Facts

- Canonical repo: `/Users/jacobbrizinski/Projects/kitty`
- Gateway: FastAPI at `127.0.0.1:8000`
- LiteLLM: model router at `127.0.0.1:8001`
- Kitty UI: Next.js at `127.0.0.1:4000`
- The UI uses a server-side `/proxy` route to inject the gateway bearer token.
- Streaming chat calls require LiteLLM. The current streaming code has no
  direct-provider fallback.
- The current Tauri-supported static Next.js export path cannot preserve the
  server-side proxy route.
- Next.js standalone output can preserve server behavior while reducing the
  deployed UI dependency set.
- The current Mac has Rust, Cargo, Node, npm, the Kitty venv, and the separate
  LiteLLM venv.

## Architecture

```text
macOS login
    |
    +--> LaunchAgent: com.kitty.desktop.litellm
    |       +--> 127.0.0.1:8001
    |
    +--> LaunchAgent: com.kitty.desktop.gateway
    |       +--> 127.0.0.1:8000
    |
    +--> LaunchAgent: com.kitty.desktop.ui
    |       +--> Next standalone server
    |       +--> 127.0.0.1:4000
    |
    +--> Kitty Desktop.app
            +--> tray/menu bar
            +--> Command+Shift+K
            +--> main external webview -> 127.0.0.1:4000
            +--> bundled Quick Capture window
            +--> bundled Status window
            +--> launchctl status/restart controls
            +--> direct locked append -> data/inbox.jsonl
```

## Ownership Boundaries

### macOS `launchd`

Owns service lifecycle only:

- start
- stop
- restart
- crash recovery
- stdout/stderr paths
- job state

### Tauri

Owns user interaction only:

- windows
- tray
- shortcut
- launch-at-login preference
- capture validation and append
- health queries
- bounded `launchctl` commands
- log display

### FastAPI Gateway

Remains the Kitty application backend. Desktop Phase 1 does not add
desktop-only capture or status routes because Tauri does not need them.

This removes duplicate inbox writers and avoids inventing a mobile API before
the mobile transport and threat model are chosen.

### Next.js UI

Remains the main Kitty interface. It keeps its server-side proxy so the bearer
secret never moves into browser JavaScript.

## Phase 1 Service Set

### LiteLLM

Launch command:

```text
/bin/bash <repo>/gateway/start_litellm.sh
```

Required because `iter_chat_completions_stream()` calls LiteLLM directly and
does not use the synchronous provider fallback chain.

Health:

```text
GET http://127.0.0.1:8001/health
Authorization: Bearer <local LiteLLM master key>
```

### Gateway

Launch command:

```text
/bin/bash <repo>/gateway/start_gateway.sh
```

Health identity:

```json
{"status": "ok", "service": "kitty-gateway"}
```

### Kitty UI

Build with Next.js standalone output:

```typescript
const nextConfig = {
  output: "standalone",
}
```

After `next build`, copy:

- `public/` to `.next/standalone/public/`
- `.next/static/` to `.next/standalone/.next/static/`

Launch command:

```text
<node> <repo>/data/desktop/ui-runtime/server.js
```

Environment:

```text
HOSTNAME=127.0.0.1
PORT=4000
KITTY_GATEWAY_URL=http://127.0.0.1:8000
KITTY_GATEWAY_SECRET=<loaded at runtime from .env>
```

The standalone runtime is staged under `data/desktop/ui-runtime/`, not run
directly from a mutable `.next` build directory.

## LaunchAgent Design

Generate these files during installation:

```text
~/Library/LaunchAgents/com.kitty.desktop.litellm.plist
~/Library/LaunchAgents/com.kitty.desktop.gateway.plist
~/Library/LaunchAgents/com.kitty.desktop.ui.plist
```

Each plist uses:

- absolute program paths
- absolute working directory
- `RunAtLoad`
- `KeepAlive` with `SuccessfulExit: false`
- `ThrottleInterval`
- service-specific stdout/stderr logs
- no secrets in the plist

Wrapper scripts load the existing `.env` through
`gateway/lib/load_env_safe.sh`. Plists never contain provider keys or bearer
tokens.

Service logs:

```text
logs/desktop/litellm.log
logs/desktop/gateway.log
logs/desktop/ui.log
```

Desktop lifecycle and installation log:

```text
logs/desktop.log
```

This preserves the requested top-level log while keeping concurrent service
output readable and attributable.

## Tauri Window Model

### Main Window

- Label: `main`
- URL: `http://127.0.0.1:4000`
- No Tauri IPC capability
- No filesystem, shell, process, or autostart permission

The localhost UI is treated as remote content. It receives no native command
authority.

### Capture Window

- Label: `capture`
- Bundled Vite content
- Access only to the named `save_quick_capture` command
- Small, centered, always-on-top while visible
- Hidden after successful save

### Status Window

- Label: `status`
- Bundled Vite content
- Access only to health, log-tail, autostart, reveal-path, and bounded service
  restart commands

Tauri capabilities are split by window label. The external `main` window is
excluded from every privileged capability.

## Native Controls

Use Tauri 2 official APIs and plugins:

- global shortcut
- autostart with macOS LaunchAgent launcher
- single instance
- tray icon/menu

Tray menu:

- Open Kitty
- Quick Capture
- Status
- Launch at Login
- Restart LiteLLM
- Restart Gateway
- Restart UI
- Restart All Kitty Services
- Quit Kitty Desktop

Closing windows hides them. Quitting Kitty Desktop does not stop the three
always-on services. Service shutdown is an explicit maintenance action, not a
side effect of closing the desktop shell.

`Command+Shift+K` shows, unminimizes, and focuses the main window. If the UI is
unhealthy, it opens Status instead and provides a retry action.

## Configuration

Product configuration lives outside the mutable repo:

```text
~/Library/Application Support/Kitty Desktop/config.json
```

Example:

```json
{
  "schema_version": 1,
  "repo_root": "/Users/jacobbrizinski/Projects/kitty",
  "python": "/Users/jacobbrizinski/Projects/kitty/venv/bin/python",
  "node": "/opt/homebrew/bin/node",
  "litellm_venv": "/Users/jacobbrizinski/kitty-services/venv-litellm",
  "gateway_url": "http://127.0.0.1:8000",
  "litellm_url": "http://127.0.0.1:8001",
  "ui_url": "http://127.0.0.1:4000",
  "inbox_path": "/Users/jacobbrizinski/Projects/kitty/data/inbox.jsonl",
  "desktop_log_path": "/Users/jacobbrizinski/Projects/kitty/logs/desktop.log"
}
```

No secret is stored in this file.

Absolute paths are required because GUI/login processes receive a reduced
environment compared with an interactive shell.

## Build Freshness

Installation writes:

```text
~/Library/Application Support/Kitty Desktop/build-manifest.json
```

Fields:

```json
{
  "git_commit": "full commit hash",
  "package_lock_sha256": "sha256",
  "ui_source_sha256": "sha256",
  "built_at": "UTC timestamp",
  "app_version": "version"
}
```

Status compares the installed build manifest with current repo inputs.

States:

- `current`
- `repo_changed`
- `dependencies_changed`
- `manifest_missing`

The desktop product continues running a known build when stale. It does not
rebuild at login. Status instructs the user to run the refresh installer.

## Capture Contract

Canonical file:

```text
data/inbox.jsonl
```

Each line:

```json
{
  "id": "uuid",
  "created_at": "2026-06-12T12:00:00Z",
  "source": "desktop_quick_capture",
  "type": "text",
  "text": "...",
  "processed": false,
  "project": null,
  "tags": []
}
```

Rules:

- UUID v4
- UTC RFC 3339 timestamp with `Z`
- `source` is exactly `desktop_quick_capture`
- Phase 1 `type` is exactly `text`
- trimmed text, 1-10,000 characters
- `processed` is `false` at creation
- project is a trimmed string or `null`
- tags are trimmed, unique, non-empty strings
- UTF-8 JSON, one object per line
- no capture text in logs

Contract file:

```text
contracts/inbox_capture.schema.json
```

### Durability and Concurrency

Capture append must:

1. Create the parent directory if needed.
2. Open a sibling lock file.
3. Acquire an exclusive advisory lock.
4. Serialize the complete line before writing.
5. Append the line in one write operation.
6. Call `sync_data()` before reporting success.
7. Release the lock.

The Tauri single-instance plugin reduces duplicate desktop writers, but the
file lock is still required for future import tools.

### Processing Semantics

`inbox.jsonl` is an immutable intake log. Phase 1 never rewrites old lines.

The required `processed: false` field describes creation state. A future inbox
processor records state transitions in a separate append-only receipt log:

```text
data/inbox_receipts.jsonl
```

Example future receipt:

```json
{
  "capture_id": "uuid",
  "status": "processed",
  "processed_at": "2026-06-12T13:00:00Z"
}
```

This avoids in-place JSONL mutation and preserves the original mobile/desktop
capture record.

## Health Model

Status combines:

1. HTTP identity and readiness
2. `launchctl` loaded-job diagnostics
3. build freshness
4. file-path writability

The Rust core reads `GATEWAY_SECRET`, `LITELLM_KEY`, or
`LITELLM_MASTER_KEY` from the existing repo `.env` only when performing local
health probes. Values stay in Rust memory, are never emitted to frontend
JavaScript, and are redacted from every error and log.

Per-service state:

- `healthy`
- `starting`
- `unhealthy`
- `not_loaded`
- `port_conflict`
- `configuration_error`

Overall product state:

- `ready`: UI, gateway, and LiteLLM healthy
- `degraded_chat`: UI and gateway healthy, LiteLLM unhealthy
- `capture_only`: capture path writable, main stack unavailable
- `broken`: capture path not writable

HTTP health is the source of truth for readiness. `launchctl` state is
diagnostic context, not proof of application health.

## Startup and Recovery

### Login

1. `launchd` starts the three services independently.
2. Tauri starts through its launch-at-login registration.
3. Tauri creates tray, shortcut, capture, and status facilities immediately.
4. Tauri polls health without blocking the macOS event loop.
5. Main window opens only when requested.

No strict launch ordering is required. Each service is independently
restartable and health-checked.

### Recovery Actions

Tauri may execute only fixed commands:

```text
/bin/launchctl kickstart -k gui/<uid>/com.kitty.desktop.litellm
/bin/launchctl kickstart -k gui/<uid>/com.kitty.desktop.gateway
/bin/launchctl kickstart -k gui/<uid>/com.kitty.desktop.ui
```

No arbitrary shell command or user-supplied argument reaches `launchctl`.

Port conflicts are reported. Kitty Desktop never kills an unrecognized
process.

## Installation, Update, and Uninstall

### Transactional Install

`scripts/install_kitty_desktop.py` performs:

1. preflight
2. tests for critical assumptions
3. UI standalone build in a temporary staging directory
4. Tauri build in staging
5. app and configuration verification
6. backup of currently installed app/plists
7. atomic promotion into final locations
8. LaunchAgent bootstrap
9. app launch and health verification

If build or verification fails before promotion, the current installation is
untouched. If activation fails after promotion, restore the previous app and
plists.

### Refresh

Run the same installer with `--refresh`. It rebuilds only after preflight and
replaces the installed artifacts transactionally.

### Uninstall

`scripts/uninstall_kitty_desktop.py`:

- disables desktop launch at login
- boots out the three Kitty Desktop LaunchAgents
- removes only generated plists and the installed app
- preserves `data/inbox.jsonl`, `data/`, and `logs/` by default
- removes product data only with an explicit `--purge-data`

## Logging

`logs/desktop.log` contains:

- installer lifecycle
- app lifecycle
- health transitions
- service restart requests
- build freshness changes

Service output remains in:

- `logs/desktop/litellm.log`
- `logs/desktop/gateway.log`
- `logs/desktop/ui.log`

Requirements:

- ISO timestamps
- service label
- no environment values
- no bearer tokens
- no capture text
- 5 MB rotation with one backup for each desktop log

## Security

- Bind all services to `127.0.0.1`.
- Never grant Tauri IPC to the external main window.
- Restrict privileged commands by window label and command allowlist.
- Store no secrets in plist, app config, frontend JavaScript, or git.
- Load secrets only into service process environments.
- Read health-probe secrets only inside Rust core memory and never return them
  through Tauri commands.
- Use fixed absolute executables and fixed `launchctl` job labels.
- Do not expose mobile ingress in Phase 1.
- Treat a moved repo as a configuration error requiring refresh install.

## Proof-First Gate 0

Before full product work, build four disposable proofs:

1. LaunchAgent proof: login-domain job starts a harmless local test server and
   survives its first process exit.
2. UI proof: Next standalone output preserves `/proxy` and serves public/static
   assets correctly.
3. Tauri proof: tray plus global shortcut can open an external localhost
   window while the external window has no IPC capability.
4. Capture proof: with all services stopped, a locked and synced append creates
   one schema-valid inbox line.

Gate 0 is discarded after its findings are folded into tests and production
code. Failure of any proof triggers design revision before feature buildout.

## Test Strategy

### Automated

- JSON Schema contract tests
- Rust capture serialization, lock, append, and fsync tests
- concurrent writer test using two processes
- installer plist generation and path escaping tests
- LaunchAgent label and command tests
- health identity and port conflict tests
- build-manifest freshness tests
- Tauri capability test proving `main` has no privileged capability
- Tauri command allowlist tests
- Next standalone build and `/proxy` integration test
- existing Python suite
- existing Kitty UI suite
- Rust format, Clippy, and unit tests

### Manual

- all services stopped
- one service already healthy
- LiteLLM unavailable
- gateway unavailable
- UI unavailable
- wrong process on each port
- malformed `.env`
- missing Node executable
- moved repo
- read-only inbox directory
- shortcut conflict
- app close, quit, and crash
- logout/login
- reboot

## Acceptance Gates

### Gate 0: Assumptions

All four proof experiments pass.

### Gate 1: Capture

Quick Capture survives complete stack failure and concurrent append testing.

### Gate 2: Services

All three LaunchAgents start, recover, and report truthful health.

### Gate 3: Desktop Shell

Tray, windows, shortcut, single instance, and launch at login work with least
privilege.

### Gate 4: Operations

Install, refresh, restart, stale-build warning, and uninstall work without
destroying user data.

### Gate 5: Daily Use

Kitty opens, chats, captures, reports health, and recovers without Terminal.

### Gate 6: Reboot

After a real reboot and login, `Command+Shift+K` opens working Kitty and Quick
Capture saves successfully.

## Adversarial Findings Resolved

1. **LiteLLM omission:** fixed by making it a required managed service.
2. **Fragile PID supervisor:** replaced with `launchd`.
3. **Tauri crash coupling:** services continue independently.
4. **Duplicate JSONL writers:** desktop HTTP capture API removed from Phase 1.
5. **Concurrent append risk:** explicit advisory lock and `sync_data()`.
6. **Undefined processed lifecycle:** immutable intake plus future receipt log.
7. **Next server deployment weight:** standalone output staged for runtime.
8. **External webview privilege:** main window receives no Tauri IPC.
9. **Stale UI after repo changes:** build manifest and refresh workflow.
10. **Unsafe in-place install:** transactional promotion and rollback.
11. **No cleanup path:** explicit uninstall preserving data.
12. **False completion risk:** logout/login and reboot are required evidence.

## Go/No-Go

**Go**, after Gate 0.

The architecture is intentionally local and macOS-specific. It solves the
actual startup-friction problem with native operating-system service
management, preserves the existing Kitty product, and keeps Quick Capture
independent from the least reliable part of the stack.

## Primary References

- Next.js standalone output:
  https://nextjs.org/docs/app/api-reference/config/next-config-js/output
- Tauri capabilities:
  https://v2.tauri.app/security/capabilities/
- Tauri global shortcut:
  https://v2.tauri.app/plugin/global-shortcut/
- Tauri autostart:
  https://v2.tauri.app/plugin/autostart/
- Tauri system tray:
  https://v2.tauri.app/learn/system-tray/
