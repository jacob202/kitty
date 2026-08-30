# Agent Handoff: Session Template

**Purpose:**  Before exiting a session, update CURRENT_FOCUS.md with completed work, next steps, and blockers. This ensures the next agent starts with complete context.

---

## Session Handoff Checklist

When your session is complete, update `CURRENT_FOCUS.md`:

### 1. **Update "Last updated" date**
```markdown
Last updated: 2026-05-09  # ← Change to today's date
```

### 2. **Update "Today's Progress" section**
Add 2-5 bullet points of what YOU accomplished:
```markdown
## Today's Progress (May 8-9)
- ✅ Fixed X bug (related to Y)
- ✅ Added /command to dispatcher (wired to handler)
- ✅ Consolidated PM tools to use CURRENT_FOCUS.md
- ✅ Added 12 regression tests (530 tests passing)
```

### 3. **Update "Working Commands" section**
List ALL commands that actually work (verified):
```markdown
## Working Commands
- /optimize, /cleanup, /onboarding, /skills, /help, /brief, /stuck, /next, /phase
- ./kitty backup, ./kitty status, ./kitty export
```

### 4. **Ensure "Forbidden work" is current**
Check against CURRENT_FOCUS and update if needed:
```markdown
## Forbidden work
- MCP expansion  
- QLoRA
```

### 5. **Update "Skills" section**
List active consolidated skills:
```markdown
## Skills
- orient, optimize, debug, handoff, research, plan, build, ship, cleanup
```

### 6. **Update "Tests" line**
Get the count from last test run:
```bash
pytest tests/ -q --tb=short 2>&1 | grep "passed"
# Copy the result, e.g. "530 passed ✓"
```

---

## Example: Good Handoff

```markdown
# Current Focus
Last updated: 2026-05-09

## Active Phase

Phase 4 — Jacob-Only Build (4 sub-projects from Standup §4)

## Today's Progress (May 8-9)
- ✅ Fixed kittybuilder --brief to read from CURRENT_FOCUS.md (was reading stale project.json)
- ✅ Created unified project_state_reader.py (shared by /brief, /next, /phase)
- ✅ Added /phase and /next commands to dispatcher  
- ✅ Added 12 regression tests for state reader (530 tests passing)
- ✅ Created AGENT_HANDOFF_SESSION_TEMPLATE.md for next agents

## Working Commands
- /optimize, /cleanup, /onboarding, /skills, /help, /brief, /stuck, /next, /phase
- ./kitty backup, ./kitty status, ./kitty export

## Skills  
- orient, optimize, debug, handoff, research, plan, build, ship, cleanup

## Forbidden work
- MCP expansion
- QLoRA

## Tests: 530 passed ✓
```

---

## Example: What NOT To Do

❌ **DON'T:**
- Leave vague descriptions like "fixed stuff"
- Leave old dates ("Last updated: 2026-05-07" when you worked on 05-09)
- Leave broken/untested commands in the "Working Commands" list
- Forget to run tests and update the count
- Add new "Forbidden work" items without explaining why

---

## Why This Matters

1. **Next agent context** — They see exactly what you did and what's next
2. **Brief consistency** — `kittybuilder --brief` reads this to show state
3. **Scope clarity** — Forbidden work prevents scope creep
4. **Verification** — Test count is proof of health
5. **Speed** — New agent doesn't waste time reverse-engineering your work

---

## Commands to Check Your Work

```bash
# Run tests and get count
python3 -m pytest tests/ -q --tb=short

# Test the brief output
./kittybuilder --brief

# Test the new state reader (if you made changes)
python3 -c "from src.core.project_state_reader import read_current_focus; print(read_current_focus())"
```

---

## Handoff Locations

- **This template:** `docs/AGENT_HANDOFF_SESSION_TEMPLATE.md`
- **Session summary:** `SESSION_SUMMARY.md` (capture session takeaways)
- **Handoff report:** `docs/handoffs/HANDOFF-YYYY-MM-DD.md` (agent-written report)
- **State source:** `CURRENT_FOCUS.md` (THIS is what PM tools read)

---

## Questions?

- If CURRENT_FOCUS section is unclear → ask Jacob
- If you're adding a new feature → update this template too
- If tests fail → fix them before handoff

**Target:** Spend 5 minutes updating CURRENT_FOCUS at handoff. Saves next agent 30 minutes.
