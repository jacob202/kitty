# REFACTOR_PLAN.md

**Date**: 2026-05-09  
**Based on**: IMPROVEMENT_AUDIT.md

---

## High Priority (Do First)

### 1. Config Index

**File**: `config/README.md`

```markdown
# Config Index

| File | Purpose | Keys |
|------|--------|------|
| kitty_settings.json | Main app settings | port, debug, model |
| hardware_triggers.json | MLX model routing by hardware | ... |
| domain_config.json | Domain routing | ... |
```

**Status**: TODO

---

### 2. Data Routing Document

**File**: `docs/DATA_ROUTING.md`

```markdown
# Data Routing

| Data Type | Store | Never use |
|----------|-------|----------|
| KB / knowledge | LightRAG | JournalDB |
| Journal entries | JournalDB | LightRAG |
| Semantic search | ChromaDB | - |
| Corrections | SQLite | - |
```

**Status**: TODO - CLAUDE.md has partial

---

## Medium Priority (Do Second)

### 3. Config Validation

Add Pydantic validation for config loading:

```python
# src/config/validators.py
from pydantic import BaseModel

class KittySettings(BaseModel):
    port: int = 5001
    debug: bool = False
    model: str = "qwen3.5"
```

**Status**: TODO

---

### 4. Migration Tool

**File**: `scripts/migrate_stores.py`

Migrate data between stores (LightRAG ↔ JournalDB ↔ ChromaDB)

**Status**: TODO

---

## Low Priority (Nice to Have)

### 5. Split Giant Files

Only if active development:

- performance_monitor.py (1338 lines)
- datasheet_intelligence.py (1262 lines)

**Status**: defer

---

## What NOT to Do

- ❌ Merge storage backends (complex, risky)
- ❌ Rewrite giant files (working code)
- ❌ Add new dependencies without justification
- ❌ Change data routing without migration tool

---

## Acceptance Criteria

- [ ] config/README.md exists
- [ ] docs/DATA_ROUTING.md exists  
- [ ] Tests still pass (532+)
- [ ] No new config errors in logs