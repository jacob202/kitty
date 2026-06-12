# Kitty Desktop Phase 1 Implementation Plan

> **Execution rule:** implement one slice at a time. Do not begin the next slice
> until the current slice has working evidence and a clean continuation note.

**Goal:** From reboot, Kitty starts without Terminal, opens from a shortcut,
captures thoughts even when AI fails, and later brings useful captures back.

**Architecture:** macOS `launchd` owns LiteLLM, FastAPI, and the standalone
Next.js UI. A least-privilege Tauri 2 app owns tray, windows, shortcuts,
launch-at-login, capture, status, and fixed recovery controls. Inbox retrieval
uses the existing `memory_graph` boundary.

**Design:** `docs/superpowers/specs/2026-06-12-kitty-desktop-phase-1-design.md`

## Delivery Principles

- Optimize for time to first daily-use value and interruption tolerance.
- Never ship a capture writer without a reader.
- Gate 0 is disposable evidence, not production scaffolding.
- Do not add a background agent for inbox processing.
- Do not make Raycast, Hammerspoon, Open WebUI, or mobile sync product
  dependencies.
- Do not hard-code a stale test count. Record and preserve the live baseline.
- Preserve unrelated working-tree changes; never use broad checkout/reset
  commands as cleanup instructions.
- Stop and move mobile, cloud, push, voice-assistant, and agent expansion into
  the Phase 1.5 document.

## Slice 0: Disposable Risk Spike

**Outcome:** We know the chosen architecture works on Jacob's Mac before
building production structures.

Use a throwaway branch or temporary directory. Do not commit product scaffolds.

- [ ] Record exact paths for Python, Node, npm, Cargo, LiteLLM venv, and repo.
- [ ] Record the current full Python test baseline with desktop prototypes
  removed from the import path; do not overwrite unrelated changes.
- [ ] Prove a harmless per-user LaunchAgent starts, restarts after one failure,
  and can be removed cleanly.
- [ ] Prove Next.js standalone output serves `/`, public/static assets, and the
  server-side `/proxy`.
- [ ] Prove a Tauri external localhost window has no IPC capability while a
  bundled window can call one allowlisted command.
- [ ] Prove a locked, synced append writes one schema-valid inbox line while all
  Kitty services are stopped.
- [ ] Prove one real streamed completion through this chain:

```text
standalone Next proxy -> LaunchAgent gateway -> LaunchAgent LiteLLM -> model
```

- [ ] Test `/proxy` with `KITTY_GATEWAY_URL` unset. Correct the stale `:5001`
  default to `:8000` or fail loudly when unset.
- [ ] Confirm desktop gateway startup fails closed when `GATEWAY_SECRET` is
  absent.
- [ ] Write a short evidence table: proof, command, result, artifact, decision.
- [ ] Delete the spike artifacts after findings become production tests.

**Exit gate:** all five proofs pass. If any fail, revise the design before
building Tauri or installer machinery.

## Slice 1: Kitty Survives Login and Reboot

**Outcome:** Browser-based Kitty no longer requires Terminal. This is the first
daily-use product win.

### 1.1 Establish Clean Contracts

- [ ] Remove only the known unverified desktop prototype changes from:
  `gateway/paths.py`, `gateway/routes/register.py`,
  `gateway/desktop_store.py`, `gateway/routes/desktop.py`, and
  `scripts/kitty_desktop_runtime.py`.
- [ ] Inspect each diff before changing it; preserve unrelated work.
- [ ] Add `contracts/inbox_capture.schema.json`.
- [ ] Add a compact `docs/DESKTOP_PHASE_1_DECISIONS.md`.
- [ ] Run the full live Python suite and record the actual baseline.

### 1.2 Harden Existing Runtime Seams

- [ ] Fix the proxy gateway default or make the required env var fail loudly.
- [ ] Add proxy tests for env-present and env-absent behavior.
- [ ] Make desktop wrappers set `KITTY_ENV=prod`.
- [ ] Refuse desktop gateway startup when `GATEWAY_SECRET` is missing.
- [ ] Add loopback Host-header validation for desktop mode.
- [ ] Verify every state-changing route rejects a missing/invalid bearer token.
- [ ] Update current authority docs that incorrectly name port `5001` or Python
  `3.11`, after verifying the actual interpreter path.

### 1.3 Build the Standalone UI Runtime

- [ ] Enable Next.js standalone output.
- [ ] Create a build script that runs `npm ci`, builds in staging, requires
  `server.js`, copies `public` and `.next/static`, writes a freshness manifest,
  and promotes only a complete build.
- [ ] Add integration tests for `/`, `/proxy/health`, static assets, and an SSE
  response through `/proxy`.

### 1.4 Build Three Production Service Wrappers

- [ ] Create wrappers for LiteLLM, gateway, and UI using absolute paths.
- [ ] Load `.env` through the existing safe loader without logging values.
- [ ] Log redacted startup diagnostics: executable paths, working directory,
  locale, and required variable names.
- [ ] Rotate each service log at 5 MB with one backup before process start.
- [ ] Bind every service to `127.0.0.1`.
- [ ] Preserve exit codes so `launchd` can distinguish failure.

### 1.5 Install LaunchAgents

Stable labels:

```text
com.kitty.desktop.litellm
com.kitty.desktop.gateway
com.kitty.desktop.ui
```

- [ ] Generate plists from templates with absolute paths and no secrets.
- [ ] Use `RunAtLoad`, bounded `KeepAlive`, and `ThrottleInterval`.
- [ ] Add fixed `install`, `bootstrap`, `bootout`, `status`, and
  `restart <service|all>` operations.
- [ ] Reject arbitrary labels, paths, and shell arguments.
- [ ] Verify exact HTTP service identity, not only listening ports.
- [ ] Logout/login and then reboot once.
- [ ] Open `http://127.0.0.1:4000` and complete a streamed chat without running
  a Terminal command.

**Exit gate:** after reboot, browser Kitty works without manual startup.

## Slice 2: Close the Capture Loop

**Outcome:** A thought can be captured during total AI failure and Kitty can
bring it back later. No native shell is required yet.

### 2.1 Build the Shared Capture Contract

- [ ] Validate UUID v4, UTC RFC 3339 timestamp, source, text type, 1-10,000
  trimmed characters, `processed:false`, nullable project, and unique tags.
- [ ] Keep `data/inbox.jsonl` immutable.
- [ ] Reserve future processing events for `data/inbox_receipts.jsonl`.
- [ ] Add malformed-line and duplicate-ID fixtures for readers.

### 2.2 Build a Temporary Capture Surface

Use the smallest repo-owned proof surface available on the Mac. A script
invoked by a macOS shortcut is acceptable; Raycast or Hammerspoon may be used
for personal evaluation but must not become a required product dependency.

- [ ] Open a focused text field with no required project/tag decisions.
- [ ] Serialize the complete record before writing.
- [ ] Acquire a sibling advisory lock.
- [ ] Append one line and call `sync_data()` before reporting success.
- [ ] Never log capture text.
- [ ] Confirm capture works with LiteLLM, gateway, and UI stopped.

### 2.3 Add `InboxAdapter`

- [ ] Add the adapter through `gateway/memory_graph.py`; do not bypass the deep
  module from chat or brief code.
- [ ] Read JSONL defensively and skip malformed lines.
- [ ] Select only recent, unprocessed records.
- [ ] Rank by lexical relevance plus recency.
- [ ] Return at most three results under a strict context budget.
- [ ] Include capture ID/source metadata and never mutate the file.
- [ ] Add tests for relevance, recency, malformed records, empty files,
  truncation, and backend failure isolation.

### 2.4 Resurface Without a Review Ritual

- [ ] Verify `unified_context()` can return a relevant capture.
- [ ] Verify the morning brief can mention one useful capture.
- [ ] Instruct synthesis to treat captures as follow-up context, not commands.
- [ ] Add sensitive next-open behavior for `spiraling` /
  `needs_follow_up` tags without promising emergency monitoring.
- [ ] Add a desktop “What am I avoiding?” capture preset for concept testing.

**Exit gate:** a capture made while the stack is down appears appropriately in
later context or the brief after services return.

## Slice 3: Native Tauri Shell

**Outcome:** The intended desktop product replaces the temporary capture
surface.

### 3.1 Scaffold Least-Privilege Windows

- [ ] `main`: external `http://127.0.0.1:4000`, no Tauri IPC capability.
- [ ] `capture`: bundled content, only `save_quick_capture`.
- [ ] `status`: bundled content, only health, log-tail, autostart,
  reveal-path, and bounded restart commands.
- [ ] Rust commands verify the caller's window label.
- [ ] Add capability tests proving `main` cannot invoke privileged commands.

### 3.2 Tray and Shortcuts

- [ ] Add Open Kitty, Quick Capture, What am I avoiding?, Status,
  Launch at Login, bounded restart actions, and Quit.
- [ ] Register `Command+Shift+K` for main Kitty.
- [ ] Register a configurable direct Quick Capture shortcut.
- [ ] Surface shortcut conflicts in Status.
- [ ] Hide windows on close; quitting the shell leaves services running.
- [ ] Enforce single instance.

### 3.3 Native Quick Capture

- [ ] Reuse the Slice 2 contract, lock, append, and durability tests.
- [ ] Focus the text field immediately.
- [ ] Keep project/tags behind optional disclosure.
- [ ] Target open-to-ready below 300 ms on the target Mac.
- [ ] Use Kitty-consistent confirmation/error copy without making AI calls.
- [ ] Remove the temporary capture integration only after parity is proven.

**Exit gate:** both shortcuts, tray, main window, capture, and capability
isolation work while chat is healthy and while chat is down.

## Slice 4: Truthful Operations and Slim Install

**Outcome:** Kitty explains real failures without turning Jacob into its SRE.

### 4.1 Status Model

- [ ] Report exact health identity for UI, gateway, and LiteLLM.
- [ ] Report capture-path writability, auth enforcement, shortcut state, and
  build freshness.
- [ ] Detect port conflicts without killing unknown processes.
- [ ] Show recent restart/flap evidence only if the target macOS
  `launchctl print` output provides a reliable signal.
- [ ] Redact secrets and capture text from all UI and logs.
- [ ] Stay visually quiet while healthy; notify on transition to broken.

### 4.2 Idempotent Installer

- [ ] Preflight exact runtime paths and credentials.
- [ ] Build UI and Tauri in staging before replacing generated artifacts.
- [ ] Install config under
  `~/Library/Application Support/Kitty Desktop/`.
- [ ] Install/bootstrap LaunchAgents and launch the app.
- [ ] Verify health and open Quick Capture as the final first-run action.
- [ ] Make rerunning the installer the documented repair path.
- [ ] Do not build separate transactional rollback machinery in Phase 1.

### 4.3 Refresh and Uninstall

- [ ] `--refresh` rebuilds only after preflight and preserves inbox/log data.
- [ ] Uninstall removes generated jobs/app/config.
- [ ] Preserve `data/` and `logs/` unless explicit `--purge-data` is supplied.

**Exit gate:** installation, repair rerun, refresh, and uninstall are bounded,
truthful, and data-preserving.

## Slice 5: Acceptance and Daily Use

### Automated Verification

- [ ] Full Python suite at or above the recorded live baseline.
- [ ] Kitty UI tests and production standalone build.
- [ ] Rust format, Clippy, unit tests, and capability tests.
- [ ] JSON Schema and concurrent-writer tests.
- [ ] Auth, Host-header, health identity, proxy SSE, freshness, and log-rotation
  tests.

### Failure Injection

- [ ] LiteLLM down.
- [ ] Gateway down.
- [ ] UI down.
- [ ] Wrong process on each port.
- [ ] Missing gateway secret.
- [ ] Malformed `.env`.
- [ ] Missing/moved runtime executable.
- [ ] Read-only inbox directory.
- [ ] Shortcut conflict.
- [ ] Repeated service crash.
- [ ] Tauri app close, quit, and crash.

### Real-System Acceptance

- [ ] Logout/login: services and tray return without Terminal.
- [ ] Reboot: `Command+Shift+K` opens working Kitty.
- [ ] Direct capture shortcut saves while AI is unavailable.
- [ ] A streamed chat works through LiteLLM after reboot.
- [ ] Status is truthful and recovery actions are bounded.
- [ ] Open WebUI is not running or required.

### Daily-Use Exit

- [ ] Use capture on seven consecutive days.
- [ ] Kitty resurfaces at least one capture usefully without manual inbox review.
- [ ] Record friction, false resurfacing, and missed resurfacing.
- [ ] Only then begin Mobile Phase 1.5 implementation or broaden native scope.

## Stop Rules

Stop and revise rather than patch around these conditions:

- LaunchAgent services cannot survive logout/login or reboot reliably.
- The standalone proxy cannot stream through the real LiteLLM chain.
- Desktop gateway can start unauthenticated.
- Capture can report success before durable append.
- Inbox retrieval pollutes unrelated prompts or exposes excessive history.
- External web content receives native capability.
- The installer requires hand repair after an ordinary rerun.

## Definition of Done

Phase 1 is complete only when:

- startup requires no Terminal after reboot
- Tauri provides tray, main shortcut, direct capture shortcut, and launch login
- capture works during complete AI failure
- inbox records are retrieved through `memory_graph`
- Kitty resurfaces captures without a mandatory review ritual
- status reports auth, health, capture availability, and staleness truthfully
- logs rotate and contain no secrets or capture text
- install/refresh/uninstall preserve user data by default
- real logout/login, reboot, failure injection, and seven-day use pass
- no mobile app, cloud auth, push system, voice assistant, or agent expansion
  was built
