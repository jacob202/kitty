# Current handoff

Working note for the interactive session in flight. Session-continuity
authority is still `.claude/STATE.md` and `.claude/HANDOFF.md`; per-campaign
phase state lives in `docs/campaigns/<slug>.md`. This file is the scratch
"where am I right now" between checkpoints.

**Updated:** 2026-08-17
**Branch:** `fix/reconcile-run-finalize-and-status-20260817`
**Execution owner:** interactive

## Done

- Post-edit Python lint hook actually runs. It read `$CLAUDE_FILE_PATH`, which
  hooks never receive; the path arrives as `tool_input.file_path` on stdin, so
  it had been a silent no-op. Now `.claude/hooks/format-edited.sh`. (`00b9098f`)
- `voice.md` rewritten for action over discussion. (`9d1806e5`)
- Resumable campaign harness: `scripts/campaign.py`,
  `.claude/commands/campaign-{start,resume}.md`, 14 tests. `verified` is
  unforgeable — it needs a passing command *and* a clean tree, and `audit`
  re-checks every claim against real git objects. (`fd96410b`)
- `./kitty campaign` launcher dispatch, 5 tests. (`d9dc5b0f`)
- Campaign proven end-to-end on that launcher task: 3/3 phases verified,
  resume correctly refused to continue over simulated mid-phase WIP
  (`docs/campaigns/kitty-campaign-cli.md`).
- Three hook bugs in `~/.claude/hooks/`, each committed there:
  - `block-bash-search.sh` hard-blocked `grep`/`find` and redirected to the
    Grep/Glob tools, which are absent in some sessions — no way to search at
    all. Now advisory.
  - `test-throttle.sh` counted narrow single-file runs, the very remedy its
    block message recommends. Now only full-suite runs count.
  - `block-duplicate-read.sh` keyed on path+mtime only, so reading a different
    line range of a file counted as a duplicate. Now keyed by range too.

## In progress

Nothing. Clean tree, campaign complete.

## Next

Jacob asked for three builds, one at a time:

1. **Done** — resumable campaign harness.
2. **Test-gated `/fix` loop** (`.claude/commands/fix.md` + a PreToolUse hook
   warning on a full-suite run before the gate step). Not started. Note the
   throttle hook already covers most of the hook half.
3. **Parallel-lane orchestration** — do *not* build. Already exists as
   KittyBuilder: `gateway/builder_queue_branch_leases.py` is an atomic
   exclusive lease keyed by
   `(initiative_id, packet_id, worker_id, branch, worktree_path)` with
   initiative scoping so duplicate work IDs are impossible;
   `builder_doctor.py`, `builder_pr_janitor.py`, and
   `scripts/start_builder_supervisor.sh` cover doctor and supervisor. Building
   a second one would create the second backlog CLAUDE.md §9 forbids. The real
   gap is discoverability, not capability.

## Known blockers

- 7 worktrees are live and another lane is committing to this branch —
  `a5e2a3d6 fix(launcher): honor PYTHON_BIN in kitty builder` is not from this
  session. Confirm ownership before pushing.
- Nothing pushed. Interactive pushes need Jacob's explicit approval.
