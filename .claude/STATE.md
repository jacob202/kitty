# Session State — Packet B2-worker-session-seam (wired WorkerSession through run-packet CLI)

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-01T00:00:00Z",
  "branch": "kittybuilder/kb_msb4yx3l_caea",
  "worktree": "kittybuilder",
  "status": "completed",
  "completed_items": [
    "Added --worker-session (shell|opencode) flag to `initiative run-packet` with --opencode-base-url/--opencode-api-key",
    "Added _resolve_worker_session production construction site and wired worker_session through _cmd_initiative_run_packet into run_packet",
    "Added tests in test_builder_adapters.py proving shell and opencode dispatch through the public CLI entry point"
  ],
  "blockers": [],
  "next_action": "await Builder validation/review of packet attempt",
  "parallel_work": [],
  "invalidation_conditions": []
}
-->

## Execution ownership

- this session: builder (packet `B2-worker-session-seam`, attempt 1)
- lease branch `kittybuilder/kb_msb4yx3l_caea`, worktree `kittybuilder`

## Summary

Wired the existing `WorkerSession` abstraction (ShellWorkerSession / OpenCodeServerSession)
through the supported CLI path. `run_packet` (builder_loop) already accepted and dispatched
`worker_session`; the seam was unconnected at the CLI boundary. Added `--worker-session`
flag to `initiative run-packet`, a single production resolver `_resolve_worker_session`
(shell wraps `--worker-command`; opencode talks HTTP to a headless server), and passing the
resolved session into `run_packet`. Proved both backends construct and dispatch through the
public CLI entry point with new tests.
