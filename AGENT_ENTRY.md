# 🚨 AGENT ENTRY POINT — READ FIRST

**Every agent MUST do this before starting:**

```bash
cd /Users/jacobbrizinski/Projects/kitty
pwd  # Verify: /Users/jacobbrizinski/Projects/kitty (NOT Desktop)
python3 scripts/agent-context-brief.py  # Read mandatory context
```

**Then:**
1. Restate your task in your own words in ONE sentence
2. Wait for Jacob to say "go"
3. Work autonomously (Rule 1)
4. Handoff only at session END (Rule 10)

---

**Authority files (in order):**
1. `docs/STANDUP.md` — §0-§9 (rules, state, tasks)
2. `CURRENT_FOCUS.md` — What's active RIGHT NOW
3. `AGENTS.md` — How agents work on this project
4. Latest handoff in `docs/handoffs/`

**Do NOT read:**
- Old docs in `docs/archive/`
- Desktop backup at `~/Desktop/kitty-system/kitty-app`

---

**One rule that prevents disaster:**
- Run `pwd` before ANY file write
- Must show: `/Users/jacobbrizinski/Projects/kitty`
- If not, STOP and tell Jacob

---

**Before you commit:**
```bash
venv/bin/python -m pytest tests/ -q --tb=short
```
Must pass (530+ tests). Pre-commit hook will block you otherwise.

---

**Questions?** Read STANDUP.md §3 (Jacob's Rules 1-14).
