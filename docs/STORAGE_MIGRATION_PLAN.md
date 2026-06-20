# Storage Migration Plan

**Date:** 2026-06-20

## Principle

Migrate behind stable APIs. Do not make the UI or clients care where state lives.

## Current Store Map

| Store | Current shape | Phase B action |
|---|---|---|
| Quick Capture inbox | `data/inbox.jsonl` | Keep append-only for desktop/mobile compatibility |
| Journal | JSONL via `gateway/journal.py` | Later episodic migration candidate |
| Todos | SQLite via `gateway/todo_store.py` | Normalize under shared DB later |
| Cron schedules | SQLite via `gateway/cron.py` | Normalize under shared DB later |
| Plugin settings | JSON via `gateway/plugin_registry.py` | Good first low-risk migration |
| Model digest | SQLite via `gateway/model_digest.py` | Leave until shared DB shape is proven |
| ChromaDB | vector store | Do not migrate in Phase B |
| mem0 | semantic memory | Do not migrate in Phase B |
| Logs/feedback/traces | JSONL | Do not migrate unless product reads require it |

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
