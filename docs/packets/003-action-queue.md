# Packet 003 — Action queue with enforced tiers

- **Status:** shipped (this PR). Tier sheet signed off by Jacob 2026-07-02
  with one change: `_T3_never` renamed to `_disabled_v1` and the disabled list
  expanded (below).
- **Best executor:** Claude Code (tier enforcement deserves the strongest
  code executor); tier config reviewed by the strongest model + Jacob

## Tier semantics (as signed)

- **T0** may execute automatically from `proposed`; every execution is recorded.
- **T1** may create *local* draft artifacts automatically from `proposed`;
  transmits nothing and performs no external side effect.
- **T2** requires explicit per-action approval before execution.
- **Purpose:** The safe path from "Kitty thinks X should happen" to
  "X happened, recorded." No external effect may exist outside this queue.

## Exact scope

1. Migration `gateway/migrations/009_actions.sql`:

   ```sql
   CREATE TABLE IF NOT EXISTS actions (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
       source_kind TEXT NOT NULL,     -- signal|triage|nudge|chat|manual
       source_id TEXT,
       kind TEXT NOT NULL,            -- e.g. todo.create
       title TEXT NOT NULL,
       preview TEXT NOT NULL,         -- human-readable: exactly what will happen
       payload TEXT NOT NULL DEFAULT '{}',
       risk_tier TEXT NOT NULL,       -- T0|T1|T2 (T3 kinds cannot exist)
       status TEXT NOT NULL DEFAULT 'proposed',
           -- proposed|approved|rejected|executed|failed
       result TEXT,
       decided_at REAL,
       executed_at REAL
   );
   ```

2. New `gateway/action_queue.py` (NOT under `gateway/actions/` — that dir
   holds unrelated legacy scripts):
   - `propose(source_kind, source_id, kind, title, preview, payload) -> dict`
   - `approve(action_id)` / `reject(action_id)` — proposed-only transitions.
   - `execute(action_id)` — dispatches through an **executor registry**
     mapping kind → (tier, callable). T0 may execute from `proposed`;
     T2 requires `approved` (else hard 403-shaped error). Unknown kind ⇒
     error. Result (success or exception text) recorded on the row.
   - Registry ships with exactly three kinds:
     - `todo.create` — T0, via `storage_router` → `todo_store.add`.
     - `note.draft` — T1, writes a file under `data/drafts/`; "execute"
       produces the artifact, transmits nothing.
     - `calendar.event.create` — T2, via `calendar_integration.create`.
   - Tier assignments load read-only at startup from
     `config/action_tiers.json`. A kind missing from the file cannot be
     registered. No runtime mutation API.
3. `config/action_tiers.json` v1 (**Jacob signs this file in review**):

   ```json
   {
     "todo.create": "T0",
     "note.draft": "T1",
     "calendar.event.create": "T2",
     "_disabled_v1": [
       "payments", "data.delete", "secrets", "bulk.outbound",
       "email.send", "email.archive", "email.delete",
       "github.merge", "github.push", "external.purchase", "account.change"
     ]
   }
   ```

   `_disabled_v1` kinds are disabled for this packet: they must not exist as
   executors now. Some may return as their own explicitly-approved future
   packets; none is reachable today. Registration fails loudly if an executor
   is ever added for a disabled kind.

4. New `gateway/routes/actions.py`: `GET /actions?status=`,
   `POST /actions/propose`, `POST /actions/{id}/approve`,
   `POST /actions/{id}/reject`, `POST /actions/{id}/execute`. Register in
   `routes/register.py`.
5. Tests `tests/test_action_queue.py` + `tests/test_actions_route.py`:
   full lifecycle round-trip; **tier-violation tests** (executing an
   unapproved T2 fails; unknown kind fails; kind absent from tier file
   fails registration); every execution writes a result; rejected actions
   remain queryable.

## Files not to touch

- `gateway/actions/` (legacy scripts), `llm_client.py`, `memory_graph.py`.
- Anything that would add an outbound-sending executor. `email.send` does
  not exist in this packet or the registry, by design.

## Acceptance criteria

- Lifecycle and tier enforcement proven by tests, not by convention.
- No code path from model output to external effect that bypasses the queue.
- The only external surface reachable is macOS Calendar create (T2).
- Full suite green.

## Verification

```bash
python3.12 -m pytest tests/test_action_queue.py tests/test_actions_route.py tests/ -q --tb=short
# manual on the Mac: propose → approve → execute a calendar event; see it in Calendar.app
```

## Risks / rollback

- Scope creep into more executors: the registry makes any addition a
  one-line diff that review will catch. Payload injection: validate
  payload per kind before dispatch. Rollback: revert PR; the actions table
  is inert; any approved calendar events are visible and manually
  deletable.

## Too broad if

It adds email sending, GitHub writes, retries/scheduling of failed
actions, standing-approval rules, or any UI.

## Jacob reviews

`config/action_tiers.json` line by line — this is the boundary document.
