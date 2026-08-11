# Owner-memory store classification — PAA-1 first slice (#389)

Scope: PAA-1 asks for "one machine-readable owner-data manifest... classify
every store as canonical, derived/rebuildable, secret, cache, or execution
evidence." This document is that classification pass only — it does not
build the manifest file, the export code, or the fresh-install semantic-
parity proof. Those require real engineering (schema, migration, restore
verification) and PAA-5's auth-boundary work explicitly requires "a
dedicated threat review and Jacob's approval" before implementation, so
none of that is attempted here.

Confidence note: classifications below come from each module's own
docstring/schema, not from running the code. Anything marked `(verify)`
should be confirmed before it's relied on for a real export.

## Gap found first

`gateway/storage_sync.py` — the module PAA-1 is told to build on — currently
exports only **5** stores: `memories`, `journal_entries`, `todos`,
`plugin_settings`, `preferences` (and `preferences` is a literal placeholder
returning `{}`, per its own docstring: "Currently a placeholder; reserved
for future use"). The repository has at least **33** modules that open a
SQLite connection or own durable state. #389's own status table already
flagged this ("current JSON export covers only selected migrated stores") —
this pass puts a number on it.

## Canonical (must be exportable; irreplaceable owner data)

| Store | Module | Notes |
|---|---|---|
| Memories | `memory.py` / `memory_graph.py` | Exported today. |
| Journal entries | `journal_store.py` | Exported today. |
| Todos | `todo_store.py` | Exported today. |
| Chat sessions | `chats_store.py` | **Not exported.** JSON-blob store, wire-compatible with legacy `chats.json`. |
| Chat lifecycle ledger | `chat_lifecycle.py` | **Not exported.** Restart-recovery facts; docstring calls the legacy blob "UI compatibility," implying this ledger is the more complete record. |
| Projects | `project_store.py` | **Not exported.** Names/paths/status registry. |
| Deadlines | `deadline_store.py` | **Not exported.** Watched deadlines + escalation log. |
| Idea-mine items / insights | `idea_mine_store.py` | **Not exported.** Backing store for #270's insight loop (capture/classify/return). |
| Image characters + references | `image_characters.py` | **Not exported.** Named, privacy-scoped subjects Jacob created. |
| Image conversational sessions | `image_sessions.py` | **Not exported.** "Keep his face, make his build broader" continuity state (#336). |
| Preferences | referenced by `storage_sync.export_preferences` | **Placeholder only** — the function exists and returns `{}`; no real preference store is wired to it (verify: find where preferences actually live — likely `config/PREFERENCES.md` per the `remember` skill, i.e. file-based, not SQLite, which is why the DB export is empty). |

## Derived / rebuildable (reconstructable from canonical data or external sources)

| Store | Module | Notes |
|---|---|---|
| Temporal knowledge graph | `memory_weave.py` | Learns from corrections/tool failures; in principle re-derivable by replaying memory + journal history, but no replay tool exists today `(verify)`. |
| Triage classifications | `triage.py` (`inbox_triage` rows) | Re-runnable against `inbox.jsonl` since capture stays dumb by design (D4) and triage never mutates the source. |
| Weekly pattern mirror | `honcho.py` | Explicitly a summary over gateway traces/logs — regenerable if logs exist. |
| Model digest | `model_digest.py` | Cached record of model-catalogue changes for the morning brief; rebuildable from the provider APIs. |
| Signals | `signal_store.py` | Append-only connector/system events; useful history but not owner-authored — losing old signals doesn't lose owner intent. |

## Execution evidence (proves what the system did, not owner content)

| Store | Module |
|---|---|
| Builder queue/attempts/leases | `builder_queue_db.py`, `builder_runtime.py`, `builder_status.py`, `builder_status_readonly.py` |
| Action queue (proposed/approved/executed) | `action_queue.py` |
| Compute governor dispatch receipts | `compute_governor.py` |
| Cron schedule state | `cron.py` |
| Image job/plan/recipe records | `image_jobs.py`, `image_plans.py`, `image_recipes.py` |
| Insight-loop lifecycle | `insight_loop.py` |
| Artifact provenance | `artifact_store.py` |
| Expert/proactive state (snooze, inbox lifecycle) | `expert_state.py` |
| Onboarding progress | `onboarding.py` |
| Next-step navigator cache | `next_step.py` |
| Composed "what's going on now" | `state_composer.py` (computed on read, not stored — likely `NOT NEEDED` for export, since it's a live projection, not a store) |
| Active-project scope | `project_context.py` |
| Buddy state | `buddy_store.py` |

None of these are owner-authored content; PAA-1's export is about owner
memory, so this bucket is lower priority for the manifest but still needs a
line in it (PAA's own spec wants every store classified, even ones excluded
from the export).

## Secret (excluded by construction)

`gateway/config.py`, `gateway/auth.py` — API keys, credentials, tokens.
`(verify)`: confirm no canonical store above embeds a secret inline (e.g. a
connector's OAuth token stored alongside its signal history) before writing
the real export — PAA-1's acceptance requires excluded/rebuildable stores
to be reported explicitly, not just assumed clean.

## Cache

No dedicated cache-only store found beyond `model_digest.py` (already
counted under derived, since it's both a cache of an external catalogue and
useful without re-fetching). No further cache-tier stores identified this
pass.

## Net finding

The real PAA-1 gap isn't designing a schema — the pieces PAA-1 asks for
(canonical/derived/secret/cache/execution-evidence classification) map
cleanly onto the existing module boundaries. The gap is that
`storage_sync.py` covers 5 of at least 11 canonical stores. Extending it to
the other 6 (chats, chat lifecycle, projects, deadlines, idea-mine,
image characters/sessions) is real engineering — schema per store, import
validation, a fresh-install semantic-parity test — and is the right next
PAA-1 slice, but is implementation work, not audit, so it isn't attempted in
this pass.
