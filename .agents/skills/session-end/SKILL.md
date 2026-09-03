---
name: session-end
description: "Close substantial work completely after verified completion or an explicit end-session request: survey live work, preserve evidence, record execution ownership and KB effectiveness, extract durable knowledge/corrections, record deduplicated workflow signals, update continuity, and leave one honest next action. USE WHEN: substantial assigned work is genuinely complete; session end; end session; wrap up; close session; finish session; save my work; ship it; before you go; finalize session"
---

# Session End — Evidence, Continuity, Measured Learning

Run every step when substantial assigned work is genuinely complete or when the
user signals the session is ending. The user does not need to ask for closeout
after a substantial assignment reaches verified completion. Do not run this for
an ordinary turn, a question, a checkpoint, pending review/CI, or while assigned
work remains. The result is a trustworthy continuation point and a measurable
learning receipt, not a goodbye message.

**The cross-tool KB is `~/kb` (absolute), a separate repository. Never write to
a repo-relative `kb/` path.**

## 0. Verify live state and execution ownership

Never write from memory. Run:

```bash
git branch --show-current
git log --oneline -1
git status --short --branch
```

Classify this session's implementation owner as exactly one of:

```text
interactive | builder
```

Use `builder` only when Builder launched the process with a valid task/packet
bundle or an explicit supported ownership transfer exists and the live lease
agrees. Otherwise use `interactive`.

An interactive review of Builder output remains `interactive`; it does not take
implementation ownership. Record any separate Builder task as parallel work.
Never claim that both lanes owned the same implementation.

## 1. Survey the field

Run:

```bash
bash scripts/session_end_survey.sh
```

Inventory this worktree, every registered worktree, unmerged branches, open PRs
including drafts, Builder's read-only projection, `~/kb/NOW.md`, and carried
recommendations.

Rules:

- `UNAVAILABLE` means unverified, never clean or empty.
- Other workers' branches, worktrees, PRs, and leases remain theirs.
- Builder's absent local DB is unknown/unused, not an empty success.
- A surprising dirty tree is evidence to report, not something to hide.
- Inspect Builder to identify state and collision; do not claim or schedule its
  next packet during an interactive session-end.

## 2. Evaluate carried recommendations safely

For each `deferred` recommendation, run its `release_check` only when it exactly
matches one of these read-only forms:

```text
test -d <path>
test -f <path>
test -e <path>
git merge-base --is-ancestor <sha> <ref>
git rev-parse --verify --quiet <ref>
```

No shell chaining, redirection, substitution, network command, arbitrary
executable, or Builder mutation may auto-run from checkpoint data.

Interpret results:

- exit 0: promote to `ready`;
- exit 1: still deferred; increment `deferred_count`;
- unavailable/invalid execution: carry unchanged and report `UNAVAILABLE`;
- obsolete or superseded work: drop it with evidence.

At three deferrals state: **we have been here before; the stated blocker is
probably not the real blocker.**

## 3. Reconcile exact work evidence

Record only facts verified now:

- session/tool identity and execution owner;
- task/packet/attempt identity when Builder-owned;
- branch, worktree, base SHA, HEAD, and dirty state;
- changed files and commits;
- validation commands and exact results;
- runtime evidence for runtime claims;
- independent review verdict bound to the reviewed SHA;
- PR/check/publication state;
- provider/model/token/spend evidence when available;
- attempts, repair commits, regressions, cleanup state;
- honest failure class and recovery action when incomplete.

For Builder-owned work, attach the final report through supported fenced
commands. Never edit SQLite or infer completion from worker prose.

## 4. Extract durable knowledge and corrections

Write a wiki entry only for a verified reusable fact:

```markdown
# Title
**Source:** <session date and discovering tool/model>
**Date:** YYYY-MM-DD
**Why it matters:** <one sentence>
**Verified:** <command, test, runtime artifact, or source citation>

<finding>
```

Store it under:

```text
~/kb/wiki/YYYY-MM-DD-slug.md
```

Append one line to `~/kb/INDEX.md`.

When Jacob corrected a generalizable mistake, write instead to:

```text
~/kb/corrections/YYYY-MM-DD-slug.md
```

Include the wrong assumption, corrected fact, evidence, and one prevention rule.
Provider/model gotchas belong in `~/kb/models.md`.

Skip ephemera, task shuffling, typo fixes, and facts already owned by canonical
repo docs. When a KB fact becomes proven and load-bearing, promote it into the
appropriate test, skill, ADR, or canonical document and record that destination
in the effectiveness receipt.

If `~/kb` is unavailable, stage the complete payload under
`docs/session-notes/<DATE>-kb-payload.md` and carry a recommendation with
`test -d ~/kb`.

## 5. Record the KB effectiveness receipt

The KB is not considered self-improving merely because agents write to it.
Record whether it was consulted, useful, stale, costly, and associated with a
verified outcome.

Create one JSON payload and run:

```bash
python3 scripts/kb_effectiveness.py record --payload-json '<json>'
```

Required receipt fields:

```json
{
  "schema_version": 1,
  "session_id": "<stable session or attempt identity>",
  "recorded_at": "<ISO timestamp with timezone>",
  "execution_owner": "interactive | builder",
  "tool": "<claude-code | opencode | codex | builder-worker | other>",
  "task_class": "<planning | investigation | code_change | review | recovery | other>",
  "outcome": "accepted | completed_unreviewed | blocked | failed | cancelled | no_op",
  "kb_entries_consulted": [],
  "kb_entries_used": [],
  "kb_entries_stale_or_wrong": [],
  "promoted_to_canonical": [],
  "kb_tokens_loaded": null,
  "total_tokens": null,
  "estimated_cost_usd": null,
  "elapsed_seconds": null,
  "attempts": null,
  "repair_commits": null,
  "regressions": null,
  "first_pass_approved": null,
  "duplicate_work_avoided": null,
  "correction_prevented": null,
  "result_id": null,
  "task_id": null,
  "initiative_id": null,
  "packet_id": null,
  "branch": null,
  "head_sha": null,
  "notes": null
}
```

Rules:

- Never estimate tokens, elapsed time, cost, attempts, review, or regressions
  from intuition. Use `null` when the source is unavailable.
- `schema_version`, `recorded_at`, and `result_id` are required for `accepted`;
  an accepted result ID may occur in only one accepted receipt, so an interactive
  review cannot double-count a Builder implementation.
- `accepted` requires independent acceptance evidence, not self-declaration.
- `kb_entries_used` and `kb_entries_stale_or_wrong` must be subsets of consulted
  entries and may not overlap.
- `duplicate_work_avoided` or `correction_prevented` is true only when there is a
  concrete avoided action/failure to name in `notes`.
- A Builder worker uses Builder's task/attempt/run identity for `session_id`.
- An interactive tool uses its durable session identifier when available;
  otherwise use a stable repository/branch/timestamp identity and do not reuse
  it for a different receipt.
- The recorder is idempotent for identical receipts, rejects a conflicting
  receipt for the same session ID, and hash-chains retained history. That chain
  detects altered or reordered retained entries; the local file is not an
  immutable audit system, so externally retain/export a head when that assurance
  matters.
- Storage is `~/kb/metrics/kb-effectiveness.jsonl`; when KB is unavailable the
  staged fallback is `docs/session-notes/kb-effectiveness.jsonl`.
- Corrupt history, unknown keys, and fabricated zeroes fail loudly.

Then generate the rolling summary:

```bash
python3 scripts/kb_effectiveness.py summary --window-days 30
```

For a human-readable report:

```bash
python3 scripts/kb_effectiveness.py summary --window-days 30 --report
```

The report tracks retrieval usefulness/staleness, known token/cost coverage,
attempts, first-pass approval, regressions, duplicate work avoided, corrections
prevented, canonical-promotion coverage, and KB-used versus no-KB cohorts. Raw
entry and promotion counts are audit coverage, not a score for verbosity. Cohort
comparison is observational and never proves causation.

Do not claim that the KB saves tokens or improves code until the report has
sufficient accepted results, complete enough measurements, and an independently
reviewed comparison. Report all evidence gaps.

## 6. Record workflow-learning signals

Extract zero to three concrete workflow signals and record them through:

```bash
python3 scripts/session_learning.py record --payload-json '<json>'
python3 scripts/session_learning.py summary
```

Signals require stable keys, allowed categories, severity, direct evidence,
impact, one bounded suggested change, source session, and verification method.

Ordinary first occurrences remain observed; repeated signals may promote;
critical/integrity incidents may promote immediately. Promotion is evidence that
a problem deserves ownership, not permission to code.

Before carrying a promoted signal, check the roadmap, Mission, initiative,
queue, branches, worktrees, PRs, and issues for an existing owner. Session-end
does not automatically create an issue or Builder task. At most one promoted,
unowned code improvement may enter the existing recommendation channel.

## 7. Update `~/kb/NOW.md`

Read and merge; do not clobber parallel sessions. Update concrete
accomplishments, blockers, last tool ownership, and promoted-signal ownership.
Prune stale lines older than roughly seven days and keep the file concise.

Do not put the Builder queue in `NOW.md`; link to Builder's supported projection
instead.

## 8. Build ranked recommendations

Produce at most three concrete actions, life before code under ADR 0016. The
highest-ranked ready item becomes `next_action`.

Defer only for a real collision or required artifact and provide one safe
release check. Unrelated parallel work is not a blocker.

A recommendation for an interactive session must not silently mean “take the
next Builder packet.” Builder schedules its own approved queue. An explicit
Builder operator action may be recommended only when the evidence shows a
specific blocked Builder condition requiring intervention.

## 9. Prepare the Global Agent Room handoff

Prepare, but do **not** publish yet, one concise `handoff` or `result` payload for
`workspace_global`. Include only durable facts another agent needs to resume
safely:

- exact outcome and changed paths;
- execution owner plus branch/worktree and current HEAD;
- exact verification/review/publication evidence gathered so far;
- blockers or unavailable evidence;
- one concrete next action;
- explicit `DO NOT REDO` boundaries when useful.

Do not call the draft verified yet. Compatibility writes and final validation
below can change the dirty-path inventory or reveal a failure.

## 10. Write legacy `.claude/HANDOFF.md` compatibility snapshot

While existing validators/adapters still consume it, keep this snapshot minimal
and mirror the prepared room handoff. Include:

- exact outcomes and changed paths;
- this session's execution owner;
- blockers and one next move;
- exact verification results known at this point.

Do not use this file as a multi-agent mailbox or duplicate a long session
narrative into it.

## 11. Write legacy `.claude/STATE.md` compatibility snapshot

Use checkpoint schema version 2 with `parallel_work` and `recommendations`
always present. Include a concise section:

```markdown
## Execution ownership
- this session: interactive | builder
- Builder parallel state: <read-only reference or unavailable>

## KB effectiveness
- receipt: <id/path>
- consulted: <count>
- used: <count>
- stale/wrong: <count>
- token/quality evidence gaps: <truthful list>
```

Requirements:

- at most three recommendations;
- deferred entries have safe release checks; ready entries have null checks;
- `next_action` matches the highest ready recommendation or is an explicit no-op;
- recommendations are compatibility metadata; the relevant `workspace_global`
  handoff/thread is the primary cross-session continuation channel;
- workflow-signal and effectiveness files are evidence history, not backlogs;
- never copy Builder queue state into STATE as an interactive task list.

## 12. Validate continuity and inspect Git

Run:

```bash
python3 scripts/check_continuity_state.py
./kitty context --agent
git status --short --branch
```

Re-read HEAD and the complete dirty-path inventory after those commands. Report
uncommitted files and other workers' changes. Do not commit, push, delete, clean,
release leases, claim Builder work, or merge unless separately authorized or an
approved Builder publication policy permits the bounded action.

## 13. Post the final Global Agent Room handoff

Only now publish the durable room message. Prefer the Agent Room MCP when
configured; otherwise use `./kitty room post --as <identity> --kind handoff
'<content>'`. If a specific registered agent owns the next response, send a
direct message; if continuing an existing discussion, reply to that exact
thread; otherwise broadcast.

The published content must use the final evidence from step 12: exact HEAD,
dirty-path inventory, verification results, PR/publication state, blockers, and
one concrete next action. If validation fails or becomes unavailable, publish a
truthful `blocked` or `failed` result describing that failure; do not post the
pre-validation success draft. Acknowledgement means received, never task
completion.

## 14. Confirm and stop

Report briefly:

1. final Global Agent Room handoff/result message id or an explicit unavailable state;
2. compatibility files written;
3. execution owner and exact task/branch state;
4. next interactive move;
5. deferred items and release conditions;
6. effectiveness receipt ID/path and evidence gaps;
7. workflow signals and status;
8. every unavailable source.

Then stop. Do not start another interactive assignment or Builder packet.
