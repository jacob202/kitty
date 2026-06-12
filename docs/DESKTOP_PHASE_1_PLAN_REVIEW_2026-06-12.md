# Desktop Phase 1 Plan Review

**Date:** 2026-06-12

**Review mode:** Adversarial architecture, operations, security, and data
integrity review

**Reviewed artifacts:**

- `docs/superpowers/specs/2026-06-12-kitty-desktop-phase-1-design.md`
- `docs/superpowers/plans/2026-06-12-kitty-desktop-phase-1.md`
- `docs/MOBILE_COMPANION_PHASE_1_5.md`

## Verdict

The original direction was correct but the first implementation architecture
was not strong enough for an always-on desktop product.

The revised plan is suitable to implement after Gate 0. It now attacks the
highest-risk assumptions before committing to the full build and uses macOS
service management instead of a hand-built process supervisor.

## Critical Findings

### 1. LiteLLM was missing from the managed service set

**Why it mattered:** Kitty's streaming completion path calls LiteLLM directly
and has no direct-provider fallback. Starting only the gateway and UI would
produce a desktop app that opens after reboot but fails normal streamed chat.

**Resolution:** LiteLLM is now one of three required LaunchAgents and part of
the `ready` health state.

### 2. The custom PID supervisor was structurally fragile

**Why it mattered:** PID reuse, child processes, orphaning, app crashes, login
timing, and restart loops would all become bespoke application code.

**Resolution:** `launchd` owns service lifecycle. Tauri is a client and control
surface.

### 3. The plan had two potential inbox writers

**Why it mattered:** Native capture and a new FastAPI capture route could append
to the same JSONL file concurrently without a shared lock.

**Resolution:** Phase 1 adds no desktop capture API. Tauri is the desktop
writer. The contract remains ready for a future locked mobile import path.

### 4. JSONL durability was underspecified

**Why it mattered:** "Append one line" is not enough to guarantee a complete
durable record during concurrent writes or sudden process termination.

**Resolution:** Serialize first, acquire an advisory lock, perform one append,
call `sync_data()`, then report success.

### 5. `processed: false` had no valid future lifecycle

**Why it mattered:** Rewriting lines conflicts with the append-only design and
introduces race and corruption risks.

**Resolution:** `inbox.jsonl` is immutable. Future processing state goes to
`inbox_receipts.jsonl`.

## High Findings

### 6. Full `node_modules` deployment was unnecessarily heavy

The current UI dependency directory is large. Next.js standalone output can
stage only traced runtime dependencies while retaining the server-side proxy.

### 7. External UI content could accidentally gain native authority

The main Kitty window loads localhost content. A broad Tauri capability would
turn a frontend compromise into local process/filesystem access.

**Resolution:** The `main` window receives no Tauri IPC capability. Capture and
Status use separate bundled windows and narrow commands. Rust commands also
check the calling window label.

### 8. Status could lie about service identity

A listening port is not proof that Kitty owns it.

**Resolution:** Health checks validate exact response identity. Authenticated
health secrets are read only by Rust core into memory and never returned to the
frontend.

### 9. Repo updates could silently leave a stale installed UI

**Resolution:** The installer writes a build manifest with source/dependency
hashes. Status reports staleness and asks for a transactional refresh.

### 10. Installation lacked rollback

An interrupted build or activation could leave the app, UI runtime, and
LaunchAgents out of sync.

**Resolution:** Build in staging, verify, back up current artifacts, promote
atomically, and restore on activation failure.

## Medium Findings

### 11. No uninstall contract

**Resolution:** Uninstall removes generated app/jobs while preserving user data
unless `--purge-data` is explicitly requested.

### 12. Service logs were going to collide

Multiple services writing one log would make incidents hard to attribute.

**Resolution:** Keep `logs/desktop.log` for product lifecycle and separate
service logs under `logs/desktop/`.

### 13. Completion criteria stopped too early

An app build and unit tests do not prove the startup-friction problem is fixed.

**Resolution:** Logout/login and real reboot checks are mandatory. Reboot
acceptance includes a streamed chat response, Quick Capture, and `ready` status.

### 14. The plan began with implementation instead of risk retirement

**Resolution:** Gate 0 proves LaunchAgent behavior, standalone Next proxying,
least-privilege Tauri external windows, and stack-independent durable capture.

## Residual Risks

- The product remains tied to this Mac's repo, Python venv, LiteLLM venv, and
  Node executable.
- A Homebrew or repo move requires refresh installation.
- Local code signing and macOS login behavior still need proof on the actual
  built app.
- Next.js standalone tracing may miss an unexpected runtime asset.
- Provider credentials and credits can still make chat unavailable even when
  all local services are healthy.
- Mobile transport and authentication remain intentionally unresolved.

These are acceptable Phase 1 risks because they are visible, testable, and do
not undermine Quick Capture.

## Recommended Implementation Style

1. Execute Gate 0 before building product polish.
2. Keep each service independently testable.
3. Commit by lifecycle boundary, not by language.
4. Require evidence before marking each gate complete.
5. Do not broaden Phase 1 when a mobile or packaging idea appears.
6. Treat installer, refresh, failure recovery, and uninstall as product
   features rather than release chores.

## Final Recommendation

Proceed with the revised `launchd` plus Tauri architecture.

Do not proceed with the original PID-supervisor architecture. It would create
more future maintenance and failure modes than the desktop product needs.
