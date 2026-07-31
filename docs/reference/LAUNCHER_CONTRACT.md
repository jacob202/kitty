# Launcher Contract

**Status:** Active authority
**Ratified:** 2026-07-31
**Owner:** Jacob

This file defines the single launcher contract for Kitty. Production
(`launchd`) and development (`./kitty up`) modes may differ in their
entry points, but both must delegate to shared bootstrap and health logic.
No silent alternate path may serve an unknown build.

## Modes

### Production mode — `launchd`

Entry point: `scripts/desktop/start_ui.sh`
Managed by: `~/Library/LaunchAgents/com.kitty.ui.plist`

### Development mode — `./kitty up`

Entry point: `kitty` CLI script → `gateway/start_gateway.sh` + gateway process

## Required shared properties

Every launch path MUST:

1. **Resolve the repository root** from a portable anchor (not a hardcoded
   absolute path). `start_ui.sh` resolves from `$BASH_SOURCE`; the CLI resolves
   from `$0`.

2. **Source `gateway/lib/load_env_safe.sh`** and load `.env` before any
   service startup.

3. **Check build freshness** before serving. For the UI: if any build input
   (`src/`, `public/`, `package.json`, `package-lock.json`, `tsconfig.json`,
   `next.config.*`) is newer than `.next/BUILD_ID`, a fresh build runs.
   A failed build MUST stop the service — no fallback to stale code.

4. **Expose mode.** `./kitty status` reports the active mode. The launcher
   sets `KITTY_MODE` (`production` or `development`).

5. **Expose source SHA.** The running service reports the Git commit it was
   launched from. `./kitty status` shows this.

6. **Expose build SHA.** The UI build reports the Next.js build ID
   (`.next/BUILD_ID`). Mismatch between source SHA and build SHA must be
   visible.

7. **Expose ports.** The running service reports which ports it binds.
   `./kitty status` shows each port, protocol, and bound interface.

8. **Expose process ownership.** `./kitty status` reports the PID and owner
   of each managed process.

9. **Expose freshness.** If source has changed since the last build but the
   service is still running (e.g., the UI was rebuilt but the service wasn't
   restarted), `./kitty status` must flag this.

10. **Use the shared health endpoint.** Every service exposes `/proxy/health`
    or an equivalent health check. The health gate in the UI waits for this
    before mounting application content.

## Explicit non-paths

These MUST NOT exist in the repository:

- An alternate server entry point that bypasses `start_ui.sh` for production.
- A hardcoded path to a developer's machine.
- A silently-startable service that doesn't report its mode, SHA, or freshness.
- A fallback that serves a pre-built bundle when the build fails.

## Verification

```bash
# Mode, SHA, ports, process ownership, freshness
./kitty status

# Health endpoint (all modes)
curl -s http://127.0.0.1:8000/proxy/health | python3 -m json.tool

# UI build freshness (production mode)
grep -c "build is current" /tmp/kitty-start-ui.log || echo "WARNING: may have rebuilt or failed"
```
