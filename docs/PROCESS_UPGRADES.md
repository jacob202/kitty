# PROCESS_UPGRADES.md

**Date**: 2026-05-09  
**Purpose**: Improve developer and AI workflow

---

## Developer Workflow

### Quick Commands (Run These)

| Task | Command |
|------|--------|
| Start server | `./kitty` |
| Run tests | `venv/bin/python -m pytest tests/ -q --tb=short` |
| Quick status | `./kitty quick status` |
| Quick test | `./kitty quick test` |
| File index | `./kitty quick index <pattern>` |
| Build file index | `python scripts/build_file_index.py` |
| Scaffold | `python scripts/scaffold.py <type> <name>` |
| Warm cache | `python scripts/warm_cache.py` |
| Session start | `bash scripts/start-session.sh` |

### Entry Points

1. `./kitty` - Main CLI (kitty shell script)
2. `./kittybuilder` - Builder entry (symlink to scripts/kitty_builder.py)
3. `python web.py` - Server directly

---

## AI Agent Workflow

### First Read Order

1. `docs/LAYER0_CONTROL_PLANE.md`
2. `docs/README.md`
3. `CURRENT_FOCUS.md`
4. `TASKS.md`
5. `AGENTS.md`

### Prompt Templates

**Debug issue**:
```
inspect files: <paths>
run tests: venv/bin/python -m pytest tests/ -q --tb=short
check logs: tail -20 .kitty.log
```

**Add feature**:
```
1. Check existing: glob pattern='**/<name>*.py'
2. Write spec: docs/superpowers/plans/<name>.md
3. Scaffold: python scripts/scaffold.py <type> <name>
4. Test: venv/bin/python -m pytest tests/ -q --tb=short
```

**Run build gate**:
```
bash scripts/run_gates.sh
```

---

## Session Management

### Start Session
```bash
bash scripts/start-session.sh           # quick mode (default)
bash scripts/start-session.sh --full  # full tests
```

### Validation

Always run after changes:
```bash
venv/bin/python -m pytest tests/ -q --tb=short
./kitty quick health
```

---

## Token Optimization

### Quick Actions (No LLM)
- `./kitty quick status` - server check
- `./kitty quick count <path>` - line count
- `./kitty quick index <pattern>` - file search

### Cached
- SemanticCache: runs automatically
- File index: `python scripts/build_file_index.py`
- Tool schemas: cached in tools module

---

## Common Patterns

### Create new test
```bash
python scripts/scaffold.py test my_feature
```

### Create new tool
```bash
python scripts/scaffold.py tool my_tool
```

### Create new route
```bash
python scripts/scaffold.py route my_endpoint
```

---

## What NOT to Do

- ❌ Run full test suite for every change (use targeted)
- ❌ Modify configs without checking existing
- ❌ Add dependencies without updating requirements.txt
- ❌ Ignore test failures

---

## Known Issues to Avoid

See `docs/DECISIONS.md` and `docs/OPEN_LOOPS.md`