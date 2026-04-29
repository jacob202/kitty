# Memory Model

Last updated: 2026-04-28

This is the planned durable-state contract. It is not permission to migrate memory yet.

## Write Rule

All durable writes must go through repository modules. Do not scatter direct SQL across runtime code.

Planned paths:

- `src/memory/db.py`
- `src/memory/task_repo.py`
- `src/memory/decision_repo.py`
- `src/memory/memory_repo.py`
- `src/memory/correction_repo.py`
- `src/memory/intake_repo.py`
- `src/memory/feedback_repo.py`

## Core Tables

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT CHECK(status IN ('open','done','parked','blocked')) NOT NULL DEFAULT 'open',
    project TEXT,
    source_message TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE decisions (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT,
    rejected_alternatives TEXT,
    consequences TEXT,
    review_trigger TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE parked_features (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'parked',
    source_context TEXT,
    problem TEXT,
    proposed_behavior TEXT,
    why_not_now TEXT,
    dependencies TEXT,
    implementation_sketch TEXT,
    risks TEXT,
    revival_trigger TEXT,
    minimum_safe_version TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE intake_logs (
    id INTEGER PRIMARY KEY,
    raw_request TEXT NOT NULL,
    interpretation TEXT,
    classification TEXT CHECK(classification IN ('ready','needs_verification','park','split','reject')) NOT NULL,
    recommended_action TEXT,
    spec_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE specialist_feedback (
    id INTEGER PRIMARY KEY,
    specialist TEXT,
    user_message TEXT,
    answer TEXT,
    correction TEXT,
    source TEXT,
    reviewed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE response_feedback (
    id INTEGER PRIMARY KEY,
    source_message TEXT,
    draft_response TEXT,
    user_correction TEXT,
    extracted_rule TEXT,
    status TEXT CHECK(status IN ('pending_review','accepted','rejected')) DEFAULT 'pending_review',
    created_at TEXT NOT NULL
);

CREATE TABLE cost_events (
    id INTEGER PRIMARY KEY,
    model TEXT NOT NULL,
    provider TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost REAL DEFAULT 0,
    route_reason TEXT,
    created_at TEXT NOT NULL
);
```

## Later Vector Tables

```sql
CREATE TABLE memory_entries (
    id INTEGER PRIMARY KEY,
    type TEXT CHECK(type IN (
      'identity','preference','goal','project','habit',
      'decision','constraint','relationship','episode','reflection'
    )),
    content TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    last_accessed TEXT,
    access_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE memory_embeddings (
    memory_id INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(memory_id) REFERENCES memory_entries(id)
);
```

## Validation When Implemented

```bash
sqlite3 data/kitty.db ".tables"
sqlite3 data/kitty.db "PRAGMA integrity_check;"
```
