# Repository Guidelines

## Prime directive

Fail loud, never mask. Raise errors with clear causes; do not swallow exceptions,
return fake defaults, convert unavailable evidence into zero, or add silent
fallbacks. External calls may retry with a visible warning, then must raise the
real error with useful context.

## Cold-start bootloader

Before acting, execute `START_HERE.md`. At minimum:

1. verify this worktree belongs to the canonical `~/Projects/kitty` checkout;
2. inspect live Git state;
3. run `./kitty context --agent` and reject stale or contradictory receipts;
4. follow the canonical reading order and authority map;
5. read `docs/ACTIVE_MISSION.md` and the current session checkpoint;
6. inspect Builder through supported interfaces when execution state matters;
7. treat handoffs and prose as invalid when live evidence disagrees; and
8. verify task scope, execution ownership, facts, and authorization before
   mutation.

## Context engineering default

Use staged context loading per `docs/reference/CONTEXT_ENGINEERING.md`: start
from `./kitty context --agent`, load only the authority needed for the task, and
expand incrementally. For code changes, complete the canonical reading order
before edits.

## Project structure

Kitty is a local-first personal AI companion. KittyBuilder is its execution
control plane: Kitty/strong planning sessions own product intent and packet
authoring; Builder owns execution state (ADR 0017). Backend code lives in
`gateway/`, FastAPI routes in `gateway/routes/`, and path constants in
`gateway/paths.py`. The main UI is `gateway/kitty-chat/`. Tests live in `tests/`.
Product, architecture, and planning docs live in `docs/`. Runtime data and logs
live in `data/` and `logs/` and must not be committed.

See `docs/reference/CODEBASE_MAP.md` for entry points, data flows, state
ownership, and common change locations.

## Commands

- `./kitty up`: start Gateway and LiteLLM locally.
- `./kitty down`: stop local services.
- `./kitty status`: show process and health status.
- `./kitty doctor --json`: run preflight checks.
- `./kitty builder initiative doctor --json`: inspect Builder health.
- `python3 scripts/kb_effectiveness.py summary --window-days 30 --report`:
  report measured KB use and evidence gaps.
- `python3.12 -m pytest tests/ -q --tb=short`: run the default Python suite.
- `cd gateway/kitty-chat && npm run build`: verify the production UI build.
- `cd gateway/kitty-chat && npm test`: run frontend tests.
- `make agent-wrap`: write a session wrap-up template.

## Style

Match existing files before introducing patterns. Python uses 4-space
indentation, explicit errors, and small readable functions. TypeScript/React uses
functional components and clear prop names. Comment the why, not the obvious
what. Keep diffs focused and do not reformat unrelated code.

## Testing

After non-trivial code changes, run the narrowest tests that cover the change and
report exact pass/fail counts. Do not run the full suite, lint, typecheck, or
build mid-session unless explicitly asked with `/qg` or `/qg all`; CI runs those
on every PR and push to main. UI changes require the relevant frontend tests and
build when quality gates are requested. Launch/auth/port/env changes also require
runtime status and doctor evidence.

`CLAUDE.md` states the same rule; change both or neither.

## Git and PRs

Use small Conventional Commit messages. Never push, force-push, rewrite history,
delete files, touch secrets/auth/payments/env, spend money, or add heavy
dependencies without explicit authorization.

Before `gh` or git push, check whether `GITHUB_TOKEN` is set. Prefer
`env -u GITHUB_TOKEN gh ...` when keyring authentication is valid so a stale
ambient token cannot override it. Never print token values.

Before merging, inspect Actions check runs and confirm every required job is
`success`; combined commit status alone is insufficient. After a non-trivial
merge, compile/import the touched files before declaring done.

A GitHub Action may review PRs through OpenRouter. Automated review is not
independent runtime acceptance and quota failures are not approvals.

## KittyBuilder execution control plane

KittyBuilder has durable initiatives, packets, queue state, leases, attempts,
isolated worker runs, validation/review, recovery, budgets, publication rails,
and a bounded read-only projection. Use `./kitty builder --help` and
`docs/KITTYBUILDER_QUICKSTART.md`.

Builder owns execution state, not product intent. The accepted boundary is the
versioned Mission in ADR 0017. Never infer Builder state from handoff prose,
worker narration, or UI emptiness, and never join its SQLite tables into another
state machine.

Under ADR 0021, Builder should proactively select and run eligible approved
packets. A failed packet does not stop unrelated eligible work. Provider
exhaustion pauses durably; it does not fabricate implementation failure or erase
partial evidence.

### Builder workers and interactive tools are different lanes

Builder may launch OpenCode, Claude Code, Codex, or shell adapters as replaceable
workers. Those processes are Builder-owned only when a valid packet/task bundle,
worker identity, and live lease prove it.

A manually opened Claude Code, OpenCode, Codex, or other repo-aware session is
interactive. It may investigate, plan, implement a named task, review Builder,
or perform recovery without consuming Builder's queue.

Every implementation has exactly one execution owner:

```text
interactive | builder
```

Reviewing another lane does not transfer implementation ownership. Ownership
transfer requires an explicit user instruction or supported durable transfer
whose lease agrees. Never let two lanes implement the same work.

### Orca/OpenCode build train

Use Orca worktrees for isolated Builder work and
`scripts/orca_worktree_setup.sh` as the setup hook. Keep
`docs/KITTYBUILDER_ORCA_SETUP.md` as the operating guide.

Default to OpenCode for normal scoped Builder planning/implementation/packaging.
Reserve Codex for high-risk review involving queue state, concurrency,
auth/secrets/env, destructive operations, or blocked escalation. Apply the
compute governor before planning or review dispatch. The same worker never
approves itself.

T0 work may proceed automatically, T1 needs separate model approval, and T2
still needs Jacob: human-branch push/merge, deletes, auth/secrets/env, spending,
heavy dependencies, and broad scope changes.

## Agent rules

Before multi-file work, give a short plan. Prefer editing existing files over
creating new structure.

### Session start

Read `.claude/HANDOFF.md` and `.claude/STATE.md` at every session start, but trust
them only while their branch, HEAD, worktree, PR, and invalidation conditions
remain valid.

### Exact interactive `next` protocol

When the user's instruction is a bare `next`, `continue`, `resume`, `keep going`,
or `do the next thing`, execute `.agents/skills/next/SKILL.md`.

Bare `next` means: continue this interactive session's current assignment. It
must:

1. run the cold-start receipt and live field survey;
2. establish `execution_owner=interactive` unless a valid Builder bundle or
   explicit transfer proves otherwise;
3. continue valid owned interactive work before any new action;
4. inspect Builder only for state/collision awareness;
5. avoid other workers' branches, worktrees, leases, and PRs;
6. verify the bounded interactive result; and
7. leave an explicit no-op when no valid interactive assignment exists.

Bare `next` must not apply an initiative, claim/release/cancel a Builder task,
select the highest-priority packet, run `initiative run-packet`, drain Builder,
or turn a KB signal into execution work.

Explicit phrases are separate intents:

- `builder status`: inspect Builder;
- `builder next` / `take the next Builder packet`: enter Builder's governed
  selection/execution workflow;
- `review builder`: independently review output without taking implementation
  ownership;
- `next`: continue the interactive assignment only.

### Session end protocol

When the user says `session end`, `end session`, `wrap up`, `i'm done`, `save my
work`, or `ship it`, run `.agents/skills/session-end/SKILL.md` in full.

The authoritative skill requires:

1. **Live survey:** worktrees, branches, open PRs including drafts, Builder's
   read-only projection, KB/NOW, and carried recommendations. `UNAVAILABLE` is
   unverified.
2. **Safe recommendation checks:** execute only allowlisted local read-only
   release checks.
3. **Exact evidence:** execution owner, task/attempt when applicable, branch,
   HEAD, changed files, tests, runtime proof, SHA-bound review, PR/check state,
   token/cost evidence, attempts, regressions, and honest failure/recovery.
4. **Durable knowledge:** verified reusable facts to `~/kb/wiki/`, Jacob
   corrections to `~/kb/corrections/`, and proven facts promoted to canonical
   tests/skills/ADRs/docs.
5. **KB effectiveness receipt:** use `scripts/kb_effectiveness.py` to record
   consulted/used/stale entries, known context and total tokens, cost, elapsed
   time, attempts, repair commits, regressions, first-pass approval, avoided
   duplication/corrections, canonical promotions, and evidence gaps.
6. **Workflow signals:** use `scripts/session_learning.py`; signals remain
   evidence, not a queue, and session-end creates no automatic issue/task.
7. **Continuity:** update `~/kb/NOW.md`, HANDOFF, and STATE without clobbering
   parallel work. Leave one interactive next action or explicit no-op.
8. **Validation:** run continuity checks and inspect final Git state.
9. **Stop:** do not start another interactive assignment or Builder packet.

Unknown token, cost, elapsed, quality, or regression data is `null`, not zero.
`accepted` requires independent evidence. KB-used versus no-KB cohort differences
are observational and must never be described as causal proof.

## Cloned dependency source

Read-only dependency repositories may exist under `.slim/clonedeps/repos/`.
Inspect but do not edit them. The GenEvolve clone is an image-planning and
renderer-boundary reference only.
