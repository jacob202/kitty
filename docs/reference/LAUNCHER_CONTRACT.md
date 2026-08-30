# Launcher Contract

**Status:** Active authority
**Ratified:** 2026-07-31; amended 2026-08-23 (runtime identity + ownership truth)
**Owner:** Jacob

This file defines the single launcher contract for Kitty. Production
(`launchd`) and development (`./kitty up`) modes may differ in their
entry points, but both must delegate to shared bootstrap and health logic.
No silent alternate path may serve an unknown build.

## Verified current state (2026-08-23)

- The canonical reboot/login supervisor is the three-service generator at
  `scripts/kitty_desktop_launchd.py`, using `com.kitty.desktop.{ui,gateway,litellm}`.
- At the E01 host check, none of those LaunchAgents were installed or loaded;
  the canonical UI, Gateway, and LiteLLM were running manually. Source files
  therefore do not imply machine-restart coverage.
- `./kitty status` reports exact checkout/source authority, dirty state, UI
  build source, process cwd/ownership role, and whether the launchd supervisor
  is actually loaded.
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
**Current host status at the 2026-08-23 E01 check: NOT INSTALLED/LOADED.**
Production mode is therefore defined but was not active on the Mac at that check.

### Development mode — `./kitty up`

Entry point: `kitty` CLI script → canonical Gateway/LiteLLM scripts plus the
native UI startup path.
**Current status at the E01 host check: ACTIVE.** Required-port conflicts are
reported with process/worktree identity instead of being silently reused.

## Required shared properties

Every launch path MUST:

1. **Resolve the repository root** from a portable anchor (not a hardcoded
   absolute path). `start_ui.sh` resolves from `$BASH_SOURCE`; the CLI resolves
   from `$0`.

2. **Share one canonical UI bootstrap.** The `kitty up` path, `launchd` path,
   phone access path, and any other startup path must call the same bootstrap
   function/library. No path may start `next dev` directly while another uses
   `start_ui.sh`.

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

8. **Expose mode, checkout path, source SHA, build SHA, PID, and port**
   at startup. `./kitty status` reports all of these for every managed listener.

9. **Expose freshness.** If source has changed since the last build but the
   service is still running, `./kitty status` must flag this.

10. **Use the shared health endpoint.** Every service exposes `/proxy/health`
    or an equivalent health check. The health gate in the UI waits for this
    before mounting application content.

## Explicit non-paths

These MUST NOT exist in the repository:

- An alternate server entry point that bypasses the shared UI bootstrap.
- A hardcoded path to a developer's machine.
- A silently-startable service that doesn't report its mode, SHA, or freshness.
- A fallback that serves a pre-built bundle when the build fails.
- A `localhost` hostname used for browser opening when health probes use an
  explicit IP address.

## Verification

```bash
# Mode, SHA, ports, process ownership, freshness for every managed listener
./kitty status

# Both loopback addresses must hit the same process
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4000/health
curl -s -o /dev/null -w '%{http_code}' http://[::1]:4000/health

# `kitty down` clears only this checkout's owned listeners. A sibling worktree
# or unrelated listener is reported and preserved.
./kitty down
./kitty status

# Conflicting worktree must be detected, not killed.
# (run from a second worktree while the first has port 4000 occupied)
./kitty up  # must refuse and name the owning worktree
```
