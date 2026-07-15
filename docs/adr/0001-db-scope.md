---
type: adr
title: "db.py is the SQLite seam for app-state stores only"
status: accepted
owner: jacob
primary_purpose: Decide the scope and role of gateway/db.py as the single SQLite seam for app-state stores
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0001: db.py is the SQLite seam for app-state stores only

**Date:** 2026-07-02
**Status:** Accepted

## Context

`gateway/db.py` exposes `connect()`, which opens `KITTY_DB_FILE` with project
defaults (foreign keys, row factory, WAL). It was introduced in Phase B as the
foundation for migrated app-state stores.

Five modules use it: `todo_store`, `chats_store`, `journal_store`,
`buddy_store`, `plugin_registry`.

Eight other gateway modules open their own `sqlite3.connect` against separate
`.db` files, bypassing `db.py` entirely:

| Module               | DB file                  |
| -------------------- | ------------------------ |
| `cron.py`            | `data/kitty/cron.db`     |
| `builder.py`         | `data/builds.db`         |
| `agent_runner.py`    | autonomy state           |
| `task_runner.py`     | `data/task_queue.db`     |
| `ingestion_queue.py` | own queue db             |
| `web_monitor.py`     | own monitor db           |
| `autonomy_state.py`  | `data/kitty/autonomy.db` |
| `model_digest.py`    | `data/model_digest.db`   |

This looks accidental — a reader who learns `db.py` then expects the rest of
the gateway to use it is surprised 8 times.

## Decision

**`db.py` is the SQLite seam for migrated app-state stores only.** It is not
the universal SQLite connector for the gateway. Subsystem modules that own
their own databases (cron, builds, tasks, ingestion, web monitors, autonomy
state, model digest) are permitted to manage their own connections and
schemas by design, because:

1. Their schemas, lifecycles, and migration needs are independent of
   app-state.
2. Forcing them through `db.py` would require `db.py` to know about
   N subsystem-specific DB files, which is not a seam — it's a router.
3. None of them need cross-DB transactions with app-state.

## Consequences

- A future architecture review should not re-suggest "make `db.py` the
  universal SQLite connector" without first addressing why the subsystems
  need to share a connector (they currently don't).
- If a subsystem later needs app-state-level guarantees (WAL, foreign keys
  to app-state tables, shared migrations), it should be migrated into
  `KITTY_DB_FILE` and use `db.py` — not the other way around.
- New app-state stores must use `db.py`. New subsystem stores may open their
  own connections but should document the DB path in `gateway/paths.py`.
