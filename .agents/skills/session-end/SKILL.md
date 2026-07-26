---
name: session-end
description: "Session hygiene — survey all in-flight work, verify live git state, extract knowledge to ~/kb, update ~/kb/NOW.md, write HANDOFF.md and STATE.md with condition-keyed next-step recommendations, show git status before stopping. USE WHEN: session end, end session, wrap up, wrap up session, close session, finish session, session over, save my work, save and exit, i'm done, ship it, before you go, finalize session"
---

# Session End — Survey, Knowledge Base, Handoff, State, Recommendations

When the user signals the session is ending, execute this checklist. The goal is
to leave the next session with a complete, accurate picture of what happened —
and one honest recommendation about what to do next, aware of every other piece
of work in flight.

Do NOT stop after writing one file. Run through every step.

**The KB is `~/kb` (absolute) — the cross-tool knowledge base, a separate repo.
Never write to a repo-relative `kb/` path; that forks the knowledge base.**

## 0. Verify live state — never write from memory

```bash
git branch --show-current && git log --oneline -1 && git status --short
```

Test counts, SHAs, and "what's done" come from commands you JUST ran.

## 1. Survey the field — what else is in flight

```bash
bash scripts/session_end_survey.sh
```

One read-only pass over: this worktree, all worktrees, unmerged branches and the
top-level directories they touch, open PRs **including drafts**, the Builder
queue, `~/kb/NOW.md` cross-tool claims, and any recommendations carried forward
from the previous `.claude/STATE.md`.

Rules for reading it:

- A section that prints `UNAVAILABLE` is **not** a clean result. If `gh` is
  missing or unauthenticated, check open PRs through the GitHub MCP tools before
  writing anything about the PR queue. If you cannot check at all, say the queue
  is unverified — never that it's empty.
- Draft PRs count as in-flight work. A queue is not empty because the drafts
  were filtered out.
- Work in another worktree or on another agent's branch is **theirs**. Name it,
  don't claim it, don't merge it, don't "clean it up."
- If the tree surprises you, report the surprise instead of writing fiction over
  it.

## 2. Evaluate carried recommendations

For each recommendation the survey printed under CARRIED RECOMMENDATIONS, run its
`release_check` command:

- Exit 0 → it's unblocked. Promote it to `ready` and consider it for this
  session's next move.
- Non-zero → still blocked. Carry it forward with `deferred_count + 1`.
- `deferred_count` reaching 3 → say it out loud in chat: *"we've been here before
  — what's actually in the way?"* Three deferrals means the blocker is not the
  real problem. Do not silently defer a fourth time.
- The check no longer makes sense (the branch was deleted, the PR was closed) →
  drop the recommendation and say why in one line.

Never carry a recommendation as prose only. If you can't write a command that
tests whether it's unblocked, it isn't blocked — it's undecided. Say that.

## 3. Extract durable knowledge

Review the session conversation. For anything worth keeping across sessions:

- Write `~/kb/wiki/YYYY-MM-DD-slug.md` — format:
  ```markdown
  # Title
  **Source:** <session date, which model discovered it>
  **Date:** YYYY-MM-DD
  **Why it matters:** one sentence on why this is reusably true
  **Verified:** <how you confirmed it — command output, doc citation, test pass>

  <the finding>
  ```
- Append one line to `~/kb/INDEX.md` under the Wiki section.
- Jacob corrected you in a generalizable way → `~/kb/corrections/YYYY-MM-DD-slug.md`
  (wrong → right → one-line rule) instead of a wiki entry.
- Provider/model gotcha → `~/kb/models.md`.

Skip entries that are:
- Session ephemera (task queue shuffling, typo fixes)
- Things Jacob already knows from identity.md or PREFERENCES.md

**If nothing is durable:** say "No durable knowledge to extract from this session."
**If an extraction comes back empty:** that is a FAILED RUN — say so loudly,
never commit a template. (`~/kb/corrections/seed-opencode-lessons-extraction.md`)
**If `~/kb` is not present** (remote container, fresh machine): do not invent a
path. Stage the payload in `docs/session-notes/<DATE>-kb-payload.md` and record a
recommendation to merge it, with `release_check: test -d ~/kb`.

## 4. Update ~/kb/NOW.md

Read `~/kb/NOW.md`. **Merge, don't clobber** — parallel sessions in other tools
exist. Update:
- Which project was worked on
- What was accomplished (the done items, not the todo items)
- What's blocked (with specific reasons, not vague "waiting on X")
- "Which tool touched what last" table

Prune lines older than ~7 days. Keep under 50 lines.
If nothing changed since the last NOW update, say "NOW.md already current."

## 5. Build the recommendations

Produce **at most three**, ranked. Life projects (job search, benefits,
education, health, money) rank above code projects including Kitty itself —
one small doable step with the why (ADR 0016).

Every recommendation is one concrete action, not a topic. "Reply to the ODSP
letter" beats "sort out benefits." The top-ranked `ready` one becomes
`next_action` in HANDOFF and STATE.

Mark a recommendation `deferred` only for a **real** collision or dependency:

- Another in-flight branch, worktree, or open PR touches the same files or
  subsystem, and doing this now creates a merge conflict or duplicate work.
- It depends on an artifact that work produces (a merged schema, a shipped API,
  a decision recorded in an ADR).

"Other work exists" is not a reason to defer. Unrelated parallel work is not a
blocker, and saying "let that finish first" when nothing actually collides is
how a session ends with zero forward motion.

Every `deferred` recommendation needs a `release_check`: a shell command that
exits 0 exactly when the blocker is gone. Prefer checks that survive a machine
change:

```bash
git merge-base --is-ancestor origin/<branch> origin/main   # branch landed
gh pr view <N> --json state -q '.state=="MERGED"' | grep -q true   # PR merged
./kitty builder queue show <task-id> --json | grep -q '"state": "done"'
test -f <path>                                             # artifact exists
```

## 6. Write HANDOFF.md

Write `.claude/HANDOFF.md`. Structure:

```markdown
# Handoff — <one-line summary>

## What was done
- <bullet list of concrete accomplishments, with file paths>

## In-flight / WIP
- <things started but not finished; branches not merged>

## Other work in flight (not mine)
- <from the survey: whose, which branch/PR/worktree, what it touches>

## Blockers
- <anything preventing forward progress — be specific>

## Next move
- <the single highest-priority action for the next session>

## Deferred, and what releases them
- <id> — <what> — blocked by <what> — unblocks when `<release_check>` exits 0

## Files changed this session
- <paths relative to repo root>

## Verification
- <commands run and their results — evidence, not adjectives>
```

## 7. Write STATE.md

Write `.claude/STATE.md`. Must include the JSON frontmatter block exactly:

```markdown
# Session State — <one-line summary>

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "<ISO timestamp>",
  "head_sha": "<git rev-parse HEAD>",
  "branch": "<current branch>",
  "worktree": "<. or worktree name>",
  "status": "complete | in_progress | blocked | awaiting_review | cancelled | superseded",
  "completed_items": [...],
  "blockers": [...],
  "next_action": "...",
  "parallel_work": [
    {
      "kind": "worktree | branch | pr | builder_task | other_tool",
      "ref": "<branch name, PR number, task id, or tool name>",
      "owner": "<who or what is driving it>",
      "touches": ["<top-level paths>"],
      "observed_at": "<ISO timestamp>"
    }
  ],
  "recommendations": [
    {
      "id": "<stable-kebab-slug — same slug across sessions so it dedupes>",
      "what": "<one concrete action>",
      "why": "<one line>",
      "class": "life | code",
      "status": "ready | deferred",
      "blocked_by": "<null when ready>",
      "release_check": "<shell command exiting 0 when unblocked; null when ready>",
      "deferred_count": 0,
      "first_deferred": "<YYYY-MM-DD or null>"
    }
  ],
  "invalidation_conditions": ["HEAD changes beyond <sha>"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint
<1-2 sentences: branch, SHA, what state the repo is in.>

## Lessons applied
<patterns or gotchas that were relevant this session — bullet list>
```

`recommendations` is the carry-forward channel. It is the ONLY one — do not open
a separate notes file for future session-end runs. Reuse a recommendation's `id`
when re-deferring it so the count is real; a new slug for the same idea resets
the history and hides that it's been stuck for weeks.

Reading an older `schema_version: 1` STATE.md is fine — it simply has no
`recommendations` to carry. Always write version 2.

## 8. Git status

Run `git status --short --branch` and include the output. Note uncommitted or
dirty files. **Do NOT commit, push, or delete unless the user explicitly asks.**
If other agents' uncommitted work is present, name it — don't claim it.

## 9. Confirm

Keep chat short — detail lives in the files. Report:

1. One line per file written.
2. The next move (one line).
3. Anything deferred, with what releases it (one line each).
4. Any survey section that came back `UNAVAILABLE`, so Jacob knows what was
   verified and what wasn't.

Then stop. Do not start new work.
