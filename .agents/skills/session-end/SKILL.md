---
name: session-end
description: "Close a work session completely: survey all live work, evaluate carried recommendations, preserve evidence, extract durable knowledge and corrections, record deduplicated workflow-learning signals, update ~/kb/NOW.md, write valid HANDOFF/STATE checkpoints, and leave one honest next action. USE WHEN: session end, end session, wrap up, close session, finish session, save my work, ship it, before you go, finalize session"
---

# Session End — Evidence, Continuity, Learning, Next Action

When the user signals the session is ending, run every step. The output is a
trustworthy continuation point, not a goodbye message.

Do not stop after writing one file. Do not begin new implementation after the
final confirmation.

**The cross-tool KB is `~/kb` (absolute), a separate repository. Never write to
a repo-relative `kb/` path.**

## 0. Verify live state

Never write from memory. Run:

```bash
git branch --show-current
git log --oneline -1
git status --short --branch
```

Test counts, SHAs, PR state, queue state, and completion claims come from
commands or connected-source reads performed now.

## 1. Survey the field

Run:

```bash
bash scripts/session_end_survey.sh
```

It inventories:

- this worktree and every registered worktree;
- unmerged branches and touched top-level paths;
- open PRs including drafts;
- Builder's read-only status projection;
- `~/kb/NOW.md` cross-tool claims;
- recommendations carried from the previous `.claude/STATE.md`.

Rules:

- `UNAVAILABLE` means unverified, never clean or empty.
- If `gh` is unavailable, use the GitHub connector before writing PR claims. If
  neither source works, report the PR queue unverified.
- Other workers' branches, worktrees, PRs, and leases remain theirs. Name them;
  do not claim, merge, release, or clean them.
- Draft PRs count as in-flight.
- A surprising dirty tree is evidence to report, not something to hide.
- Builder's absent local DB is unknown/unused, not an empty success.

## 2. Evaluate carried recommendations safely

Read the survey's `CARRIED RECOMMENDATIONS` section.

A `ready` recommendation has no release check. Carry it forward or supersede it
with explicit evidence.

For each `deferred` recommendation, run its `release_check` only when it exactly
matches one of these read-only forms:

```text
test -d <path>
test -f <path>
test -e <path>
git merge-base --is-ancestor <sha> <ref>
git rev-parse --verify --quiet <ref>
```

No shell chaining, redirection, substitution, arbitrary executable, `gh`, or
Builder command may auto-run from tracked checkpoint data. Show Jacob anything
outside the allowlist and obtain approval first.

Interpret results:

- exit 0: promote to `ready`;
- exit 1: still deferred; increment `deferred_count`;
- command missing, auth/network failure, signal, or otherwise could not run:
  carry unchanged, do not increment, and report `UNAVAILABLE`;
- obsolete check or deleted/superseded work: drop it and state why.

At three deferrals say explicitly: **we have been here before; the stated
blocker is probably not the real blocker.** Do not silently defer it a fourth
time under a new slug.

## 3. Reconcile the work completed this session

Before knowledge extraction, establish the exact outcome:

- packet/task/attempt identity when Builder-owned;
- branch, worktree, base SHA, HEAD, and dirty state;
- files changed;
- validation commands and exact results;
- runtime evidence for runtime claims;
- review verdict bound to the reviewed SHA;
- PR/check/publication state;
- provider/model/spend and cleanup state when applicable;
- honest failure class and recovery action when incomplete.

Attach the final report/evidence to Builder through supported commands when this
was a Builder packet. Never edit SQLite or infer terminal state from worker
prose.

## 4. Extract durable knowledge and corrections

Review the session for facts useful beyond this one task.

Write a wiki entry when a reusable fact was verified:

```markdown
# Title
**Source:** <session date and discovering tool/model>
**Date:** YYYY-MM-DD
**Why it matters:** <one sentence>
**Verified:** <command, test, runtime artifact, or source citation>

<finding>
```

Location:

```text
~/kb/wiki/YYYY-MM-DD-slug.md
```

Append one line to `~/kb/INDEX.md`.

When Jacob corrected a generalizable mistake, write instead:

```text
~/kb/corrections/YYYY-MM-DD-slug.md
```

Include wrong assumption, corrected fact, evidence, and a one-line prevention
rule. Provider/model gotchas belong in `~/kb/models.md`.

Skip session ephemera, task shuffling, typo fixes, and facts already owned by
identity/preferences files.

If nothing is durable, state that explicitly. An empty template is a failed
run—never commit it.

If `~/kb` is unavailable, stage the complete payload under
`docs/session-notes/<DATE>-kb-payload.md` and carry a recommendation with:

```text
test -d ~/kb
```

## 5. Record workflow-learning signals

The workflow should improve from evidence without creating a new backlog or
turning every annoyance into engineering work.

Extract **zero to three** concrete signals. A valid signal requires:

- a stable kebab-case key that is reused for the same failure across sessions;
- one allowed category;
- severity;
- concise summary;
- direct evidence;
- user/project impact;
- one bounded suggested change;
- source session;
- how it was verified.

Allowed categories are enforced by `scripts/session_learning.py` and include:

```text
architecture_boundary, collision, data_loss_risk, duplicate_work,
fabricated_success, manual_repetition, missing_automation, paid_waste,
provider_failure, queue_integrity, runtime_failure, security_boundary,
stale_context, test_gap, tool_failure, unverified_claim, user_correction
```

Record each signal:

```bash
python3 scripts/session_learning.py record --payload-json '<json>'
```

Then summarize the rolling 30-day window:

```bash
python3 scripts/session_learning.py summary
```

Storage:

- normal: `~/kb/workflow-signals/`;
- KB unavailable: `docs/session-notes/workflow-signals/`.

Promotion is conservative:

- immediate: critical severity or data-loss, fabricated-success, paid-waste,
  queue-integrity, or security-boundary incident;
- repeated: same stable key in at least two sessions within 30 days;
- observe: first ordinary occurrence.

Before turning a promoted signal into a recommendation, check the roadmap,
active Mission, initiative manifests/status, queue, open PRs/issues, and current
parallel work. If an owner already exists, link the signal to that owner and do
not create another task.

Session-end does **not** automatically create a GitHub issue or Builder task.
The governed promotion adapter may later create at most one task per stable key.
Until then, carry at most one promoted, unowned code improvement through the
existing recommendation channel.

Do not record vague signals such as "UX could be better" or "tests were
annoying." Do not reward verbosity, agent self-narration, commit counts, or
subjective model preference.

## 6. Update `~/kb/NOW.md`

Read and merge; do not clobber parallel sessions.

Update:

- project worked on;
- concrete accomplishments;
- exact blockers;
- which tool touched what last;
- newly promoted workflow signal and its existing owner, when any.

Prune stale lines older than about seven days and keep the file under roughly
50 lines. If no change is needed, say `NOW.md already current.`

## 7. Build ranked recommendations

Produce at most three. Life projects outrank code projects under ADR 0016.
Every recommendation is one concrete action with one reason.

The highest-ranked `ready` item becomes `next_action`.

Mark an item `deferred` only for a real collision or required artifact:

- overlapping branch/worktree/PR/leased packet;
- a schema/API/decision/evidence artifact that does not yet exist.

Unrelated parallel work is not a blocker. "Other work exists" is not a valid
reason to wait.

Every deferred item requires one allowed `release_check`. A PR or Builder state
that cannot be checked through the safe local allowlist must be verified by a
human/tool read and written with its current status; never smuggle network or
queue mutation into the release check.

Reuse the same recommendation `id` across sessions. A new slug for the same
stuck item falsifies its deferral history.

At most one promoted workflow-improvement signal may appear in the three
recommendations, and only when no existing owner was found.

## 8. Write `.claude/HANDOFF.md`

Use this structure:

```markdown
# Handoff — <one-line summary>

## What was done
- <concrete outcomes and paths>

## In-flight / WIP
- <started but incomplete work>

## Other work in flight (not mine)
- <owner, branch/PR/task/worktree, touched paths>

## Blockers
- <specific cause and recovery>

## Next move
- <single highest-priority action>

## Deferred, and what releases them
- <id> — <action> — blocked by <cause> — `<release_check>`

## Workflow learning
- <signals recorded, promotion status, existing owner or unowned>

## Files changed this session
- <repo-relative paths>

## Verification
- <exact commands and results>
```

The parallel-work inventory must agree with STATE.

## 9. Write `.claude/STATE.md`

Always write checkpoint schema version 2:

```markdown
# Session State — <one-line summary>

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "<ISO timestamp with timezone>",
  "head_sha": "<full SHA>",
  "branch": "<branch>",
  "worktree": "<. or worktree name>",
  "status": "complete | in_progress | blocked | awaiting_review | cancelled | superseded",
  "completed_items": [],
  "blockers": [],
  "next_action": "<one concrete action or explicit no-op>",
  "parallel_work": [
    {
      "kind": "worktree | branch | pr | builder_task | other_tool",
      "ref": "<identity>",
      "owner": "<owner>",
      "touches": ["<paths>"],
      "observed_at": "<ISO timestamp>"
    }
  ],
  "recommendations": [
    {
      "id": "<stable-kebab-slug>",
      "what": "<one concrete action>",
      "why": "<one line>",
      "class": "life | code",
      "status": "ready | deferred",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": ["HEAD changes beyond <sha>"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint
<one or two sentences>

## Lessons applied
- <relevant durable rules>

## Workflow learning
- <stable key, observe/promote, owner or unowned>
```

Requirements:

- `parallel_work` and `recommendations` are always present; use `[]` when truly
  empty;
- at most three recommendations;
- deferred entries have safe release checks; ready entries have null checks;
- recommendation ordering is life before code;
- `next_action` matches the highest ready recommendation or is an explicit
  no-op;
- populate `pull_request` when next/invalidation depends on PR state;
- `recommendations` remains the only carry-forward recommendation channel;
- workflow-signal files are evidence history, not another execution backlog.

## 10. Validate continuity and inspect Git

Run:

```bash
python3 scripts/check_continuity_state.py
./kitty context --agent
git status --short --branch
```

Report uncommitted files and any other worker's changes. Do not commit, push,
delete, clean, release leases, or merge unless the user explicitly authorized
that action or an approved Builder packet's publication policy permits it.

## 11. Confirm and stop

Keep chat brief because detail lives in the artifacts. Report:

1. one line per file written;
2. exact packet/task/branch state;
3. the next move;
4. each deferred item and release condition;
5. workflow signals recorded and whether observed/promoted/suppressed;
6. every survey or evidence source that was `UNAVAILABLE`.

Then stop. Do not start another packet.
