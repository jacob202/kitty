# Session State — Packet B2-worker-session-seam (WorkerSession wired through run-packet CLI)

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-01T00:00:00Z",
  "branch": "kittybuilder/kb_msb4yx3l_caea",
  "worktree": "kittybuilder",
  "status": "completed",
  "completed_items": [
    "Added --worker-session (shell|opencode) flag to `initiative run-packet` with --opencode-base-url/--opencode-api-key",
    "Added _resolve_worker_session single production construction site, wired worker_session through _cmd_initiative_run_packet into run_packet",
    "Wrote mode-specific resolution: opencode uses no subprocess, shell wraps --worker-command",
    "Added tests in tests/test_builder_adapters.py proving shell and opencode construction + dispatch through the public CLI entry point"
  ],
  "blockers": [],
  "next_action": "await Builder validation/review of packet attempt",
  "parallel_work": [],
  "invalidation_conditions": []
}
-->

## Execution ownership

- this session: builder (packet `B2-worker-session-seam`, attempt 4)
- lease branch `kittybuilder/kb_msb4yx3l_caea`, worktree `kittybuilder`

## Summary

Wired the existing WorkerSession abstraction through the run-packet CLI public
entry point. `run_packet` (builder_loop) already accepted and dispatched
`worker_session`; the seam was unconnected at the CLI boundary. Added a
`--worker-session` flag (choices shell|opencode) to `builder initiative
run-packet` with supporting --opencode-base-url/--opencode-api-key flags, a
single production resolver `_resolve_worker_session` (gateway/builder_cli.py)
that constructs ShellWorkerSession (wrapping --worker-command) or
OpenCodeServerSession (HTTP to a headless server), and threaded the resolved
session into builder_loop.run_packet via worker_session=. Mode-specific
resolution: opencode runs without a subprocess command; shell requires
--worker-command. Default (no flag) behaviour is unchanged and still runs the
subprocess backend. No production code constructs a WorkerSession through a
test-only path; _resolve_worker_session is the sole construction site.

Verification (attempt 4):
- tests/test_builder_adapters.py + tests/test_worker_session_contract.py: 103 passed
- builder queue/loop/runner/run/attempt/cli regression tests: 491 passed
