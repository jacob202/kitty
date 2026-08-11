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
## Interaction patterns adopted after Buzz review

The Command Center should borrow Buzz's collaboration ergonomics without borrowing its relay/forge architecture.

- **Visible identity:** every task surface names the logical worker (`Codex`, later Builder worker/reviewer) and its role/mode. Use one Command Center Discord app; do not create one Discord bot identity per model or worker.
- **One task, one thread:** a task thread is the human conversation and projection surface. When Gateway-backed tasks arrive, replies inside a participating task thread should steer that task without repeated mentions; the thread-to-task binding remains authoritative in Gateway.
- **At-a-glance activity:** prefer one mutable status item with `state · worker · current meaningful action`. Do not turn tool calls into a scrolling transcript. Silence, timeout, waiting, blocked, and failed are explicit states.
- **Semantic progress:** render what happened and the outcome, not transport details or raw shell commands. Raw logs remain evidence/debug detail, not the headline.
- **Explicit handoffs:** when execution moves from planner → worker → reviewer, show the transition in the thread. The handoff is a projection of Gateway/Builder state, never a Discord-local assignment.
- **Approvals stay external-authority:** Discord may show Approve/Reject controls only for an approval request issued by Gateway/Builder. Approval must carry the authoritative task/plan identity (including `plan_hash` where applicable) and be revalidated by Gateway before action.
- **Outcome cards:** terminal presentation should summarize outcome, worker, PR/artifacts, checks/evidence, blockers, and next action. Every field must come from authoritative evidence; missing fields say unavailable rather than being inferred.
- **Who is working:** a future `/status` or war-room view may list active work as a read-only Gateway projection (`task · state · worker · current action`). No Discord task database or scheduler.
- **Thread lifecycle:** terminal tasks may be archived only after Gateway/Builder reports a terminal state. Discord thread state never closes or completes Builder work by itself.

### Explicit non-copy rules

Do not copy Buzz's relay-as-workspace/event-log ownership, forge/workflow engine, cryptographic agent identity model, branch-as-authoritative-channel model, or broad agent permissions. Do not rely on repeated `@mention` delivery once an agent/task is already participating in a thread; Buzz's current mention/thread bugs are evidence that routing semantics need one authoritative binding rather than duplicated mention filters.