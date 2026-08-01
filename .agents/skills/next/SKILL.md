---
name: next
description: "Resolve and execute the next authorized Kitty work item end to end. USE WHEN the user's instruction is exactly: next, do the next thing, continue the queue, resume work, or take the next packet."
---

# Next — Resolve, Execute, Verify, Close

This skill turns a short `next` instruction into one deterministic unit of work.
It does not invent a task, trust stale prose, or start a second copy of work that
is already running.

The durable authorities remain unchanged:

- product intent and ordering: `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, and
  approved Mission revisions;
- execution state: KittyBuilder's initiative, packet, task, attempt, event,
  review, and publication records;
- cross-session continuity: `.claude/STATE.md` and `.claude/HANDOFF.md` while
  their receipt remains valid;
- cross-tool learning: `~/kb`;
- Git and GitHub state: live Git and PR/check evidence.

Do not create another backlog, queue, state database, or notes channel.

## 0. Interpret the trigger narrowly

Use this workflow when the user gives a bare continuation instruction such as
`next`. A request naming a specific task follows that task instead.

Do not ask "what should I do next?" until the live authorities have been read
and genuinely leave more than one consequential choice.

## 1. Cold start and field survey

Run the normal bootloader from `START_HERE.md`, including:

```bash
git status --short --branch
./kitty context --agent
bash scripts/session_end_survey.sh
./kitty builder initiative doctor --json
python3 scripts/session_learning.py summary
```

The learning summary is evidence history, not an execution queue. A promoted
signal can only enter selection after existing roadmap, Mission, initiative,
queue, branch, PR, and issue owners have been checked.

A failed or unavailable source stays failed or unavailable. Do not turn it into
an empty queue or a clean result.

Read open PRs including drafts, registered worktrees, unmerged branches, the
Builder projection, `.claude/STATE.md`, `.claude/HANDOFF.md`, `~/kb/NOW.md`, and
the workflow-signal summary when available.

## 2. Continue before starting

Resolve work in this order:

1. A valid non-terminal checkpoint owned by this session/tool.
2. A Builder packet already claimed/running by this worker identity.
3. A blocked/review/publication state that has a concrete recovery action this
   tool is authorized to perform.
4. The highest-priority eligible queued initiative packet whose allowed paths do
   not collide with live work.
5. A promoted workflow-learning signal only when no approved roadmap item,
   Mission packet, queue task, branch, PR, or issue owns the same problem.
6. No-op with an explicit reason when nothing is authorized and eligible.

Never hijack another worker's lease. Never treat unrelated parallel work as a
blocker. A collision exists only when paths, state authority, or a required
artifact overlap.

A promoted signal is not permission to code. Until the governed promotion
adapter ships, it may become at most one structured recommendation for a later
approved packet. Never create a hidden issue or queue task from the summary.

## 3. Ensure the leverage program is materialized

The ratified meta-analysis program is:

```text
docs/initiatives/ktl-001-leverage-and-learning-v1.json
```

Validate and apply it idempotently when it is not already present:

```bash
./kitty builder initiative validate \
  docs/initiatives/ktl-001-leverage-and-learning-v1.json --json
./kitty builder initiative apply \
  docs/initiatives/ktl-001-leverage-and-learning-v1.json --json
```

Applying a byte-identical manifest is safe and must not duplicate tasks. A
manifest conflict is a stop condition: report the existing and proposed hashes;
do not replace the durable initiative in place.

Do not apply a different unapproved manifest merely because it exists under
`docs/initiatives/`.

## 4. Select an eligible packet

Inspect every active initiative, not only the newest one:

```bash
./kitty builder initiative list --json
./kitty builder initiative status <initiative-id> --json
```

For each candidate, inspect the mapped queue task and its allowed paths:

```bash
./kitty builder initiative show <initiative-id> --json
./kitty builder queue show <task-id> --json
```

A packet is selectable only when:

- Builder reports it eligible;
- its queue task is `queued`;
- dependencies are complete;
- its base and manifest identities are valid;
- no active branch, worktree, PR, or leased packet owns overlapping paths;
- required credentials/services are available or the packet explicitly proves
  a failure/offline path without them;
- the action is within the current human authorization boundary.

Rank selectable packets by queue priority, then initiative sequence. Preserve a
human-approved roadmap override when one exists.

## 5. Execute through Builder

Prefer the governed packet runner so work receives an isolated worktree,
recorded attempt, worker brief, validation, independent review, evidence, and
recovery:

```bash
./kitty builder initiative run-packet <initiative-id> <packet-id> --free --watch
```

A paid model, GPU, destructive action, secret/auth/env change, broad dependency,
or human-judgment decision still requires the relevant approval. Do not silently
fall back from a failed free route to paid execution.

When the current interactive tool must execute the packet itself instead of the
free runner:

1. claim the mapped task using a tool-specific worker id;
2. preserve the lease token and claim version;
3. render and follow the Builder brief;
4. transition to `running` with fencing values;
5. work only in an isolated packet branch/worktree and allowed paths;
6. run the packet's exact validation plus the narrowest meaningful tests;
7. attach a structured final report and PR metadata;
8. move through the canonical review/publication states—never edit SQLite or
   fabricate completion.

The same worker never approves its own work.

## 6. Completion means evidence

A packet is not complete because code was written. Require:

- acceptance criteria mapped to observable evidence;
- exact command results and pass/fail counts;
- runtime proof for runtime claims;
- non-vacuous failure proof where required;
- diff/commit identity;
- review bound to the reviewed SHA;
- truthful PR/check/publication state;
- explicit unresolved limitations and cleanup state.

If execution fails, classify it honestly as implementation failure,
infrastructure/provider failure, blocked decision, collision, exhausted budget,
or cancelled work. Preserve the evidence and recovery action.

## 7. Close with session-end

After the selected packet reaches an honest terminal or waiting state, invoke
`.agents/skills/session-end/SKILL.md` in full. Do not merely summarize in chat.

Session end must:

- survey parallel work and the Builder queue again;
- attach/record the final evidence and current state;
- extract durable knowledge and corrections;
- record structured workflow-learning signals;
- update `~/kb/NOW.md`, HANDOFF, and STATE without clobbering parallel work;
- leave exactly one valid next action or an explicit no-op;
- report unavailable evidence instead of rounding up.

Then stop. One `next` instruction executes one bounded continuation cycle; it
does not begin a second packet after session end.
