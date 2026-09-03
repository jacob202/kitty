# Launcher Contract

**Status:** Active authority
**Ratified:** 2026-07-31; amended 2026-08-23 (runtime identity + ownership truth)
**Materially revalidated:** 2026-09-03 against `main` `8b4550e20f4fa24bb047adb61d18793b859c2707`; live host process/launchd state was also sampled.
**Owner:** Jacob

This file defines the single **product-runtime** launcher contract for Kitty. Production (`launchd`) and interactive product startup (`./kitty`, `./kitty ui`) may differ in their entry points, but every supported native-UI runtime path must delegate to the shared bootstrap and health logic. Isolated frontend development/test commands may run Next directly, but they are not product-runtime evidence and must not be advertised as the normal phone/desktop launch path. No silent alternate product path may serve an unknown build.

## Verified current state

- The canonical reboot/login supervisor is the three-service generator at
  `scripts/kitty_desktop_launchd.py`, using `com.kitty.desktop.{ui,gateway,litellm}`.
- At the 2026-08-23 E01 host check, none of those LaunchAgents were installed or loaded. A 2026-09-03 live recheck found the same: canonical UI, Gateway, and LiteLLM listeners were manual and the three `com.kitty.desktop.*` jobs were not loaded. Source files therefore do not imply machine-restart coverage.
- `./kitty status` exposes checkout/build/process/launchd provenance fields, but its current freshness classification is **not yet fully authoritative**: nested UI edits can evade the top-level mtime check and macOS Gateway detection has a known false-not-running path. [`KH-RUNTIME-01`](../packets/KH-RUNTIME-01.md) owns that repair. Until it lands, a green/current status is a projection to corroborate, not proof by itself.
- Sibling Kitty worktrees are distinct active ownership domains. A launcher may
  refuse to start while a sibling holds a required port, but `./kitty down`
  must not terminate that sibling merely because it belongs to the same Git
  repository.

## Modes

### Production mode — `launchd`

Entry point: `scripts/kitty_desktop_launchd.py`, whose UI service executes
`scripts/desktop/start_ui.sh` and whose Gateway/LiteLLM services reuse their
canonical start scripts.
Managed by: `~/Library/LaunchAgents/com.kitty.desktop.{ui,gateway,litellm}.plist`
**Host status:** NOT INSTALLED/LOADED at the 2026-08-23 E01 check and again at the 2026-09-03 live recheck. Production mode is defined but was not active on the Mac at either observed point.

### Interactive product mode — `./kitty` / `./kitty ui` / `./kitty up`

- `./kitty` (or `./kitty start`) starts Gateway + LiteLLM, then starts the native UI through `scripts/desktop/start_ui.sh` and opens the local browser.
- `./kitty ui` starts only the native UI through that same bootstrap.
- `./kitty up` starts Gateway + LiteLLM only; it does **not** start the UI.

Required-port conflicts are reported with process/worktree identity instead of being silently reused. On the 2026-09-03 live host sample the stack was running manually rather than under launchd.

## Required shared properties

Every launch path MUST:

1. **Resolve the repository root** from a portable anchor (not a hardcoded
   absolute path). `start_ui.sh` and the CLI both resolve from `${BASH_SOURCE[0]}`.

2. **Share one canonical product UI bootstrap.** `./kitty` / `./kitty start`, `./kitty ui`, and the launchd UI service must use `scripts/desktop/start_ui.sh`. `./kitty up` has no UI responsibility. Isolated frontend development/tests may invoke Next directly, but those processes are not canonical product runtime and cannot support source-freshness or phone-access claims.

3. **Source `gateway/lib/load_env_safe.sh`** and load `.env` before any
   service startup.

4. **Check build freshness** before serving. For the UI: if any build input
   (`src/`, `public/`, `package.json`, `package-lock.json`, `tsconfig.json`,
   `next.config.*`) is newer than `.next/BUILD_ID`, a fresh build runs.
   A failed build MUST stop the service — no fallback to stale code.
   **This check must run on every path, not just `start_ui.sh`.**

5. **Use one host/address consistently for probing and opening.** If health
   is probed at `127.0.0.1:4000`, the browser must open `http://127.0.0.1:4000`,
   not `http://localhost:4000`. The address used for probes must be the address
   the browser loads.

6. **Refuse to launch when a conflicting listener exists.** If any process
   from another Kitty worktree is listening on a required port (IPv4 or IPv6),
   the launcher must report which worktree holds the port and exit non-zero.
   `assert_port_available` must recognize sibling worktrees.

7. **Shutdown must be ownership-safe.** `./kitty down` may terminate manual
   listeners only when their cwd proves they belong to the checkout whose
   launcher was invoked. A sibling Kitty worktree is reported as
   `owned-other-worktree` and left running; an unrelated process is `external`
   and is also left alone. Required-port conflicts are refused rather than
   resolved by killing another lane.

8. **Expose mode, checkout path, source SHA, build SHA, PID, and port** at startup. `./kitty status` must project these for every managed listener.

9. **Expose freshness truthfully.** If source has changed since the last build but the service is still running, `./kitty status` and `./kitty doctor` must agree and flag it; unknown process/build identity must stay unknown. Current implementation does not fully satisfy this property; see `KH-RUNTIME-01`.

10. **Use the shared health endpoint.** Every service exposes `/proxy/health`
    or an equivalent health check. The health gate in the UI waits for this
    before mounting application content.

## Explicit non-paths

These MUST NOT be treated as supported product-runtime behavior:

- An alternate product server entry point that bypasses the shared UI bootstrap.
- A hardcoded path to a developer's machine.
- A silently-startable product service that doesn't report its mode, SHA, or freshness.
- A fallback that serves a pre-built bundle when the build fails.
- A `localhost` hostname used for browser opening when health probes use an explicit IP address.

**Known current violation:** `make ui-tailnet` directly starts `next dev -H 0.0.0.0`, and `./kitty verify-home` still suggests that command when Tailnet reachability fails. It bypasses the canonical UI bootstrap and still cannot make normal `/proxy/*` workflows work remotely because the server-side proxy rejects non-loopback Hosts. This is defect evidence for [`KH-REMOTE-01`](../packets/KH-REMOTE-01.md), not a supported launcher mode.

## Verification

```bash
# Mode, SHA, ports, process ownership, freshness for every managed listener
./kitty status

# The native shell and its full-stack health proxy must answer
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4000/
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4000/proxy/health

# `kitty down` clears only this checkout's owned listeners. A sibling worktree
# or unrelated listener is reported and preserved.
./kitty down
./kitty status

# Conflicting worktree must be detected, not killed.
# (run from a second worktree while the first has port 4000 occupied)
./kitty up  # must refuse and name the owning worktree
```
