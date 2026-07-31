# Launcher Contract

**Status:** Active authority
**Ratified:** 2026-07-31; amended 2026-07-31 (competing-launcher finding)
**Owner:** Jacob

This file defines the single launcher contract for Kitty. Production
(`launchd`) and development (`./kitty up`) modes may differ in their
entry points, but both must delegate to shared bootstrap and health logic.
No silent alternate path may serve an unknown build.

## Verified current state (2026-07-31)

- No `com.kitty.ui` launch agent is installed or loaded. `start_ui.sh`
  is never invoked.
- Two Next servers from different Kitty checkouts simultaneously occupy port
  4000: canonical checkout (Next 16.2.6, IPv4 `127.0.0.1:4000`) and piddock
  worktree (Next 16.2.11, IPv6 `*:4000`).
- `kitty` probes `127.0.0.1:4000` but opens `http://localhost:4000` in the
  browser. On macOS, `localhost` prefers IPv6, so the health check validates
  the canonical checkout and the browser displays the piddock one.
- `pid_owned_by_kitty()` (`kitty:90-95`) scopes "Kitty-owned" to the
  `$KITTY_ROOT` of the currently-running script. `./kitty down` from the
  canonical checkout leaves piddock worktree listeners running.
- `kitty` starts `next dev` directly at line 680 — it never calls
  `start_ui.sh`, so the #328 freshness fix is on an unused code path.

## Modes

### Production mode — `launchd`

Entry point: `scripts/desktop/start_ui.sh`
Managed by: `~/Library/LaunchAgents/com.kitty.ui.plist`
**Current status: NOT INSTALLED.** The launch agent does not exist, so
production mode is not active.

### Development mode — `./kitty up`

Entry point: `kitty` CLI script → `gateway/start_gateway.sh` + gateway process
**Current status: ACTIVE** but suffers the probe/open mismatch and worktree
collision documented above.

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

7. **Shutdown must recognize all Kitty worktrees.** `./kitty down` must stop
   listeners from any Kitty worktree, not only the one whose `kitty` script
   was invoked. `pid_owned_by_kitty` must accept any path under a known Kitty
   checkout root. As a minimal heuristic: a process is Kitty-owned if its
   command line or cwd contains any path that looks like a Kitty worktree
   (contains `kitty` as a Git repo and has a `gateway/kitty-chat` directory).

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

# `kitty down` from any worktree must clear all Kitty listeners
lsof -iTCP:4000 -sTCP:LISTEN  # must be empty after `./kitty down`

# Conflicting worktree must be detected
# (run from a second worktree while the first has port 4000 occupied)
./kitty up  # must refuse with "port 4000 occupied by Kitty worktree at /path/to/other"
```
