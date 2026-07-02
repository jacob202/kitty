# Packet 002 — Inbox triage

- **Status:** ready
- **Best executor:** Codex or Claude Code
- **Purpose:** Make capture come back. Decide, for every inbox entry and
  unprocessed signal, whether it matters now, later, never, or needs Jacob.

## Exact scope

1. Migration `gateway/migrations/008_inbox_triage.sql`:

   ```sql
   CREATE TABLE IF NOT EXISTS inbox_triage (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       inbox_id TEXT NOT NULL UNIQUE,
       ts REAL NOT NULL,
       bucket TEXT NOT NULL,          -- now|scheduled|someday|reference|needs_jacob|drop
       confidence REAL NOT NULL,
       rationale TEXT NOT NULL,
       model TEXT NOT NULL,
       created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
   );
   ```

2. New `gateway/triage.py`:
   - `run_pass(limit=25)` — load inbox entries (`desktop_store.read_inbox`)
     with no `inbox_triage` row, classify each via an injected LLM callable
     (default: `llm_client` local-model route, with TELOS/`user_context` and
     `config/PREFERENCES.md` in the prompt), write one row per entry.
   - Buckets: `now`, `scheduled`, `someday`, `reference`, `needs_jacob`,
     `drop`. Confidence below `TRIAGE_CONFIDENCE_FLOOR` (0.6) ⇒ bucket is
     overridden to `needs_jacob` and the rationale says so.
   - LLM unavailable or non-parseable output ⇒ raise; zero rows written for
     that entry. No rule-based fallback, no guessed bucket. (CLAUDE.md
     non-negotiable 1.)
   - `list_triaged(bucket=None, limit=50)` — join triage rows to entries.
3. Routes (new `gateway/routes/inbox.py` or extend `routes/desktop.py`,
   whichever the existing inbox read endpoint lives in):
   - `POST /inbox/triage` — run a pass, return counts per bucket.
   - `GET /inbox/triaged?bucket=` — list.
4. Cron registration for a periodic pass, following the existing
   `gateway/cron.py` pattern.
5. Tests `tests/test_triage.py`: stubbed-LLM classification per bucket;
   low-confidence override to `needs_jacob`; LLM-down path writes nothing
   and raises; `drop` is a row, never a deletion; idempotence (second pass
   skips already-triaged ids).

## Files not to touch

- `data/inbox.jsonl` format and `desktop_store.py` write path (D4: capture
  stays dumb and append-only; triage results live only in kitty.db).
- `memory_graph.py`, `storage_router.py`, existing migrations, UI.

## Acceptance criteria

- Fixture entries land in expected buckets with a stub model.
- Inbox JSONL is byte-identical before/after a pass.
- Failure path proven: stub raising ⇒ explicit error, zero triage rows.
- Full suite green.

## Verification

```bash
python3.12 -m pytest tests/test_triage.py tests/ -q --tb=short
curl -s -X POST localhost:8000/inbox/triage | jq .
```

## Risks / rollback

- Over-eager `drop`: mitigated — drop is a bucket, not a deletion, and low
  confidence reroutes to `needs_jacob`. Rollback: revert PR; the triage
  table is inert; inbox untouched by design.

## Too broad if

It starts proposing actions (packet 003's consumer does that), adds new
capture sources, or triages anything other than inbox entries in v1.

## Jacob reviews

Bucket definitions and the confidence floor.
