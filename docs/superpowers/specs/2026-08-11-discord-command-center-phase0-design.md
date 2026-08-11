# Discord Command Center Phase 0 Design

## Outcome

Prove one Discord-to-local-agent path without introducing a second engineering control plane.
A `/vibe <request>` command defers immediately, creates a task thread, launches Codex in a disposable git worktree in advisory read-only mode, streams bounded progress to the thread, and audits the worktree afterward.

## Boundary

Command Center is a replaceable Discord control surface. Phase 0 MUST NOT modify or duplicate KittyBuilder execution ownership, model routing, retries, worktree lifecycle, review, publication, or spend governance.

Allowed implementation surface:
- `integrations/discord_command_center/`
- focused tests under `tests/`
- Command Center documentation

Explicitly out of scope:
- Gateway task projection/state machine
- `/builder/proposals`
- Builder model/cost routing
- `/swarm`, dashboard, approvals, reactions
- any edits to `gateway/builder_*`, `gateway/compute_governor.py`, `opencode.jsonc`, or KittyBuilder adapter scripts

## Components

`config.py` loads only Command Center settings and never logs secret values.
`workspace.py` creates/reaps one detached disposable git worktree per run and returns an explicit diff audit.
`adapters/codex.py` owns strict argv construction for an advisory read-only Codex run. Codex user config is ignored; its internal sandbox is disabled because nested macOS sandboxes prevent its app-server/shell from starting. The outer `sandbox-exec` profile is the OS write boundary.
The adapter also disables Codex apps, plugins, browser/computer use, image generation, and multi-agent features for this Phase 0 local-inspection path.
`runner.py` owns bounded `asyncio.create_subprocess_exec` execution, environment allow-listing, output truncation, and optional macOS `sandbox-exec` containment.
`service.py` composes workspace + runner and makes a non-empty readonly diff a loud `readonly_violation`; violating worktrees are preserved.
`bot.py` is thin Discord wiring: defer first, create private thread, run service, post milestones.

## Safety

- No shell invocation; all child commands are argv arrays.
- Codex read-only is advisory, not trusted as the proof. The prompt forbids mutation, while the outer macOS sandbox prevents writes outside the worktree and the post-run audit detects writes inside it.
- Every run occurs in a disposable git worktree.
- `sandbox-exec` denies writes outside the run worktree while allowing `/dev/null`, required system reads, and network. A macOS behavioral test proves inside-write/outside-deny semantics.
- Post-run `git status --porcelain` is authoritative for mutation detection.
- Clean run worktrees are removed; violating worktrees are preserved and named in the local log only.
- Child environment is an allow-list plus required process basics; Discord token is never passed to Codex. Codex HOME/state is disposable inside the worktree and removed before the git audit; only the existing auth file is linked read-only for startup.
- Default run timeout is 900 seconds; termination escalates from terminate to kill.

## Verification

Unit tests prove command construction, defer-before-execution ordering, diff violation detection, worktree preservation, and output chunking. A local Codex smoke proves the disposable-worktree/diff-audit path. Full Discord acceptance remains blocked until a Discord application/token and test guild are available.