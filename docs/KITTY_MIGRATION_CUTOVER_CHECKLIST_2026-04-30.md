# Kitty Migration Cutover Checklist

Date: 2026-04-30
Status: checkpoint ready

## Completed

- [x] Preflight status is `READY`.
- [x] Copy-first workspace refreshed from current `main`.
- [x] Copied app gate passes (`92 passed`).
- [x] Copied app launch smoke verified (`KITTY_PORT=5004`).
- [x] Migration start report written.
- [x] Runtime-manifest and operations docs updated for `kitty-system/kitty-app`.
- [x] Full smoke from `kitty-system/kitty-app` using `scripts/golden_demo.sh` (non-strict chat mode).

## Pending

- [x] Final cutover decision: make `kitty-system/kitty-app` the daily execution path for workers.
- [x] Update remaining control docs pointing at `/Users/jacobbrizinski/Projects/kitty` as authoritative runtime.
- [x] Add one rollback command block and one forward command block to `SESSION_SUMMARY.md`.
- [x] Decide retirement criteria for legacy path (do not delete yet).

## Legacy Path Retirement Criteria

- Two consecutive daily runs from `kitty-system/kitty-app` pass routes + gates.
- No active open loop depends on legacy-only paths.
- User explicitly approves retirement in writing.

## Rollback

If cutover causes issues, use legacy checkout immediately:

```bash
cd /Users/jacobbrizinski/Projects/kitty
./kitty status
```
