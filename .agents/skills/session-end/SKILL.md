---
name: session-end
description: "Close a work session: survey live work, record KB effectiveness with measurement, update continuity, and leave one honest next action. USE WHEN: session end, end session, wrap up, close session, finish session"
---

# Session End

Close the session with a trustworthy continuation point. Every step produces
evidence for the next session to resume without rediscovery.

**Cross-tool KB is `~/kb` (absolute). Never write to a repo-relative path.**

## 0. Verify live state

```bash
git branch --show-current
git log --oneline -1
git status --short --branch
```

Classify execution owner: `interactive` or `builder`. Use `builder` only when
Builder launched the process with a valid task/packet bundle or an explicit
supported ownership transfer exists. An interactive review of Builder output is
`interactive` — it does not take implementation ownership.

## 1. Survey + continuity

```bash
bash scripts/session_end_survey.sh
python3 scripts/check_continuity_state.py
```

From the survey, extract: this worktree's state, other worktrees' dirtiness,
relevant open PRs, and Builder's read-only projection. From continuity checks,
note mismatches in branch/head/PR state. Other workers' branches and leases
remain theirs. Do not claim or schedule Builder's next packet.

## 2. KB effectiveness receipt

**Only KB-consulted sessions** record a receipt. Sessions that did not consult
the KB at all skip this step.

### 2a. Get measurements

```bash
MEASUREMENTS=$(python3 scripts/opencode_session_measure.py --live)
```

Queries the live OpenCode session database (SQLite, sub-millisecond) for the
current session's running totals: `total_tokens`, `estimated_cost_usd`,
`elapsed_seconds`, `kb_tokens_loaded`. No export needed — the session table
updates in real-time. When the DB is unavailable, all four are null.

### 2b. Record receipt

Build the JSON payload with the fields from 2a plus session metadata:

```bash
python3 scripts/kb_effectiveness.py record --payload-json '<json>'
```

Required: `schema_version`, `session_id`, `recorded_at`, `execution_owner`,
`tool`, `task_class`, `outcome`. Fill measurement fields from 2a; never
estimate. The report is evidence, not decoration.

KB wiki entry: write to `~/kb/wiki/YYYY-MM-DD-slug.md` only when a session
surface verified a provably reusable fact. 99% of sessions skip this. Append one
line to `~/kb/INDEX.md`. Corrections go to `~/kb/corrections/`.
Provider/model gotchas go to `~/kb/models.md`.

Do not run the 30-day summary report here — it adds 2 tool calls for data that
doesn't change between sessions. Run it when the user explicitly asks.

## 3. Rank recommendations

Carry forward ≤2 deferred recommendations from the previous session, evaluating
each `release_check` only if it matches a read-only form (`test`, `git rev-parse`).
Promote to `ready` if the check passes; drop if obsolete with evidence.

Add ≤1 new recommendation. At most 3 total. The highest-ranked ready item is
`next_action`. Defer only for a real collision. Unrelated parallel work is not
a blocker. Never silently mean "take the next Builder packet."

## 4. Write `.claude/HANDOFF.md`

Include exact outcomes, changed paths, execution owner, in-flight work,
blockers, one next move, deferred items with release checks, verification
results, and KB effectiveness receipt ID. Keep it factual — no narrative filler.

## 5. Write `.claude/STATE.md`

Checkpoint schema v2. `parallel_work` and `recommendations` must be present.
At most 3 recommendations. `next_action` matches the highest ready item.

```markdown
## Execution ownership
- this session: interactive | builder
- Builder parallel state: <read-only reference or unavailable>

## KB effectiveness
- receipt: <id or skipped>
- consulted: <count>
- used: <count>
- stale/wrong: <count>
- measurement gaps: <which null fields block ROI proof>
```

## 6. Confirm and stop

Report: files written, execution owner, branch/HEAD, next move, deferred items,
effectiveness receipt ID, and every unavailable source.

Then stop. Do not start another assignment.

## Anti-patterns

- Recording KB effectiveness when you did not consult the KB.
- Filling null-measurement fields with estimates — null is truthful.
- Running the 30-day summary as part of every session-end.
- Running workflow-signal extraction for sessions with zero signals.
- Duplicating survey output in continuity validation.
- Claiming Builder work during an interactive session-end.