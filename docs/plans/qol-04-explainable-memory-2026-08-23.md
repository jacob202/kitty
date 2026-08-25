# QoL Packet 04 — Explainable Memory

**Status:** Implementation plan for Jacob approval (not self-authorizing)
**Packet:** `docs/quality_of_life_packets.md` PACKET 04 — EXPLAINABLE MEMORY (P1)
**Branch:** `feat/explainable-memory-20260823` (worktree `/Users/jacobbrizinnski/Projects/kitty/.worktrees/explainable-memory-20260823`)
**Base:** origin/main `d29e323a`
**Depends on:** #552 governed explicit-memory store (already on main)

## Objective

For any significant remembered fact ("I prefer X"), the user can ask *where did you get
that?* and get a truthful explanation — fact, source, source type, time, authority,
confidence/truth status, superseded value, current state, and sensitivity — then act on
it with **Correct**, **Forget**, **Pin/Unpin**, and **View source**, without ever touching
Kitty's memory internals.

## Constraints

- **Do not expose internal embeddings or vector bytes.** The explanation is a projection
  over the governed `explicit_memories` store only.
- **Do not create a new memory backend.** Compose `gateway/explicit_memory.py` (#552).
- **Do not let the UI mutate domain truth directly.** All controls route through the
  existing governed lifecycle: Correct → `remember(supersedes_id=...)` (the normal
  correction/supersession path); Forget → `forget()`; Pin/Unpin → a thin new toggle.
- **Do not weaken forbidden/deprecated memory handling.** `blocked`/`archived` statuses
  are never resurrected; sensitive memories stay sensitive.
- **Do not turn every memory into permanent user-visible clutter.** The explain surface is
  per-memory and request-driven; there is no new home-page dump.
- Read-only by default: `explain` never mutates. Mutating controls require an explicit
  user action.
- Preserve `GET /memories` and `DELETE /memories/{id}` semantics.

## Existing primitives to compose (do not reinvent)

| Need | Source |
|---|---|
| Fact / text | `explicit_memory.get(memory_id, include_inactive=True)` |
| Source kind + ref | row `source_kind`, `source_ref` (e.g. `user_explicit`, `user_correction`, `insight_loop`, `repairs`) |
| Time | row `created_at`, `updated_at`, `forgotten_at` |
| Authority | derived from `source_kind`: `user_explicit`/`user_correction`/`verbal_confirmation` → `user`; everything else (`insight_loop`, `repairs`, `web_search`, ...) → `automated` |
| Confidence / truth status | row `truth_confidence` (1.0; stable facts do not decay — existing `search` never age-scores) |
| Superseded value | walk `superseded_by` chain / query `WHERE superseded_by = ?` for the value this memory replaced |
| Current state | row `status` (`active`/`superseded`/`forgotten`/`archived`/`blocked`) |
| Sensitivity | row `sensitivity` (`normal`/`sensitive`) |
| Correct | `remember(text, supersedes_id=memory_id, source_kind="user_correction", ...)` |
| Forget | `forget(memory_id)` (existing) |
| Pin/Unpin | NEW thin `set_pinned(memory_id, *, pinned)` mirroring `forget()` |
| View source | `source_kind` + `source_ref` in the explain payload |

## Deliverables

1. **`gateway/memory_explain.py`** (NEW) — pure, read-only projection:
   - `explain(memory_id, *, now=None) -> dict` raising `ExplicitMemoryNotFound` when the
     row is missing. Payload shape:
     ```
     {
       id, fact, namespace, memory_key,
       source: {kind, ref, authority},        # authority ∈ {user, automated}
       source_type,                           # human label for kind
       remembered_at, updated_at,
       truth: {confidence: 1.0, stable: true},
       current_state,                         # status
       sensitivity,
       pinned,
       supersedes: {id, fact, source, remembered_at} | None,   # value this memory replaced
     }
     ```
   - No mutation. No embedding bytes. No new tables (uses the existing `explicit_memories`
     rows incl. the `superseded_by` link).
   - Sensitive isolation: `explain` is id-addressable (the user already has the id); it
     never widens search recall or exposes unrelated sensitive context.
2. **`gateway/explicit_memory.py`** — add one small function `set_pinned(memory_id, *,
   pinned: bool, now=None) -> bool` (active-only update mirroring `forget()`), plus expose
   the existing `source_kind` provenance already stored. No schema change, no migration.
3. **`gateway/routes/memories.py`** (EDITED) — new routes, existing `/memories` +
   `/memories/{id}` (DELETE) untouched:
   - `GET /memories/{memory_id}/explain` → `{"memory": explain(...)}`; 404 via
     `StorageNotFound` on `ExplicitMemoryNotFound`.
   - `POST /memories/{memory_id}/correct` body `{text, memory_key?}` → routes through
     `remember(text, supersedes_id=memory_id, source_kind="user_correction", ...)`
     (existing correction/supersession path); 404 when the target is not active.
   - `POST /memories/{memory_id}/pin` body `{pinned: bool}` → `set_pinned`; 404 when not
     active. (`GET /memories` rows already carry `pinned`.)
4. **UI (deferred in plan; separate PR stage)** — a per-memory explain/control surface in
   kitty-chat (RightPanel memory items or a small memory view) showing the explanation
   block and Correct / Forget / Pin / View-source controls. Not part of this backend PR.

## RED tests first

`tests/test_memory_explain.py` (NEW), fixture mirrors `tests/test_explicit_memory.py`
(monkeypatch `explicit_memory.DB_FILE` = tmp db; `kitty_db.migrate` applies the store):

1. Explicit preference explainability — remember with `source_kind`/`source_ref`;
   `explain` returns fact, `source.kind`, `source.ref`, `authority == "user"`,
   `truth.confidence == 1.0`, `current_state == "active"`, `sensitivity`, `pinned`.
2. Automated-source authority — `source_kind="insight_loop"` → `authority == "automated"`.
3. Correction creates supersession — remember old, correct via `remember(supersedes_id=old)`
   → `explain(new).supersedes == {id: old, fact: old_text, ...}`; old row is `superseded`
   with `superseded_by == new.id`; `search` returns only the new value (project truth
   outranks the stale memory).
4. Forget — `forget(id)` → `current_state == "forgotten"` + `forgotten_at` set; active
   search no longer returns it; the audit row still explains.
5. Stable fact aging — a 3650-day-old fact still explains with `truth.confidence == 1.0`
   and original `remembered_at` preserved (no decay).
6. Sensitive-memory isolation — a `sensitivity="sensitive"` memory explains with its
   `sensitivity` field; unrelated search still returns `[]` (isolation unchanged).
7. Missing id → `ExplicitMemoryNotFound`.
8. `set_pinned` — pin True then False; `pinned` flips and persists; non-active or missing
   id returns `False`/raises consistently.
9. Route tests (mounted `TestClient` or direct calls, following `test_status_glance`
   pattern): `GET /memories/{id}/explain` 200 shape; missing id → 404; `correct` creates a
   `user_correction` active row and supersedes the original; `correct` on a forgotten
   target → 404; `pin` flips `pinned`.

## Acceptance

1. RED tests fail before implementation; GREEN after smallest implementation.
2. Wider memory slice still passes: `test_explicit_memory`, `test_memory_*` relevant
   suites, `test_automation_*`/cron unaffected.
3. `GET /memories/{id}/explain` verified live against a running sandbox gateway with a
   real remembered + corrected fact (supersession chain visible).
4. Ruff + mypy clean on changed files.
5. The `storage: "explicit"` id-addressable projection never renders embedding bytes; no
   new memory backend or migration introduced.

## Deferred / out of scope

- UI surface for explain/controls (separate, follow-on PR with hermetic-stub care so Home
  stays free of internal names, per the Packet 01 lesson).
- Restore previous value (Unpin/Unsupersede) — packet lists as "potentially".
- Semantic/vector memory explanation (packet targets the governed #552 store; weave and
  mem0 remain out of scope).
- Builder memory state.
