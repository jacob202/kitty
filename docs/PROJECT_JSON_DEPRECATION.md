# project.json Deprecation Notice

## Status: DEPRECATED (migration to CURRENT_FOCUS.md in progress)

**Date:** 2026-05-09  
**Decision:** `project.json` is being phased out. Use `CURRENT_FOCUS.md` as source of truth for project state.

---

## What Changed

### Before (Stale):
```json
{
  "milestones": [
    {"id": 1, "status": "completed", "tasks": [...]},
    ...
  ]
}
```

### Now (Live):
Use `CURRENT_FOCUS.md` instead:
```markdown
## Active Phase
Phase 4 — Jacob-Only Build

## Today's Progress
- ✅ Fixed bug X
- ✅ Added feature Y

## Working Commands
- /optimize, /cleanup, ...
```

---

## Migration Path

### ✅ Already Done:
1. Created `src/core/project_state_reader.py` to read from CURRENT_FOCUS.md
2. Updated `generate_project_brief()` to use reader (not stale JSON)
3. Added `/phase` command (reads from CURRENT_FOCUS)
4. Added `/next` command (reads from TASKS.md)
5. 530 regression tests passing

### 🔄 Still To Do (low priority):
1. Audit remaining `project.json` references in code
2. Decide: keep it as optional backup or fully remove?
3. Update any remaining PM tools that still write to `project.json`

---

## Why This Matters

| Aspect | project.json | CURRENT_FOCUS.md |
|--------|---|---|
| **Freshness** | Stale (old JSON) | Live (updated at session end) |
| **Who maintains** | Unclear | Agents (explicit) |
| **Readability** | JSON (machine) | Markdown (human) |
| **Used by** | Old brief code (now deprecated) | `/brief`, `/phase`, `/next` |
| **Governed by** | AGENTS.md (source of truth rule) | ✅ YES |

---

## Action for Agents

### Keep using CURRENT_FOCUS.md, ignore project.json:
```bash
# Good ✅
cat CURRENT_FOCUS.md
./kittybuilder --brief

# Not recommended ❌
cat project.json
# (will be removed eventually)
```

### If you touch project state code:
Check if it's reading from `project.json`:
- If yes → Consider using `project_state_reader.py` instead
- If updating state → Update `CURRENT_FOCUS.md` at session end (not JSON)

---

## Questions?

- **Can I still use project.json?** Yes, but it will be stale
- **When will it be removed?** Unknown (low priority; safe to coexist for now)
- **What should I read?** CURRENT_FOCUS.md (and TASKS.md for next steps)

---

## Related Docs

- `AGENT_HANDOFF_SESSION_TEMPLATE.md` — How to update CURRENT_FOCUS at handoff
- `src/core/project_state_reader.py` — Unified reader for state docs
- `docs/DECISIONS.md` — If you want to formally decide to delete project.json
