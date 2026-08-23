---
name: session-end
description: "Close a work session completely: survey live work, preserve evidence, record execution ownership and KB effectiveness, extract durable knowledge/corrections, record deduplicated workflow signals, update continuity, and leave one honest next action. USE WHEN: session end, end session, wrap up, close session, finish session, save my work, ship it, before you go, finalize session"
---

# Session End — Evidence, Continuity, Measured Learning

When the user signals the session is ending, run every step. The result is a
trustworthy continuation point and a measurable learning receipt, not a goodbye
message.

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

## 9. Write `.claude/HANDOFF.md`

Include:

- exact outcomes and changed paths;
- this session's execution owner;
- in-flight work and other owners;
- blockers and recovery;
- one next move for this interactive assignment;
- deferred items and release checks;
- KB entries consulted/used/stale;
- effectiveness receipt path and evidence gaps;
- workflow signals and owners;
- exact verification results.

## 10. Write `.claude/STATE.md`

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
- recommendations remain the only cross-session next-step channel;
- workflow-signal and effectiveness files are evidence history, not backlogs;
- never copy Builder queue state into STATE as an interactive task list.

## 11. Validate continuity and inspect Git

Run:

```bash
python3 scripts/check_continuity_state.py
./kitty context --agent
git status --short --branch
```

Report uncommitted files and other workers' changes. Do not commit, push, delete,
clean, release leases, claim Builder work, or merge unless separately authorized
or an approved Builder publication policy permits the bounded action.

## 12. Write the command-center digest

`~/Projects/kitty-command-center` is Jacob's operator surface on his Mac, a
sibling of the Kitty checkout and a separate store from `~/kb`. `HANDOFF.md` and
`STATE.md` are written for the next agent; this file is written for Jacob.

Append a new entry to the top of:

```text
~/Projects/kitty-command-center/SESSIONS.md
```

**Never create that directory yourself.** An empty one made inside a container
becomes a convincing-looking command centre holding nothing but this session,
and it dies with the container. When the path is absent, that is a fact to
report, not a gap to paper over: write the identical entry to
`docs/session-notes/<DATE>-command-center.md`, commit it, and say in the final
report that the Mac path was unreachable.

Entry format, newest first, one per session:

```markdown
## YYYY-MM-DD HH:MM <tz> — <one-line outcome>

- **Landed:** <what is true now that was not before, or "nothing">
- **In flight:** <branch / PR number and its state, or "nothing">
- **Broke:** <what failed, and whether it is already fixed, or "nothing">
- **Needs Jacob:** <the exact decision or action, or "nothing">
- **Next move:** <the single next interactive action, or an explicit no-op>
- **Evidence:** <receipt path, test counts, run IDs>
```

Rules:

- Plain language throughout. Jacob does not code and this is the one artifact he
  reads directly; name what a thing does, not the module that holds it.
- Facts verified this session only. Reuse the evidence from steps 3, 5, and 8
  rather than restating intent — a digest that disagrees with `STATE.md` is worse
  than no digest.
- **Needs Jacob** carries only genuine blockers: a required approval, a
  credential, a real collision. Work you could have done yourself never appears
  here.
- Keep the last 10 entries and delete older ones in the same write. This file is
  a rolling board, not an archive, and never a second backlog.
- Never write secrets, tokens, or provider keys.

## 13. Confirm and stop

Report briefly:

1. files written;
2. execution owner and exact task/branch state;
3. next interactive move;
4. deferred items and release conditions;
5. effectiveness receipt ID/path and evidence gaps;
6. workflow signals and status;
7. the command-center digest path actually written;
8. every unavailable source.

Then stop. Do not start another interactive assignment or Builder packet.
