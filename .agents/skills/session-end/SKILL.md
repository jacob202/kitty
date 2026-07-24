---
name: session-end
description: "Session hygiene — write kb/wiki entry, update NOW.md, write HANDOFF.md and STATE.md, show git status before stopping. USE WHEN: session end, end session, wrap up, wrap up session, close session, finish session, session over, save my work, save and exit, i'm done, ship it, before you go, finalize session"
---

# Session End — Knowledge Base, Handoff, and State

When the user signals the session is ending, execute this checklist. The goal is
to leave the next session with a complete, accurate picture of what happened.

Do NOT stop after writing one file. Run through every step.

## 1. Extract durable knowledge

Review the session conversation. For anything worth keeping across sessions:

- Write `kb/wiki/YYYY-MM-DD-slug.md` — format:
  ```markdown
  # Title
  **Source:** <session date, which model discovered it>
  **Date:** YYYY-MM-DD
  **Why it matters:** one sentence on why this is reusably true
  **Verified by:** <how you confirmed it — command output, doc citation, test pass>
  
  <the finding>
  ```
- Append one line to `kb/INDEX.md` under the Wiki section:
  `| YYYY-MM-DD-slug | one-line summary |`

Skip entries that are:
- Session ephemera (task queue shuffling, typo fixes)
- Already captured in a correction (those go to `kb/corrections/` instead)
- Things Jacob already knows from identity.md or PREFERENCES.md

**If nothing is durable:** say "No durable knowledge to extract from this session."

## 2. Update NOW.md

Read `kb/NOW.md`. Update it to reflect:
- Which project was worked on
- What was accomplished (the done items, not the todo items)
- What's blocked (with specific reasons, not vague "waiting on X")
- Any sync changes (new docs, new kb entries, new tools configured)

If nothing changed since the last NOW update, say "NOW.md already current."

## 3. Write HANDOFF.md

Write `.claude/HANDOFF.md`. Structure:

```markdown
# Handoff — <one-line summary>

## What was done
- <bullet list of concrete accomplishments>
- <include file paths where helpful>

## In-flight / WIP
- <things started but not finished>
- <branches that exist but aren't merged>

## Blockers
- <anything preventing forward progress>
- <be specific about what's needed to unblock>

## Next move
- <the single highest-priority action for the next session>
- <optional: 2-3 secondary actions>

## Files changed this session
- <paths relative to repo root>
```

## 4. Write STATE.md

Write `.claude/STATE.md`. Must include the JSON frontmatter block (`<!-- kitty-state ... -->`) exactly as in existing state files. Structure:

```markdown
# Session State — <one-line summary>

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "<ISO timestamp>",
  "head_sha": "<git rev-parse HEAD>",
  "branch": "<current branch>",
  "worktree": "<. or worktree name>",
  "status": "complete | in-progress | blocked",
  "completed_items": [...],
  "blockers": [...],
  "next_action": "...",
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

<1-2 sentences: branch, SHA, what state the repo is in.>

## Lessons applied

<patterns or gotchas that were relevant this session — bullet list>
```

The `status` field: use `complete` if everything shipped, `in-progress` if work continues,
`blocked` if you hit a hard stop.

## 5. Git status

Run `git status --short --branch` and include the output. Note any uncommitted
or dirty files. Do NOT commit unless the user explicitly asks.

## 6. Confirm

After writing all four files, show the user a one-line summary of what was written:
- "Wrote kb/wiki/YYYY-MM-DD-slug.md — <topic>"
- "Updated NOW.md — <what changed>"
- "Wrote HANDOFF.md — <status: complete/in-progress/blocked>"
- "Wrote STATE.md — branch <name> at <short sha>"

Then stop. Do not start new work after completing session hygiene.
