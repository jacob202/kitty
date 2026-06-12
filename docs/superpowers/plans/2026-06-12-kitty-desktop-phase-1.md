# Kitty Desktop Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Kitty a dependable macOS desktop product that starts after login, opens with `Command+Shift+K`, chats without Open WebUI, captures thoughts during stack failure, and explains its own health.

**Architecture:** Three per-user LaunchAgents own LiteLLM, FastAPI, and the standalone Next.js UI. A least-privilege Tauri 2 application owns tray, windows, shortcut, launch-at-login, Quick Capture, status, and fixed service-recovery controls.

**Tech Stack:** macOS `launchd`, Python 3.12, FastAPI, LiteLLM, Next.js 16 standalone output, TypeScript, Vite, Tauri 2, Rust, pytest, Vitest.

**Design:** `docs/superpowers/specs/2026-06-12-kitty-desktop-phase-1-design.md`

---

## Planning Corrections

The first draft is superseded in these areas:

- LiteLLM is required because streaming chat has no direct fallback.
- `launchd` replaces the custom PID supervisor.
- Phase 1 adds no desktop capture/status HTTP routes.
- Only Tauri writes desktop captures.
- JSONL append uses a cross-process lock and `sync_data()`.
- Next.js uses standalone output, not `next start` against full `node_modules`.
- Product config moves to `~/Library/Application Support/Kitty Desktop/`.
- Installation becomes transactional and includes refresh and uninstall.
- A proof-first Gate 0 precedes full implementation.

The current uncommitted prototype files are not accepted implementation:

- `gateway/paths.py`
- `gateway/desktop_store.py`
- `gateway/routes/desktop.py`
- `gateway/routes/register.py`
- `scripts/kitty_desktop_runtime.py`

Task 1 removes those prototype changes before production work.

## Delivery Order

1. Clean prototype and establish contracts.
2. Prove the four risky assumptions.
3. Build standalone Kitty UI runtime.
4. Generate and control LaunchAgents.
5. Build least-privilege Tauri shell.
6. Add durable Quick Capture.
7. Add status and recovery.
8. Build transactional install/refresh/uninstall.
9. Run automated, login, and reboot acceptance.

Do not parallelize tasks that modify the same contract or lifecycle boundary.

## Task 1: Reset the Prototype and Lock the Scope

**Files:**

- Restore: `gateway/paths.py`
- Restore: `gateway/routes/register.py`
- Delete: `gateway/desktop_store.py`
- Delete: `gateway/routes/desktop.py`
- Delete: `scripts/kitty_desktop_runtime.py`
- Create: `contracts/inbox_capture.schema.json`
- Create: `docs/DESKTOP_PHASE_1_DECISIONS.md`

- [ ] **Step 1: Remove only the unverified prototype**

Restore `gateway/paths.py` and `gateway/routes/register.py` to their pre-desktop
content. Delete the three untracked prototype files. Do not touch unrelated
changes.

- [ ] **Step 2: Verify gateway imports**

```bash
venv/bin/python -c "from gateway.app import app; print(app.title)"
```

Expected:

```text
Kitty Gateway
```

- [ ] **Step 3: Add the inbox JSON Schema**

Require:

```json
[
  "id",
  "created_at",
  "source",
  "type",
  "text",
  "processed",
  "project",
  "tags"
]
```

Constraints:

- UUID v4 string
- RFC 3339 UTC timestamp
- source `desktop_quick_capture` for Phase 1
- type `text`
- text length 1-10000
- processed `false`
- project string or null
- unique string tags
- additive future properties allowed

- [ ] **Step 4: Add a short decision log**

Record:

- macOS-only
- launchd for services
- Tauri for UI
- required service set includes LiteLLM
- no desktop HTTP API
- immutable inbox
- future receipt log
- no mobile implementation

- [ ] **Step 5: Validate docs and schema**

```bash
venv/bin/python -m json.tool contracts/inbox_capture.schema.json >/dev/null
git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add gateway/paths.py gateway/routes/register.py contracts/inbox_capture.schema.json docs/DESKTOP_PHASE_1_DECISIONS.md
git commit -m "docs(desktop): lock Phase 1 architecture and capture contract"
```

## Task 2: Gate 0A - Prove Next Standalone Runtime

**Files:**

- Modify: `gateway/kitty-chat/next.config.ts`
- Create: `scripts/build_kitty_desktop_ui.py`
- Create: `tests/test_desktop_ui_build.py`

- [ ] **Step 1: Write failing build-script tests**

Cover:

```python
def test_build_command_uses_npm_ci_and_npm_run_build(): ...
def test_staging_copies_public_and_static_assets(): ...
def test_manifest_contains_commit_and_source_hashes(): ...
def test_staging_rejects_missing_standalone_server(): ...
```

- [ ] **Step 2: Enable standalone output**

Set:

```typescript
const nextConfig: NextConfig = {
  output: 'standalone',
}
```

- [ ] **Step 3: Build into a temporary staging directory**

`build_kitty_desktop_ui.py` must:

1. run `npm ci`
2. run `npm run build`
3. require `.next/standalone/server.js`
4. copy standalone output to staging
5. copy `public/`
6. copy `.next/static/`
7. write a build manifest
8. atomically replace `data/desktop/ui-runtime/`

- [ ] **Step 4: Prove `/proxy` survives standalone deployment**

Start staged `server.js` on a test port with a stub gateway. Verify:

- `/` returns Kitty UI content
- `/proxy/health` reaches the stub gateway
- a public mascot asset returns 200
- a static Next asset returns 200

- [ ] **Step 5: Run tests**

```bash
venv/bin/python -m pytest tests/test_desktop_ui_build.py -q --tb=short
cd gateway/kitty-chat
npm test
npm run build
```

- [ ] **Step 6: Commit**

```bash
git add gateway/kitty-chat/next.config.ts scripts/build_kitty_desktop_ui.py tests/test_desktop_ui_build.py
git commit -m "feat(desktop): stage standalone Kitty UI runtime"
```

## Task 3: Gate 0B - Prove LaunchAgent Lifecycle

**Files:**

- Create: `scripts/kitty_desktop_launchd.py`
- Create: `tests/test_desktop_launchd.py`
- Create: `config/desktop/launchagents/`

- [ ] **Step 1: Write failing plist-generation tests**

Cover:

```python
def test_plists_use_absolute_paths(): ...
def test_plists_never_contain_secret_values(): ...
def test_plists_bind_only_loopback_services(): ...
def test_plists_have_run_at_load_keepalive_and_throttle(): ...
def test_each_service_has_distinct_log_paths(): ...
def test_labels_are_stable_and_unique(): ...
```

- [ ] **Step 2: Define stable labels**

```text
com.kitty.desktop.litellm
com.kitty.desktop.gateway
com.kitty.desktop.ui
```

- [ ] **Step 3: Generate plists from templates**

Templates contain placeholders, not machine-specific committed paths.
Generation writes resolved plists to a temporary install staging directory.

- [ ] **Step 4: Add fixed lifecycle commands**

```text
install
bootstrap
bootout
status
restart <litellm|gateway|ui|all>
```

Reject all other service names and actions.

- [ ] **Step 5: Run a disposable LaunchAgent proof**

Generate a temporary job that starts a harmless local HTTP test process,
exits once, and is restarted by `launchd`. Bootstrap it into `gui/$(id -u)`,
verify restart, then boot it out and remove it.

This proof must not use production Kitty labels or ports.

- [ ] **Step 6: Run tests**

```bash
venv/bin/python -m pytest tests/test_desktop_launchd.py -q --tb=short
plutil -lint <each generated test plist>
```

- [ ] **Step 7: Commit**

```bash
git add scripts/kitty_desktop_launchd.py tests/test_desktop_launchd.py config/desktop/launchagents
git commit -m "feat(desktop): add tested LaunchAgent lifecycle"
```

## Task 4: Gate 0C - Scaffold Least-Privilege Tauri

**Files:**

- Create: `apps/kitty-desktop/package.json`
- Create: `apps/kitty-desktop/package-lock.json`
- Create: `apps/kitty-desktop/vite.config.ts`
- Create: `apps/kitty-desktop/tsconfig.json`
- Create: `apps/kitty-desktop/index.html`
- Create: `apps/kitty-desktop/src/`
- Create: `apps/kitty-desktop/src-tauri/Cargo.toml`
- Create: `apps/kitty-desktop/src-tauri/Cargo.lock`
- Create: `apps/kitty-desktop/src-tauri/tauri.conf.json`
- Create: `apps/kitty-desktop/src-tauri/src/`
- Create: `apps/kitty-desktop/src-tauri/capabilities/`

- [ ] **Step 1: Pin dependencies**

Select compatible Tauri 2/plugin versions, record exact npm versions in
`package-lock.json`, and commit `Cargo.lock`. Do not use floating `"*"` versions.

- [ ] **Step 2: Define three windows**

- `main`: external `http://127.0.0.1:4000`
- `capture`: bundled content
- `status`: bundled content

- [ ] **Step 3: Split capabilities**

Create dedicated capability files for `capture` and `status`.

The `main` label must not appear in any privileged capability. Registered Rust
commands must additionally verify the calling window label.

- [ ] **Step 4: Add tray and shortcut proof**

Implement:

- tray icon
- Open Kitty
- Quick Capture
- Status
- Quit
- `Command+Shift+K`
- single instance

The shortcut opens `main`. If the UI endpoint is unavailable, it opens
`status`.

- [ ] **Step 5: Add security tests**

Tests inspect generated Tauri configuration and assert:

- no remote URL is granted IPC
- main is absent from privileged capabilities
- command handlers reject wrong window labels
- shell execution is not exposed to frontend JavaScript

- [ ] **Step 6: Verify**

```bash
cd apps/kitty-desktop
npm ci
npm test
npm run build
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

- [ ] **Step 7: Commit**

```bash
git add apps/kitty-desktop
git commit -m "feat(desktop): prove least-privilege Tauri shell"
```

## Task 5: Gate 0D - Prove Durable Quick Capture

**Files:**

- Create: `apps/kitty-desktop/src-tauri/src/capture.rs`
- Create: `apps/kitty-desktop/tests/capture.test.ts`
- Modify: `apps/kitty-desktop/src-tauri/Cargo.toml`
- Modify: `apps/kitty-desktop/src-tauri/src/lib.rs`

- [ ] **Step 1: Write Rust contract tests**

Cover:

- UUID v4
- UTC `Z` timestamp
- text trim and limit
- project normalization
- tag trim, deduplication, and order preservation
- schema-valid serialization
- no newline injection outside JSON escaping

- [ ] **Step 2: Write filesystem tests**

Cover:

- parent creation
- exclusive lock
- one complete line
- `sync_data()` success before response
- preserved input on error
- no capture text in error logs

- [ ] **Step 3: Add a concurrent writer test**

Spawn two independent writer processes against the same temporary inbox.
Require:

- expected record count
- every line parses
- every UUID is unique
- no partial or merged lines

- [ ] **Step 4: Implement fixed-path command**

```rust
save_quick_capture(
    text: String,
    project: Option<String>,
    tags: Vec<String>
) -> Result<CaptureRecord, CaptureError>
```

The path comes from validated product configuration. Frontend code cannot
supply a path.

- [ ] **Step 5: Verify with the entire stack stopped**

Boot out disposable/provisional services, save a capture, validate the last
line, then remove only the test record by UUID using a test helper.

- [ ] **Step 6: Commit**

```bash
git add apps/kitty-desktop
git commit -m "feat(desktop): prove durable offline quick capture"
```

## Gate 0 Review

- [ ] **Step 1: Write proof results**

Create:

```text
docs/DESKTOP_PHASE_1_GATE0_RESULTS.md
```

Record commands, outputs, failures, and design changes.

- [ ] **Step 2: Stop if any proof is unresolved**

Do not proceed to production service installation until all four proofs pass.

- [ ] **Step 3: Commit proof evidence**

```bash
git add docs/DESKTOP_PHASE_1_GATE0_RESULTS.md
git commit -m "test(desktop): record Phase 1 architecture proofs"
```

## Task 6: Build Production Service Wrappers

**Files:**

- Create: `scripts/desktop/start_litellm.sh`
- Create: `scripts/desktop/start_gateway.sh`
- Create: `scripts/desktop/start_ui.sh`
- Create: `tests/test_desktop_start_scripts.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write shell contract tests**

Assert each script:

- uses `set -euo pipefail`
- resolves the configured repo root
- loads `.env` through `load_env_safe.sh`
- binds to the required loopback port
- uses `exec`
- never prints a secret
- fails clearly when an executable or build is missing

- [ ] **Step 2: Implement wrappers**

LiteLLM and gateway wrappers delegate to their existing canonical scripts.
The UI wrapper executes the staged standalone `server.js` using the absolute
configured Node path.

- [ ] **Step 3: Add generated/runtime ignores**

Ignore:

```gitignore
data/desktop/ui-runtime/
logs/desktop.log
logs/desktop.log.1
logs/desktop/
apps/kitty-desktop/dist/
apps/kitty-desktop/src-tauri/target/
```

- [ ] **Step 4: Verify syntax and tests**

```bash
bash -n scripts/desktop/start_litellm.sh
bash -n scripts/desktop/start_gateway.sh
bash -n scripts/desktop/start_ui.sh
venv/bin/python -m pytest tests/test_desktop_start_scripts.py -q --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add scripts/desktop tests/test_desktop_start_scripts.py .gitignore
git commit -m "feat(desktop): add production service wrappers"
```

## Task 7: Install the Three Production LaunchAgents

**Files:**

- Modify: `scripts/kitty_desktop_launchd.py`
- Create: `tests/test_desktop_service_health.py`

- [ ] **Step 1: Add service identity checks**

LiteLLM:

- authenticated `/health`

Gateway:

- `/health`
- exact `service: kitty-gateway`

UI:

- page marker unique to Kitty UI
- `/proxy/health` exact gateway identity

- [ ] **Step 2: Detect port conflicts**

If a port responds but identity is wrong, return `port_conflict`. Never
terminate the process.

- [ ] **Step 3: Install and bootstrap**

Use modern per-user commands:

```text
launchctl bootstrap gui/<uid> <plist>
launchctl enable gui/<uid>/<label>
launchctl kickstart -k gui/<uid>/<label>
```

Repeated install must be idempotent.

- [ ] **Step 4: Verify recovery**

For each service:

1. verify healthy
2. terminate only the known LaunchAgent process
3. verify `launchd` restarts it
4. verify health recovers

- [ ] **Step 5: Run tests**

```bash
venv/bin/python -m pytest tests/test_desktop_launchd.py tests/test_desktop_service_health.py -q --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add scripts/kitty_desktop_launchd.py tests/test_desktop_service_health.py
git commit -m "feat(desktop): manage the complete Kitty service stack"
```

## Task 8: Complete Tauri Service Status and Recovery

**Files:**

- Create: `apps/kitty-desktop/src-tauri/src/health.rs`
- Create: `apps/kitty-desktop/src-tauri/src/services.rs`
- Create: `apps/kitty-desktop/src-tauri/src/logs.rs`
- Modify: `apps/kitty-desktop/src-tauri/src/lib.rs`
- Create: `apps/kitty-desktop/src/status.ts`
- Create: `apps/kitty-desktop/tests/status.test.ts`

- [ ] **Step 1: Define stable status types**

Service states:

```text
healthy
starting
unhealthy
not_loaded
port_conflict
configuration_error
```

Overall states:

```text
ready
degraded_chat
capture_only
broken
```

- [ ] **Step 2: Add fixed native commands**

```rust
desktop_status()
restart_service(ServiceName)
tail_log(LogName, limit)
reveal_path(PathKind)
```

Use enums, fixed job labels, fixed log paths, and fixed `launchctl` argument
construction. Reject arbitrary strings.

- [ ] **Step 3: Build status UI**

Display:

- three service states
- endpoint identity
- launchd diagnostic state
- inbox writability
- build freshness
- launch-at-login state
- recent logs

Rust reads local health credentials from the existing repo `.env` using a
dotenv parser. It must keep values in native memory, redact errors, and return
only booleans/status metadata to frontend code.

- [ ] **Step 4: Add actionable failures**

- missing UI build: Refresh Installation
- repo moved: configuration error
- port conflict: show port and owner diagnostics, no kill button
- LiteLLM failure: chat degraded, capture available
- inbox failure: preserve capture and show exact path

- [ ] **Step 5: Test all state combinations**

Include ready, degraded chat, capture only, broken, stale build, and conflict.

- [ ] **Step 6: Verify**

```bash
cd apps/kitty-desktop
npm test
cargo test --manifest-path src-tauri/Cargo.toml
```

- [ ] **Step 7: Commit**

```bash
git add apps/kitty-desktop
git commit -m "feat(desktop): add truthful status and service recovery"
```

## Task 9: Complete Quick Capture UX

**Files:**

- Create: `apps/kitty-desktop/src/capture.ts`
- Modify: `apps/kitty-desktop/src/styles.css`
- Modify: `apps/kitty-desktop/tests/capture.test.ts`

- [ ] **Step 1: Implement capture interaction**

Controls:

- text
- optional project
- optional comma-separated tags
- Save
- Cancel

Keyboard:

- `Command+Enter`: save
- `Escape`: hide without clearing

- [ ] **Step 2: Preserve failure state**

On write failure:

- keep every field
- focus text
- show concise error and target path
- allow retry

- [ ] **Step 3: Prevent accidental duplicate submission**

Disable Save while the native command is pending. After success, clear once
and hide once.

- [ ] **Step 4: Add accessibility checks**

Require labels, keyboard traversal, visible focus, sufficient contrast, and
screen-reader status for success/error.

- [ ] **Step 5: Verify stack-independent capture**

With all three LaunchAgents booted out, save and validate a capture.

- [ ] **Step 6: Commit**

```bash
git add apps/kitty-desktop
git commit -m "feat(desktop): finish Quick Capture experience"
```

## Task 10: Add Launch at Login and Full Tray

**Files:**

- Create: `apps/kitty-desktop/src-tauri/src/autostart.rs`
- Create: `apps/kitty-desktop/src-tauri/src/tray.rs`
- Modify: `apps/kitty-desktop/src-tauri/src/lib.rs`
- Modify: `apps/kitty-desktop/src-tauri/capabilities/`

- [ ] **Step 1: Initialize autostart**

Use the Tauri autostart plugin with `MacosLauncher::LaunchAgent`.

- [ ] **Step 2: First-run behavior**

The installer launches Kitty Desktop once. On first run, explicitly enable
launch at login and record that choice in product preferences. The Status
window exposes an immediate off switch.

- [ ] **Step 3: Keep state truthful**

After enable/disable, reread actual plugin state. Tray and Status display the
verified result.

- [ ] **Step 4: Complete tray actions**

- Open Kitty
- Quick Capture
- Status
- Launch at Login
- Restart each service
- Restart all
- Quit Kitty Desktop

- [ ] **Step 5: Verify close and quit semantics**

- closing windows leaves tray and services
- quitting app removes tray but leaves services
- relaunch restores one instance

- [ ] **Step 6: Commit**

```bash
git add apps/kitty-desktop
git commit -m "feat(desktop): finish tray and login startup"
```

## Task 11: Build Transactional Install, Refresh, and Uninstall

**Files:**

- Create: `scripts/install_kitty_desktop.py`
- Create: `scripts/uninstall_kitty_desktop.py`
- Create: `tests/test_desktop_installer.py`
- Create: `tests/test_desktop_uninstaller.py`

- [ ] **Step 1: Write installer transaction tests**

Cover:

- failed build leaves installed app untouched
- failed activation restores backup
- generated config contains no secrets
- plist backup and restore
- stable app path `~/Applications/Kitty Desktop.app`
- application-support config path
- build-manifest hashes

- [ ] **Step 2: Implement preflight**

Verify:

- macOS
- canonical repo exists
- venv Python
- LiteLLM venv and CLI
- Node and npm
- Rust and Cargo
- ports available or already correct Kitty services
- writable data/log/application-support directories

- [ ] **Step 3: Implement staged build**

Build UI and Tauri into temporary directories. Run artifact checks before
touching the installed app or LaunchAgents.

- [ ] **Step 4: Implement atomic promotion**

Backup current:

- app bundle
- generated LaunchAgent plists
- product config
- build manifest

Promote verified artifacts, bootstrap jobs, launch app, and verify health.
Rollback on activation failure.

- [ ] **Step 5: Implement refresh**

`--refresh` uses the same transaction and preserves data, logs, and user
preferences.

- [ ] **Step 6: Implement uninstall**

Default uninstall preserves all user data. `--purge-data` requires explicit
confirmation and lists paths before deletion.

- [ ] **Step 7: Run tests**

```bash
venv/bin/python -m pytest tests/test_desktop_installer.py tests/test_desktop_uninstaller.py -q --tb=short
```

- [ ] **Step 8: Commit**

```bash
git add scripts/install_kitty_desktop.py scripts/uninstall_kitty_desktop.py tests/test_desktop_installer.py tests/test_desktop_uninstaller.py
git commit -m "feat(desktop): add transactional lifecycle tools"
```

## Task 12: Documentation and Operator Surface

**Files:**

- Modify: `docs/ARCHITECTURE.md`
- Modify: `TASKS.md`
- Create: `docs/KITTY_DESKTOP_RUNBOOK.md`
- Create: `scripts/desktop_acceptance.sh`

- [ ] **Step 1: Document architecture**

Include:

- all four processes
- ports
- LaunchAgent labels
- config paths
- log paths
- inbox path
- Open WebUI optional status

- [ ] **Step 2: Write a beginner-safe runbook**

Commands:

```text
install
refresh
status
restart one
restart all
show logs
uninstall
```

Explain expected healthy output and what each failure means.

- [ ] **Step 3: Add non-destructive acceptance script**

Check:

- app bundle
- product config
- build freshness
- three loaded LaunchAgents
- three endpoint identities
- inbox writable
- no service binds beyond loopback

Do not add or remove a real inbox record. Use a temporary sibling file to test
filesystem permissions.

- [ ] **Step 4: Commit**

```bash
git add docs/ARCHITECTURE.md TASKS.md docs/KITTY_DESKTOP_RUNBOOK.md scripts/desktop_acceptance.sh
git commit -m "docs(desktop): add runbook and acceptance checks"
```

## Task 13: Full Automated Verification

- [ ] **Step 1: Python desktop tests**

```bash
venv/bin/python -m pytest \
  tests/test_desktop_ui_build.py \
  tests/test_desktop_launchd.py \
  tests/test_desktop_start_scripts.py \
  tests/test_desktop_service_health.py \
  tests/test_desktop_installer.py \
  tests/test_desktop_uninstaller.py \
  -q --tb=short
```

- [ ] **Step 2: Full Python suite**

```bash
venv/bin/python -m pytest tests/ -q --tb=short
```

- [ ] **Step 3: Kitty UI**

```bash
cd gateway/kitty-chat
npm ci
npm test
npm run build
```

- [ ] **Step 4: Tauri frontend and Rust**

```bash
cd apps/kitty-desktop
npm ci
npm test
npm run build
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

- [ ] **Step 5: Static checks**

```bash
git diff --check
plutil -lint ~/Library/LaunchAgents/com.kitty.desktop.litellm.plist
plutil -lint ~/Library/LaunchAgents/com.kitty.desktop.gateway.plist
plutil -lint ~/Library/LaunchAgents/com.kitty.desktop.ui.plist
bash scripts/desktop_acceptance.sh
```

## Task 14: Failure Injection

- [ ] **Step 1: LiteLLM failure**

Boot out LiteLLM. Verify:

- overall state `degraded_chat`
- UI and gateway remain visible
- Quick Capture succeeds
- restart action restores LiteLLM

- [ ] **Step 2: Gateway failure**

Boot out gateway. Verify:

- UI remains loadable
- status identifies gateway
- Quick Capture succeeds
- restart action restores gateway

- [ ] **Step 3: UI failure**

Boot out UI. Verify:

- shortcut opens Status
- capture opens
- restart action restores UI

- [ ] **Step 4: Port conflict**

Use a disposable test port configuration with a wrong HTTP server. Verify
`port_conflict` and no destructive process action.

- [ ] **Step 5: Filesystem failure**

Use a temporary read-only inbox path. Verify input preservation and recovery
after permissions are restored.

- [ ] **Step 6: Stale build**

Modify a copied UI source fixture. Verify Status reports `repo_changed` and
does not rebuild at login.

## Task 15: Login and Reboot Acceptance

**Files:**

- Modify: `SESSION_HANDOFF.md`
- Modify: `TASKS.md`

- [ ] **Step 1: Cold launch**

With services booted out, run the installer and verify the product reaches
`ready` without manually starting a service.

- [ ] **Step 2: Close, quit, and relaunch**

Verify exact semantics:

- close: app remains in tray
- quit: services remain running
- relaunch: one desktop instance

- [ ] **Step 3: Logout/login**

Enable Launch at Login, log out, log in, and verify:

- three services healthy
- tray present
- shortcut opens Kitty
- capture succeeds

- [ ] **Step 4: Reboot**

With explicit user approval, reboot. After login:

1. Do not open Terminal.
2. Press `Command+Shift+K`.
3. Send one real chat message and receive a streamed response.
4. Save one Quick Capture.
5. Open Status and verify `ready`.

- [ ] **Step 5: Record evidence**

Record:

- app path
- LaunchAgent labels
- endpoint checks
- exact test counts
- logout/login result
- reboot result
- known residual risks

- [ ] **Step 6: Mark complete only after evidence**

```bash
git add SESSION_HANDOFF.md TASKS.md
git commit -m "docs(desktop): record verified Phase 1 acceptance"
```

## Stop Rules

Stop and revise the design if:

- standalone Next output breaks `/proxy`
- external main content requires Tauri IPC
- any service must bind beyond `127.0.0.1`
- Quick Capture requires a running service
- installation must store a secret outside process environment
- mobile sync or cloud auth enters Phase 1
- a recovery action needs arbitrary shell input
- install failure can damage the current working installation
- full existing test suites regress

## Definition of Done

Phase 1 is complete only when:

- Gate 0 evidence exists
- all automated suites pass
- failure injection passes
- logout/login passes
- reboot passes
- streamed chat works after reboot
- Quick Capture works with the stack down
- install, refresh, and uninstall preserve user data
- the mobile companion remains unimplemented
