# Multi-Agent Coordination

This is an operational supplement to `AGENTS.md`, not a competing authority.
`AGENTS.md` owns implementation ownership and Builder/Gateway boundaries. This
file defines how concurrent agents discover and coordinate that ownership.

## Live coordination surfaces

Use `workspace_global` for durable cross-agent communication: questions,
handoffs, status, review requests, results, direct messages, and thread replies.
Default to a direct message when one owner needs to act, and reply in the existing
thread when continuing a question, review, or gotcha. Broadcast only when multiple
participants genuinely need the same context. Broadcast status and result messages
are shared context, not assignment inbox items. Acknowledge only messages whose
contents were actually consumed; do not bulk-ACK a stale unread backlog. Replying to
a directly addressed message records receipt of that parent; when no reply is needed,
ACK it explicitly after consumption. Presence is presence only and must never be
treated as ownership.
Use GitHub issue #490 (`[coordination] Kitty campaign live lanes`) for the
authoritative interactive ownership/collision markers. The room does not replace
Builder execution state, #490 ownership, or Git/GitHub publication evidence. Do
not bake temporary campaign facts into this file.

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

## Establish truth before work

Inspect the evidence relevant to the lane before mutation:

- **GitHub truth** — current `main`, PRs, branches, commits, checks.
- **Builder truth** — durable initiative, packet, attempt, review, publication.
- **Local/Mac truth** — worktrees, runtime state, unpublished commits when the
  Mac is available.

Never let prose override fresher durable evidence.

`workspace_global` is the primary mutable handoff source. At start/resume, read
only relevant recent/thread/inbox messages and acknowledge what was actually
received. `.claude/STATE.md` and `.claude/HANDOFF.md` are legacy compatibility
inputs while existing tooling still consumes them. Verify their `head_sha`,
branch, timestamp, and claims before relying on them; they never override fresher
room, GitHub, Builder, or local evidence. Normal implementation work does not
edit them.

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

### INTEGRATE and the mutation gate

`INTEGRATE` covers merge and conflict work, and it needs a claim shape that `OWN`
does not provide. `.githooks/pre-commit` runs `./kitty agent preflight --staged`,
which requires every staged path to sit inside a claimed path fence and to resolve
to a claimed registered resource. There is no `pre-merge-commit` hook, so a clean
merge is not inspected, but a merge finished by `git commit` after resolving a
conflict **is** checked against `git diff --cached` — and that contains every path
the merge brings in, not only the files this lane resolved.

An authored `OWN` fence never covers those incoming paths, so the check cannot be
satisfied that way. Do not answer with `--no-verify`: the gate is satisfiable
honestly, and bypassing it also conceals a real collision. Before the resolving
commit:

1. List the incoming paths:
   `git diff --cached --name-only --no-renames --diff-filter=ACMRD`.
2. Resolve them per resource against the **worktree's** registry copy —
   `resolve_paths_to_resources(paths, registry_path=<worktree>/coordination/resources.yaml)`.
   Resolving against the canonical checkout's copy reports paths as unresolvable
   that resolve fine, because the two copies can differ.
3. Claim each incoming resource with role `INTEGRATE` and the incoming paths,
   keeping `OWN` claims for work this lane authored.

Two mechanics to know: `acquire` returns `CONFLICT` for a resource the calling
session already holds and does not widen paths, so widening means `release` —
which drops every claim for that session — followed by re-claiming; and `release`
itself takes no arguments.

## Adjacent findings and initiative

This section is the canonical normative wording for adjacent-work initiative. Agent skills may summarize it, but should point here rather than duplicate the full policy.

Noticing, inspecting, reproducing, and root-causing problems outside the active
assignment is not a scope violation and does not require mutation ownership.
Read-only investigation is encouraged; use `RESEARCH` only when a sustained
investigation benefits from a visible coordination marker, not as a prerequisite
to curiosity.

When adjacent work appears:

1. **CAPTURE** — send one `workspace_global` message with the useful evidence:
   symptom, exact reproduction, root cause when known, and suggested owner. Send
   it directly to the owning lane when known, otherwise to the room. Capture is
   lightweight and automatic; it does not create Builder queue work and does not
   transfer implementation ownership.
2. **ABSORB** — mutate adjacent work only when it directly serves the current
   assignment's outcome and completion criteria, the collision check above shows
   no valid conflicting owner, and the normal durable mutation ownership is
   established **before editing**. For KX-registered scope this means an active
   mutating `OWN` or `INTEGRATE` claim; `CONFLICT` means handoff, never silent
   takeover. Keep the existing #490/Builder ownership marker semantics. If the
   scope is not registered or ownership cannot be established, capture/handoff
   instead of inventing a drive-by exception.
3. **PREEMPT** — genuine security, data-loss, or P0 findings may reorder capture
   and claim, never skip them. Notify the current owner/coordinator, use the
   supported transfer/reclamation/emergency path, perform only the minimum
   mitigation needed to contain the incident, then hand the lane back. Urgency
   is not a self-declared ownership bypass.

Before any adjacent mutation ask: **Am I still completing my assignment, or
have I just found a more interesting outcome?** The second answer is a handoff,
not a switch. Exploration is never a scope violation; silent lane-switching is.

## Product boundary

Gateway is product truth. KittyBuilder owns durable engineering execution.
Console and Discord consume/project that truth; they do not create independent
execution state machines.

## Handoff and completion

When ownership changes, record only durable facts in `workspace_global` and
update #490 when the interactive ownership/collision marker itself changes:

`OWNER NEXT / VERIFIED STATE / EXACT BASE-HEAD / DONE / DO NEXT / DO NOT REDO / BLOCKERS`

Passing tests or a model reviewer verdict is not sufficient acceptance by
itself. The lead must verify the actual diff against the approved contract and
architecture before merge.

Do not make Jacob manually relay agent state when shared evidence can resolve
ownership. If overlap is discovered, change lanes automatically and continue
useful non-conflicting work.

### Human-only approvals are currently unenforceable, so they are behavioural

Sensitive PRs require "explicit exact-head **human** approval" plus trusted
independent review (`scripts/pr_policy.py`). Mechanically the human half is a
label plus a self-written body line, and neither `_exact_head_approval` nor
`parse_exact_head_override` is actor-bound: both parse text, so any actor able to
edit the body or apply the label can supply them.

The guard that seems obvious — require the approving actor to differ from the PR
author — cannot work here. Every PR is authored by `jacob202`, and agents push,
label, and comment using the owner's own credentials. GitHub therefore cannot
distinguish an approval Jacob wrote from one an agent wrote on his behalf, and no
change to the gate can recover a distinction the platform never recorded.

Until that identity gap is closed, hold to the behavioural rule:

- An agent must not write a `Risk approval:` line or apply
  `review/override-approved` for work it implemented, rebased, or reviewed. It may
  *record* a human's decision in the human's terms after asking; it must not
  originate the decision or infer consent from a general instruction to continue.
- Ask for approval explicitly and at the exact head, and state what is being
  approved. A green gate is not evidence that this rule was followed.
- Self-approval is a process failure even when the gate returns green, and even
  when the change is genuinely good.

Closing the gap needs attributable agent actions: agents operating under a
distinct GitHub identity would make "approval from an actor other than the PR
author and other than the implementing lane" mechanically checkable. That is an
auth/identity change requiring deliberate intent, not an agent's unilateral edit.
