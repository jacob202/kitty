---
name: session-end
description: "Session hygiene — verify live git state, extract knowledge to ~/kb, update ~/kb/NOW.md, write HANDOFF.md and STATE.md, show git status before stopping. USE WHEN: session end, end session, wrap up, wrap up session, close session, finish session, session over, save my work, save and exit, i'm done, ship it, before you go, finalize session"
---

# Session End — Knowledge Base, Handoff, and State

When the user signals the session is ending, execute this checklist. The goal is
to leave the next session with a complete, accurate picture of what happened.

Do NOT stop after writing one file. Run through every step.

**The KB is `~/kb` (absolute) — the cross-tool knowledge base, a separate repo.
Never write to a repo-relative `kb/` path; that forks the knowledge base.**

## 0. Verify live state — never write from memory

```bash
git branch --show-current && git log --oneline -1 && git status --short
```

Test counts, SHAs, and "what's done" come from commands you JUST ran. If the
tree surprises you (parallel sessions exist), report the surprise instead of
writing fiction over it.

## 1. Extract durable knowledge

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

## 2. Update ~/kb/NOW.md

Read `~/kb/NOW.md`. **Merge, don't clobber** — parallel sessions in other tools
exist. Update:
- Which project was worked on
- What was accomplished (the done items, not the todo items)
- What's blocked (with specific reasons, not vague "waiting on X")
- "Which tool touched what last" table

Prune lines older than ~7 days. Keep under 50 lines.
If nothing changed since the last NOW update, say "NOW.md already current."

## 3. Write HANDOFF.md

Write `.claude/HANDOFF.md`. Structure:

```markdown
# Handoff — <one-line summary>

## What was done
- <bullet list of concrete accomplishments, with file paths>

## In-flight / WIP
- <things started but not finished; branches not merged>

## Blockers
- <anything preventing forward progress — be specific>

## Next move
- <the single highest-priority action for the next session>

## Files changed this session
- <paths relative to repo root>

## Verification
- <commands run and their results — evidence, not adjectives>
```

## 4. Write STATE.md

Write `.claude/STATE.md`. Must include the JSON frontmatter block exactly:

```markdown
# Session State — <one-line summary>

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "<ISO timestamp>",
  "head_sha": "<git rev-parse HEAD>",
  "branch": "<current branch>",
  "worktree": "<. or worktree name>",
  "status": "complete | in_progress | blocked | awaiting_review | cancelled | superseded",
  "completed_items": [...],
  "blockers": [...],
  "next_action": "...",
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

## 5. Git status

Run `git status --short --branch` and include the output. Note uncommitted or
dirty files. **Do NOT commit, push, or delete unless the user explicitly asks.**
If other agents' uncommitted work is present, name it — don't claim it.

## 6. Confirm

One-line summary of every file written, then stop. Do not start new work.
