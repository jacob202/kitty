# Goose Builder Stack — Phase 3 Tasks

**Instructions for Goose:** Work through these tasks sequentially. For each task:
1. Read the spec
2. Build the files
3. Run validation
4. Log result in SESSION_SUMMARY.md under a section for that feature
5. Mark task done in TASKS.md
6. Move to next task

**Rules:**
- Do NOT wire into web.py or app factory (no route registration)
- Do NOT edit protected files (see docs/FILE_GOVERNANCE.md)
- Run `bash scripts/run_gates.sh` after each task
- Commit only after validation passes

---

## Task 1: Morning Brief Module

**Files to create:**
- `src/core/morning_brief.py` — deterministic brief generator (no LLM)
- `src/api/brief.py` — handler function only (no route registration)
- `tests/test_morning_brief.py` — pytest tests
- `specs/morning-brief.spec.md` — using specs/_template.md

**Validation:**
```bash
python3 -m pytest tests/test_morning_brief.py -q
python3 -c "from src.core.morning_brief import generate_brief; print(generate_brief())"
```

---

## Task 2: Task Tracker + Done Handler

**Files to create:**
- `src/memory/task_repo.py` — SQLite tasks table + functions
- `src/memory/task_tracker.py` — process_done_command + get_next_task_brief
- `tests/test_task_tracker.py` — pytest tests
- `specs/task-tracker.spec.md` — using specs/_template.md

**Init DB:**
```bash
python3 -c "from src.memory.task_repo import init_task_db; init_task_db()"
```

**Validation:**
```bash
python3 -m pytest tests/test_task_tracker.py -q
sqlite3 data/kitty.db ".tables"
```

---

## Task 3: /stuck Command (already has src/core/stuck.py and src/api/commands.py)

**Files to create:**
- `tests/test_stuck_command.py` — pytest tests
- `specs/stuck-command.spec.md` — using specs/_template.md

**Validation:**
```bash
python3 -m pytest tests/test_stuck_command.py -q
python3 -c "from src.core.stuck import get_stuck_action; print(get_stuck_action())"
```

---

## Task 4: Response Quality Critic (v1.1)

**Files to create:**
- `src/space_kitty/quality_critic.py` — SOUL-aligned response reviewer
- `tests/test_quality_critic.py` — pytest tests
- `docs/SOUL_LEARNED_RULES.md` — pending review rules (initial empty structure)
- `specs/quality-critic.spec.md`

**Validation:**
```bash
python3 -m pytest tests/test_quality_critic.py -q
```

---

## Task 5: Chat Log Consolidation Pipeline

**Files to create:**
- `scripts/consolidate_chat_logs.py` — dry-run extraction pipeline
- `tests/test_consolidate_chat_logs.py`
- `docs/CHAT_LOG_CONSOLIDATION_REPORT.md` — initial template

**Validation:**
```bash
python3 scripts/consolidate_chat_logs.py --project . --input data/sessions --dry-run
python3 -m pytest tests/test_consolidate_chat_logs.py -q
```

---

## Completion

After all tasks done:
1. Update TASKS.md — mark all Phase 3 tasks as done
2. Update CURRENT_FOCUS.md — set next phase
3. Run `bash scripts/run_gates.sh` — must pass 65+ tests
4. Log final summary in SESSION_SUMMARY.md under "Phase 3 Complete"
