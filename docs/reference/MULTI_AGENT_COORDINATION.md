# Multi-Agent Coordination

This is an operational supplement to `AGENTS.md`, not a competing authority.
`AGENTS.md` owns implementation ownership and Builder/Gateway boundaries. This
file defines how concurrent agents discover and coordinate that ownership.

## Live coordination surface

Use GitHub issue #490 (`[coordination] Kitty campaign live lanes`) for changing
campaign state and active lane markers. Do not bake temporary campaign facts
into this file.

Before substantial implementation, publish or refresh a durable marker:

`OWNER / LANE / BASE / OUTPUT / STATUS`

A private chat statement or internal plan is not an ownership claim other
agents can rely on.

## Establish truth before work

Inspect the evidence relevant to the lane before mutation:

- **GitHub truth** — current `main`, PRs, branches, commits, checks.
- **Builder truth** — durable initiative, packet, attempt, review, publication.
- **Local/Mac truth** — worktrees, runtime state, unpublished commits when the
  Mac is available.

Never let prose override fresher durable evidence.

`.claude/STATE.md` and `.claude/HANDOFF.md` are read-mostly historical inputs.
Verify their `head_sha`, branch, timestamp, and claims against current truth
before relying on them. Edit them only when the active packet explicitly owns
those paths.

## Collision rule

Before creating a branch, task, or implementation, check issue #490 plus the
relevant GitHub and Builder/local state.

If another active lane overlaps, choose exactly one:

- **OWN** — continue as the authoritative implementation owner.
- **REVIEW** — inspect the existing implementation.
- **INTEGRATE** — handle CI, conflicts, acceptance, or merge work.
- **DEPENDENCY** — do useful non-overlapping work until the owner unblocks.

Never start a competing implementation merely because the authoritative lane
is temporarily inaccessible.

Never reconstruct unpublished local work from prose, summaries, or remembered
diffs when the original work is recoverable.

## Product boundary

Gateway is product truth. KittyBuilder owns durable engineering execution.
Console and Discord consume/project that truth; they do not create independent
execution state machines.

## Handoff and completion

When ownership changes, record only durable facts:

`OWNER NEXT / VERIFIED STATE / EXACT BASE-HEAD / DONE / DO NEXT / DO NOT REDO / BLOCKERS`

Passing tests or a model reviewer verdict is not sufficient acceptance by
itself. The lead must verify the actual diff against the approved contract and
architecture before merge.

Do not make Jacob manually relay agent state when shared evidence can resolve
ownership. If overlap is discovered, change lanes automatically and continue
useful non-conflicting work.