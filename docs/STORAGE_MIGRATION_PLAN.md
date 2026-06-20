# Storage Migration Plan

**Date:** 2026-06-20

## Principle

Migrate behind stable APIs. Do not make the UI or clients care where state lives.

## Current Store Map

| Store | Path | Current shape | Phase B action | Layout |
|---|---|---|---|---|
| Quick Capture inbox | `data/inbox.jsonl` | JSONL append | Keep append-only (D4) | `data/` — stays |
| Journal | `data/journal_entries.jsonl` | JSONL | B3 episodic migration candidate | moves to `data/kitty/` |
| Todos | `data/todos.db` legacy, `data/kitty/kitty.db` current | SQLite | **B3 first user-facing seam** | moved to `data/kitty/kitty.db`; old file copied once and left untouched |
| Cron schedules | `data/cron_schedules.db` | SQLite | B3 episodic migration candidate | moves to `data/kitty/` |
| Plugin settings | `data/plugin_settings.json` | JSON | **B2 first migration** | moves to `data/kitty/kitty.db` |
| Model digest | `data/model_digest.db` | SQLite | Leave until shared DB proven | stays (deferred) |
| ChromaDB | `data/knowledge_db` | vector | Do not migrate in Phase B | stays |
| mem0 | `data/mem0` | semantic memory | Do not migrate in Phase B | stays |
| Logs/feedback/traces | `data/*.jsonl` | JSONL | Do not migrate unless reads require | stays |

## Migration Rules

- Old files are copied or renamed only with explicit operator action.
- Migration scripts must be idempotent.
- Every migration records schema version.
- Every failure includes source path, target path, and migration name.
- Tests must exercise corrupted input where practical.

## Proposed Schema Areas

- `app_settings`
- `captures`
- `journal_entries`
- `todos`
- `chat_sessions`
- `chat_messages`
- `buddy_state`
- `cron_schedules`
- `schema_migrations`

Do not create all tables at once unless a migration needs them. The list is a map, not permission to overbuild.

## Path Layout Policy

Two locations serve two purposes:

- `data/` — cross-substrate or external-compatibility stores. Currently just `inbox.jsonl` (D4: append-only for desktop and future mobile capture).
- `data/kitty/` — app-owned episodic state. All Phase B SQLite migrations land here.

The default for new stores is `data/kitty/`. A store stays in `data/` only if it satisfies one of:

1. Cross-substrate compatibility (currently: inbox only).
2. Operationally meaningful path pinned by other tools.
3. Explicit operator decision recorded in the Current Store Map above.

## Phase Order

The seam work is layered. Each phase's output is the next phase's input.

| Phase | Name | Depends on | Output |
|---|---|---|---|
| 0 | Path-seam discipline | — | `paths.py` is single source; path duplications resolved; `model_digest.py` hardcode fixed |
| 1 | Policy doc (this section) | — | `data/` vs `data/kitty/` rule is explicit |
| 2 | First store via `gateway/db.py` | Phase 0, 1 | `plugin_settings` writes through `db.py`; JSON readable during transition |
| 3 | First user-facing seam | Phase 2 | `todos` writes through `db.py`; old `data/todos.db` untouched |
| 4 | `StorageRouter` port | Phase 3 | Write-side seam mirrors `memory_graph` for future stores |

## StorageRouter Port (Phase 4 - shipped)

The read side is `memory_graph` (D3). The write side had no equivalent: every writer imported its store directly. Phase 4 introduces a small port that mirrors the read seam.

**Public surface** (thin mutation wrappers):

| Function | Purpose | Backend |
|---|---|---|
| `replace_todos(items)` | Replace the model-maintained todo list | `todo_store.update` |
| `add_todo(content, status, active_form)` | Append one todo | `todo_store.add` |
| `complete_todo(todo_id)` | Complete one todo by id | `todo_store.complete_by_id` |
| `delete_todo(todo_id)` | Delete one todo by id | `todo_store.delete_by_id` |
| `clear_todos()` | Remove all todos | `todo_store.clear` |
| `enable_plugin(name)` / `disable_plugin(name)` | Toggle plugin settings | `plugin_registry` |

The router is intentionally boring right now: no generic adapter registry, no
new query language, and no hidden fallback behavior. Route handlers cross this
seam for writes, and storage errors propagate from the underlying store.

**Current route coverage:**

- `gateway/routes/extended.py`: todo mutations use `storage_router`.
- `gateway/routes/integrations.py`: plugin enable/disable use `storage_router`.

Tests are local-substitutable per DEEPENING.md category 2. The interface is
the test surface; adapter internals are not.
