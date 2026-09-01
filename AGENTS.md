# Repository Guidelines

This file is the compact root contract. `START_HERE.md`,
`docs/reference/CONTEXT_ENGINEERING.md`, and the named skills own the detailed
procedures; do not duplicate them here.

## Prime directive

Fail loud. Raise errors with clear causes. Do not swallow exceptions, invent
defaults, hide unavailable evidence, or add silent recovery. External calls may
retry with a visible warning, then must raise the real error with status,
parameters, and response context.

## Before work

For repository-changing work or stale inherited context, run `START_HERE.md`.
It is the single source for checkout verification, live Git state, the context
receipt, authority reading order, mission/checkpoint freshness, and the final
mutation gate. Use staged loading from
`docs/reference/CONTEXT_ENGINEERING.md`; read only the authority required by
the task. Inspect Builder only when the task involves Builder state, ownership,
execution, or collision risk.

## Global Agent Room

`workspace_global` is the primary mutable cross-agent communication channel for
Kitty work. After checkout/Git verification at start or resume, discover new
work through the unread inbox first. Prefer the Agent Room MCP tools when
configured; otherwise use `./kitty room inbox --as <identity> --unread --json`.
When a handoff or current assignment supplies a durable locator, load that exact
conversation with `room_thread` or `./kitty room thread <message_id> --json`.
Use `room_recent` only for bounded shared situational context; the newest global
window is not an assignment index. If no unread handoff or durable locator
exists and legacy checkpoint fallback is required, run the strict `./kitty
context --agent` receipt and use the checkpoint only when that validation
succeeds. A legacy-skipping receipt never validates a legacy fallback.
Acknowledge messages actually received; acknowledgement means received, not
completed. Use direct messages for a specific owner, broadcasts for shared
context, and replies for an existing thread.

Before ending or handing off substantial work, post a concise verified result or
handoff to the room with exact SHA/evidence, blockers, and next action when
relevant. Publish the final handoff only after final validation so its evidence
matches the state another agent will resume. Mutable handoffs, current-lane
status, and cross-agent questions belong in the room instead of being duplicated
across startup markdown. Do not infer online presence from `registered`. Builder
remains execution/task/lease authority, GitHub issue #490 remains interactive
ownership/collision authority, and Git/GitHub remain publication evidence.

## Scope and code quality

Kitty is a local-first companion. Backend code is in `gateway/`, FastAPI routes
in `gateway/routes/`, the web UI in `gateway/kitty-chat/`, tests in `tests/`,
and product/architecture docs in `docs/`. Runtime data and logs in `data/` and
`logs/` are not source artifacts. Use the existing patterns, keep diffs focused,
prefer editing existing files, and comment the why rather than the obvious.

## Verification

After a meaningful change, run the narrowest relevant checks and report exact
results. Do not run the full suite, lint, typecheck, or build unless the task
asks for it or `/qg`/CI requires it. Runtime, UI, launch, and environment
claims need their corresponding live proof. Never call work complete from
inspection alone; use the final states in `verified-delivery`.

## Reviewer routing

Independent review is reliability-sensitive. Outside an explicitly requested
`--free` Builder lane, use the governed paid OpenRouter reviewer directly instead
of spending time on flaky free-model roulette. Routine reviewer requests force
OpenRouter price-first provider routing and may fall back once to a different
reviewer model if the primary fails cleanly. Keep review read-only and preserve
model-family independence: DeepSeek implementations use MiniMax M3 first and
Qwen 3.7 Plus as the bounded fallback. Explicit `--free` still means zero paid
fallback. Do not depend on Freebuff, 9Router, or any other optional service.
OpenRouter is the preferred router for reviewer routing. AgentRouter is dead; do not recommend it. Freebuff and 9Router are optional only and must never be dependencies. Do not prefer `openrouter/deepseek/deepseek-v4-flash-0731` merely because it is newer; repeated runs observed it stalling.


## Git, credentials, and irreversible actions

The canonical checkout is an observation/integration point, not the default
implementation workspace. Before creating any task branch intended for a PR,
resolve the fresh GitHub `main` SHA and base the task worktree/branch on that
SHA. Do not base new PR work on local `main` unless you have just proven it
equals GitHub `main`; local-only integration commits can silently contaminate
the PR.

Keep small Conventional Commits. Never force-push, rewrite history, delete data,
touch secrets/auth/env, spend money, add a heavy dependency, merge, or push
directly to `main` without explicit authorization. An explicit instruction from
Jacob to implement, fix, continue, or finish a named technical task authorizes
creating an isolated task worktree/branch, committing verified task work, pushing
that non-main branch, and opening or updating its PR. It does not authorize the
higher-impact actions listed above or material scope expansion. Before `gh` or
push, check for an ambient `GITHUB_TOKEN`; prefer `env -u GITHUB_TOKEN gh ...`
when stored auth is valid, and never print credential values. Before merge,
inspect every required Actions check run. A green aggregate status is not enough.

## Builder ownership

Builder owns durable initiative, packet, lease, attempt, worker, review,
recovery, and publication state. Product intent remains in the versioned
Mission. Use supported Builder projections, never infer state from prose or UI
emptiness, and never join Builder tables into another state machine.

Interactive and Builder work are separate lanes. Every implementation has one
owner: `interactive` or `builder`. A manual session does not consume Builder's
queue. Ownership changes only by explicit user instruction or a valid supported
transfer. Never let two lanes implement the same work. Builder workers may use
replaceable tools, but the same worker never approves itself; T0 is automatic,
T1 needs separate model approval, and T2 needs Jacob for publication, deletion,
auth/secrets/env, spending, heavy dependencies, or broad scope.

## Special commands

When the user says bare `next`, `continue`, `resume`, or `do the next thing`,
execute `.agents/skills/next/SKILL.md`: continue only the current interactive
assignment, inspect Builder only for collision awareness, and leave an explicit
no-op when no valid assignment exists. Explicit `builder next`, `builder
status`, or `review builder` are different intents.

When the user says `session end`, `wrap up`, or equivalent, execute
`.agents/skills/session-end/SKILL.md`. It owns the live survey, exact evidence,
KB receipt, continuity updates, learning signals, validation, and stop rule; it
must not create an automatic issue or start another assignment.

For implementation, repair, review, or completion claims, use
`.agents/skills/verified-delivery/SKILL.md`. For modernization or maintenance
cost reduction, use `.agents/skills/aim42-software-improvement/SKILL.md`.

Read-only dependency sources under `.slim/clonedeps/repos/` may be inspected
but not edited.
