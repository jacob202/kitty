# Owner-memory store classification — PAA-1 first slice (#389)

Scope: PAA-1 asks for "one machine-readable owner-data manifest... classify
every store as canonical, derived/rebuildable, secret, cache, or execution
evidence." This document is that classification pass only — it does not
build the manifest file, the export code, or the fresh-install semantic-
parity proof. Those require real engineering (schema, migration, restore
verification) and PAA-5's auth-boundary work explicitly requires "a
dedicated threat review and Jacob's approval" before implementation, so
none of that is attempted here.

`docs/adr/0037-paa-reference-profile.md:120-123` is the accepted boundary:
canonical owner state explicitly includes "conversations, memory, journal,
projects, preferences, todos, captures, signals, imported knowledge
sources, and artifact metadata." Several classifications below were checked
against that line directly.

**Revision history:** this document went through two rounds of PR review
(both on #468, now merged) that found real errors — first in the "only 5
exported, ~11 canonical" version, then again in the "13 canonical, 8
missing" version below. Both rounds are folded in here. Confidence note:
classifications still come from reading each module's schema, not from
running an export/restore cycle. Anything marked `(verify)` should be
confirmed before it's relied on for a real export.

## Method gap, found in the second review round

The original module search (`grep` for `kitty_db.connect|sqlite3.connect
|DB_FILE\s*=`) missed every store that opens SQLite through
`gateway.db.connect` with a locally-named path constant instead of a
literal `..._DB_FILE` suffix — e.g. `gateway/tutor.py`'s `MEMORY_DB` and
`gateway/web_monitor.py`'s `MONITOR_DB`. Both hold real owner data (see
below) and were completely absent from the first version of this document.
Treat this classification as a starting inventory, not a verified-complete
one — a real manifest needs a structural search (every `DATA_DIR /` or
`KITTY_DATA_DIR /` path assignment, every `db.connect(...)` call site), not
a naming-convention grep.

## Gap found first

`gateway/storage_sync.py` — the module PAA-1 is told to build on — exports
only **5** stores: `memories`, `journal_entries`, `todos`,
`plugin_settings`, `preferences` (and `preferences` is a literal placeholder
returning `{}` — see the Preferences row below, it doesn't even export the
real preference files). The canonical list below now runs to at least
**19** stores. #389's own status table already flagged partial coverage;
this pass puts a real number on it, and that number grew across both
review rounds as more owner data surfaced.

Two exported stores also silently truncate: `export_memories()` and
`export_journal_entries()` both call their underlying `list_*` functions
with `limit=1000`. Past 1,000 rows, older canonical records are dropped
from the backup with no warning. These are marked **exported (truncated at
1000)** below, not simply "exported."

## Canonical (must be exportable; irreplaceable owner data)

| Store | Module | Notes |
|---|---|---|
| Memories | `memory.py` / `memory_graph.py` | **Exported (truncated at 1000).** `storage_sync.export_memories()` calls `list_memories(limit=1000)`. |
| Journal entries | `journal_store.py` | **Exported (truncated at 1000).** Same pattern, `journal_store.list_entries(limit=1000)`. |
| Todos | `todo_store.py` | Exported today, no truncation found. |
| Plugin settings | `plugin_registry.py` (`plugin_settings` table) | **Exported today, but never classified in the first version of this doc.** Owner-selected enable/disable preferences from the integration routes — canonical, not execution evidence. |
| Chat sessions | `chats_store.py` | **Not exported.** JSON-blob store, wire-compatible with legacy `chats.json`. |
| Chat lifecycle ledger | `chat_lifecycle.py` | **Not exported.** Restart-recovery facts; docstring calls the legacy blob "UI compatibility," implying this ledger is the more complete record. |
| Projects | `project_store.py` | **Not exported.** Names/paths/status registry. |
| Deadlines | `deadline_store.py` | **Not exported.** Watched deadlines + escalation log. |
| Idea-mine items / insights | `idea_mine_store.py` | **Not exported.** Backing store for #270's insight loop (capture/classify/return). |
| Image characters + references | `image_characters.py` | **Not exported.** Named, privacy-scoped subjects Jacob created. |
| Image conversational sessions | `image_sessions.py` | **Not exported.** "Keep his face, make his build broader" continuity state (#336). |
| Onboarding preferences (name, theme) | `onboarding.py` | **Not exported.** `PREFERRED_NAME_KEY` and `THEME_KEY` are owner-chosen values, stored in the same `app_settings` table as the rebuildable `ONBOARDING_COMPLETE_KEY` flag — split the fields or export the whole table as canonical. |
| Quick-capture inbox (metadata) | `desktop_store.py` (`data/inbox.jsonl`, `data/inbox_processed.jsonl`) | **Not exported.** Owner-authored capture text/metadata; this document's own "derived" section relies on this file as the source triage classifications are re-derived from. |
| Quick-capture uploaded files | `gateway/routes/capture.py` (`data/captures/`, via `POST /capture/file`) | **Not exported. Missed in the first pass.** The inbox row only stores a path/metadata reference; the actual uploaded PDFs/images/documents live in `data/captures/` and cannot be reconstructed from the inbox event or from lossy knowledge-base chunks. Needs file-content export, not just a metadata row. |
| Imported knowledge (Chroma) | `gateway/archivist.py` (`KNOWLEDGE_DB_PATH = data/knowledge_db`) | **Not exported. Missed in the first pass, explicitly named canonical by ADR 0037.** Not generally rebuildable: `gateway/routes/knowledge.py`'s URL-ingestion path deletes the downloaded source file in a `finally` block once its contents are stored in Chroma, so Chroma is the only retained copy. |
| Artifact metadata | `artifact_store.py` | **Not exported. Corrected — originally misfiled as execution evidence.** Rows carry `display_name`, `storage_uri`, `source_ref`, project/conversation/work-item associations, and custom `metadata`, not just ingestion status. ADR 0037 names "artifact metadata" as canonical explicitly. If files stay on disk but this table is lost, the *relationships* between artifacts and their owning project/conversation are gone even though the bytes survive. Operational fields (`ingestion_status`, `error`) can split out as execution evidence; the identity/association fields cannot. |
| Cron schedule definitions | `cron.py` | **Not exported. Corrected — originally misfiled as execution evidence.** `schedule()` persists owner-requested `name`, `action`, `schedule_type`, `schedule_value`, and `metadata` — configuration, not a record of what already ran. Only `last_run` is genuinely execution evidence; `enabled` is arguably either (it's a toggle, but it's the owner's toggle). Split before building the export. |
| Signals | `signal_store.py` | **Not exported. Corrected — originally misfiled as derived.** ADR 0037 explicitly lists signals as canonical personal state, and this document's own earlier claim ("losing old signals doesn't lose owner intent") is contradicted by the ADR: project resume, deadline sweeps, and life-awareness composition all consume signal history, and historical connector/system events generally can't be recreated by replaying current external APIs. |
| Physical inventory | `gateway/inventory.py` (`data/inventory.csv`) | **Not exported. Missed in the first pass.** Components extracted from owner-submitted photos — parts, quantities, notes, acquisition dates. The source photo is not retained after processing (per the module's own upload flow), so the CSV is the only copy. |
| Tutor learning state | `gateway/tutor.py` (`data/kitty/tutor_memory.db`) | **Not exported. Missed in the first pass** — this module opens SQLite via `gateway.db.connect(MEMORY_DB)` with a locally-named path constant, which the original module search didn't catch (see Method gap above). Vocabulary, confidence history, attempts, mastery, and review schedule — losing this resets Jacob's actual learning progress. |
| Web monitors | `gateway/web_monitor.py` (`data/web_monitors.db`) | **Not exported. Same method-gap miss.** Owner-configured URL/keyword watches; losing this silently deletes monitors the owner set up. |
| Real preference files | `config/PREFERENCES.md`, `config/user_profile.json`, `config/USER/*.md` (BELIEFS, GOALS, MISSION, MODELS, NARRATIVES, PROBLEMS, PROJECTS, WISDOM, TELOS) | **Not exported, not SQLite.** These are the actual preference/identity files — `storage_sync.export_preferences()` is a placeholder returning `{}` and doesn't touch any of them. The "Preferences" row in `storage_sync` should be treated as **currently unexported**, full stop, not partially covered. |

## Derived / rebuildable (reconstructable from canonical data or external sources)

| Store | Module | Notes |
|---|---|---|
| Temporal knowledge graph | `memory_weave.py` | Learns from corrections/tool failures; in principle re-derivable by replaying memory + journal history, but no replay tool exists today `(verify)`. |
| Triage classifications | `triage.py` (`inbox_triage` rows) | Re-runnable against `inbox.jsonl` since capture stays dumb by design (D4) and triage never mutates the source. |
| Weekly pattern mirror | `honcho.py` | Explicitly a summary over gateway traces/logs — regenerable if logs exist. |
| Model digest | `model_digest.py` | Cached record of model-catalogue changes for the morning brief; rebuildable from the provider APIs. |

Signals moved to canonical above (corrected). No other stores confirmed
derived this pass — the confidence here is lower than the canonical list
after two rounds of missed classifications; treat "derived" as
provisional per-store, not a verified bucket.

## Execution evidence (proves what the system did, not owner content)

| Store | Module |
|---|---|
| Builder queue/attempts/leases | `builder_queue_db.py`, `builder_runtime.py`, `builder_status.py`, `builder_status_readonly.py` |
| Action queue (proposed/approved/executed) | `action_queue.py` |
| Compute governor dispatch receipts | `compute_governor.py` |
| Cron run history (`last_run` only) | `cron.py` — split from the canonical schedule-definition fields above |
| Image job/plan/recipe records | `image_jobs.py`, `image_plans.py`, `image_recipes.py` |
| Insight-loop lifecycle | `insight_loop.py` |
| Artifact ingestion status (`ingestion_status`, `error` only) | `artifact_store.py` — split from the canonical metadata fields above |
| Expert/proactive state (snooze, inbox lifecycle) | `expert_state.py` |
| Next-step navigator cache | `next_step.py` |
| Composed "what's going on now" | `state_composer.py` (computed on read, not stored — likely `NOT NEEDED` for export, since it's a live projection, not a store) |
| Active-project scope | `project_context.py` |
| Buddy state | `buddy_store.py` |
| Onboarding completion flag (`ONBOARDING_COMPLETE_KEY` only) | `onboarding.py` — split from the canonical name/theme fields above |

None of these are owner-authored content; PAA-1's export is about owner
memory, so this bucket is lower priority for the manifest but still needs a
line in it (PAA's own spec wants every store classified, even ones excluded
from the export). Three rows above are now explicitly split from a
canonical counterpart rather than covering the whole source module.

## Secret (excluded by construction)

The actual artifacts to exclude, not the modules that read them
(`gateway/config.py` and `gateway/auth.py` are readers — `config.py` calls
`load_dotenv(PROJECT_ROOT / ".env")`, `auth.py` reads `GATEWAY_SECRET` from
the environment; neither file holds a credential itself):

- `.env` (repo root) — provider API keys and `GATEWAY_SECRET`.
- `data/gmail_token.json` — referenced in `gateway/doctor.py:211`; OAuth
  token for the Gmail connector.

`(verify)`: confirm no canonical store above embeds a secret inline (e.g. a
connector's OAuth token stored alongside its signal history) before writing
the real export, and check for other per-connector token files beyond
Gmail's — this pass only confirmed the one `doctor.py` names.

## Cache

No dedicated cache-only store found beyond `model_digest.py` (already
counted under derived, since it's both a cache of an external catalogue and
useful without re-fetching). No further cache-tier stores identified this
pass — though given how much this document's canonical count grew across
two review rounds, treat that as weak evidence, not a clean result.

## Net finding

The real PAA-1 gap isn't designing a schema — canonical/derived/secret/
cache/execution-evidence still maps cleanly onto existing module
boundaries. The gap is coverage and precision: `storage_sync.py` exports 4
stores cleanly, silently truncates 2 more at 1000 rows, and misses at least
15 canonical stores entirely — several of which (artifact metadata, cron
definitions, signals, onboarding preferences) were originally misclassified
in this very document as disposable, and would have been *designed out* of
a real export if the first draft had shipped unreviewed. Extending
`storage_sync.py` to full canonical coverage, fixing the truncation, and
splitting the three mixed canonical/execution-evidence tables (`cron`,
`artifact_store`, `onboarding`) is real engineering — schema per store,
import validation, a fresh-install semantic-parity test — and is the right
next PAA-1 slice, but is implementation work, not audit, so it isn't
attempted in this pass.

The pattern across two review rounds is the finding worth remembering: a
first-pass classification driven by docstrings and naming conventions
missed real owner data twice, in both directions (wrong bucket for stores
found, and stores never found at all via a name-pattern search). The next
PAA-1 slice should budget for a structural inventory pass, not another
docstring read, before trusting a manifest enough to build an export
against it.
