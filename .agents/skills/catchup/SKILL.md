---
name: catchup
description: Rebuild working context from live Git and the current assignment after /clear or a fresh session.
disable-model-invocation: true
allowed-tools:
  - Read
  - Bash(git status)
  - Bash(git log *)
  - Bash(git diff *)
  - Bash(git branch *)
  - Bash(git merge-base *)
  - Bash(python3 scripts/work_claim.py *)
---

# Catch Up

Catchup is read-only. It does not post to GAR, write handoff files, select
Builder work, or create continuity state.

## Procedure

1. Read the current conversation/assignment available to this session.
2. Inspect live Git state:

```bash
git status --short --branch
git log --oneline $(git merge-base HEAD origin/HEAD 2>/dev/null || echo HEAD~10)..HEAD
git diff --stat $(git merge-base HEAD origin/HEAD 2>/dev/null || echo HEAD~10)..HEAD
python3 scripts/work_claim.py status
```

3. Read only the changed files needed to explain the current work.
4. If mutable facts matter, refresh their authoritative source.
5. Summarize:

```text
## Catchup: <branch>
Goal: <one line>
Done: <2-4 verified bullets>
In flight: <current dirty/unfinished work or clean>
Next: <single concrete action supported by live state>
Watch out: <real collision/blocker, if any>
```

If there is no current assignment and no branch work to resume, say so. Do not
invent a task from ROADMAP, Builder, GAR, STATE.md, or HANDOFF.md.

`.claude/STATE.md` and `.claude/HANDOFF.md` are preserved compatibility
snapshots only. They are not catchup inputs.
