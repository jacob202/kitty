# Goose Phase 6+ Task Stack

**Instructions for Goose (using MLX backend):** Work through these tasks sequentially. For each task:
1. Read the spec
2. Build the files
3. Run validation
4. Log result in SESSION_SUMMARY.md under a section for that feature
5. Mark task done in TASKS.md

**Rules:**
- Do NOT wire into web.py or app factory (no route registration)
- Run `bash scripts/run_gates.sh` after each task
- Commit only after validation passes

---

## Task 1: Memory Inspect/Forget

**Files to create:**
- `src/memory/inspect.py` — memory inspect and forget functions
- `tests/test_memory_inspect.py` — pytest tests
- `specs/memory-inspect.spec.md` — using specs/_template.md

**Validation:**
```bash
python3 -m pytest tests/test_memory_inspect.py -q
python3 -c "from src.memory.inspect import list_all_memories; print('OK')"
```

---

## Task 2: Specialist Prototype (One)

**Files to create:**
- `src/core/specialists/code.py` — Alex code specialist prototype
- `tests/test_code_specialist.py` — pytest tests
- `specs/code-specialist.spec.md`

**Validation:**
```bash
python3 -m pytest tests/test_code_specialist.py -q
python3 -c "from src.core.specialists.code import AlexSpecialist; print('OK')"
```

---

## Task 3: Transparent Evals Dashboard

**Files to create:**
- `src/observability/evals_dashboard.py` — eval metrics endpoint
- `tests/test_evals_dashboard.py`
- `specs/evals-dashboard.spec.md`

**Validation:**
```bash
python3 -m pytest tests/test_evals_dashboard.py -q
```

---

## Task 4: Security Scanning of Builder Output

**Files to create:**
- `src/utils/security_scanner.py` — bandit-like checks for builder output
- `tests/test_security_scanner.py`
- `specs/security-scanner.spec.md`

**Validation:**
```bash
python3 -m pytest tests/test_security_scanner.py -q
```

---

## Completion

After all tasks done:
1. Update TASKS.md — mark Phase 6+ tasks as done
2. Update CURRENT_FOCUS.md — set next phase
3. Run `bash scripts/run_gates.sh` — must pass 65+ tests
4. Log final summary in SESSION_SUMMARY.md under "Phase 6+ Complete"
