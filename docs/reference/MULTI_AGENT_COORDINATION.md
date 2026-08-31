# Multi-Agent Coordination

This is an operational supplement to `AGENTS.md`, not a competing authority.
`AGENTS.md` owns implementation ownership and Builder/Gateway boundaries. This
file defines how concurrent agents discover and coordinate that ownership.

## Live coordination surface

Use GitHub issue #490 (`[coordination] Kitty campaign live lanes`) for changing
campaign state and active lane markers. Do not bake temporary campaign facts
into this file.

Before substantial implementation, establish a durable ownership marker:

`OWNER / LANE / BASE / OUTPUT / STATUS`

Use the narrowest already-authorized durable surface. Interactive or
GitHub-authorized work may publish or refresh the marker in issue #490. Builder
work that is not authorized to publish to GitHub uses its existing Builder
initiative/task/attempt state as the marker; lack of GitHub publication approval
must never block otherwise authorized Builder work. An authorized coordinator
may later project that Builder state into #490.

For interactive claims in issue #490, include a lease expiry in `STATUS` as
`lease_until=<ISO-8601 timestamp>`. Keep the lease short enough to represent an
active session (normally no more than four hours) and refresh it only while the
lane is actually being worked. Builder work uses Builder's own lease/state and
does not need a second GitHub lease.

A private chat statement or internal plan is not an ownership claim other
agents can rely on.

### Machine-readable interactive claims

New interactive claims should use `scripts/agent_coordination.py`. The script
publishes the same human-readable marker plus a hidden versioned
`kitty-lane:v1` JSON event in issue #490. Legacy prose markers remain evidence
during migration, but only v1 events are machine-enforced claims.

Use the registry before writing:

```bash
python3.12 scripts/agent_coordination.py survey --format markdown
python3.12 scripts/agent_coordination.py claim \
  --lane-id <stable-id> --owner <agent-id> --lane '<scope>' --output '<pr-or-artifact>' \
  --path 'gateway/example/**' --lease-minutes 180
```

`claim` is a dry-run unless `--post` is supplied. A posted `OWN` claim fails
closed if GitHub, git/worktree, PR, or Builder scope evidence is unavailable,
or if a live scope overlaps. After posting it re-reads #490; if another claim
won a concurrent race by durable GitHub ordering, the loser releases itself.

Refresh only while actively working, and release when ownership ends:

```bash
python3.12 scripts/agent_coordination.py refresh --lane-id <id> --owner <agent-id> --post
python3.12 scripts/agent_coordination.py release --lane-id <id> --owner <agent-id> --post
```

Path claims are exact repo-relative paths or deterministic `/**` subtrees.
Arbitrary globs, parent traversal, absolute paths, and empty scopes are invalid.
The registry also projects open PR files, unpublished worktrees, and active
Builder `allowed_paths` as collision evidence. Builder leases remain Builder
authority; the registry never creates a second Builder lease or execution state.

## Establish truth before work

Inspect the evidence relevant to the lane before mutation:

- **GitHub truth** — current `main`, PRs, branches, commits, checks.
- **Builder truth** — durable initiative, packet, attempt, review, publication.
- **Local/Mac truth** — worktrees, runtime state, unpublished commits when the
  Mac is available.

Never let prose override fresher durable evidence.

`.claude/STATE.md` and `.claude/HANDOFF.md` are read-mostly historical inputs.
Verify their `head_sha`, branch, timestamp, and claims against current truth
before relying on them. Normal implementation work does not edit them. The
supported interactive `session-end` workflow may update them as its continuity
output; Builder work edits them only when its packet explicitly owns those
paths.

## Collision rule

Before any substantial implementation, always check issue #490 plus the
relevant GitHub and Builder/local state available to that execution lane. Do
not decide that overlap is unlikely before performing the check. A lane that
cannot mutate GitHub may still read the coordination surface when available and
must use supported Builder/local evidence for collision detection.

Ownership is deterministic. An existing valid owner keeps the lane until an
explicit supported transfer or a valid reclamation. If two overlapping
interactive claims are created before either observes the other, the earliest
unexpired durable claim in issue #490 wins; the later claimant must not select
`OWN`. If durable timestamps cannot establish an order, implementation stops
for that lane until the campaign lead records the authoritative owner. Builder
ownership follows Builder's supported ownership/lease state rather than GitHub
comment ordering.

If another active lane overlaps, choose exactly one:

- **OWN** — continue only when durable evidence identifies this execution lane
  as the authoritative implementation owner.
- **REVIEW** — inspect the existing implementation.
- **INTEGRATE** — handle CI, conflicts, acceptance, or merge work.
- **DEPENDENCY** — do useful non-overlapping work until the owner unblocks.

Never start a competing implementation merely because the authoritative lane
is temporarily inaccessible.

An expired interactive lease is not permission to recreate work. Before
reclaiming it, the campaign lead must inspect the referenced GitHub, Builder,
and available local evidence for recoverable or still-running work. If work is
recoverable, preserve it and use `INTEGRATE` or record an explicit ownership
transfer. If no active execution or recoverable owner work remains, record a
reclamation marker in issue #490 naming the previous owner, the evidence used,
and the new owner before implementation resumes. Age by itself is not enough
to discard work.

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
