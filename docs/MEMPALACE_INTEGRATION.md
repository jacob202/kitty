# MemPalace integration (Phase 4)

[MemPalace](https://github.com/MemPalace/mempalace) is a local-first semantic memory
system (Python, MIT, ChromaDB-backed) with verbatim storage and a **typed knowledge
graph with temporal validity windows**. It's the chosen vehicle for closing Kitty's
"typed relationship graph" gap (see `docs/PAI_GAP_ANALYSIS.md`).

## Architecture decision

MemPalace is wired as a **`StoreAdapter` behind `memory_graph`**, not as a separate
always-on service. This keeps Kitty's deep-module pattern intact (one unified
`memory_graph` API; backends are implementation details) and avoids operating a
sidecar. The standalone MCP-server mode remains an option later if other clients
(Claude Code, etc.) should share Kitty's memory.

## Status: scaffolded, OFF by default

`gateway/mempalace_adapter.py` implements `MemPalaceAdapter`. It is appended to the
active adapter list by `memory_graph._default_adapters()` **only** when enabled, so
the default hot path is byte-for-byte unchanged. When disabled, missing, or erroring,
`fetch()` returns `[]` and the unified context is unaffected.

## Enabling it

```bash
pip install mempalace
export KITTY_MEMPALACE_ENABLED=1
```

Then index sources MemPalace should know about, e.g.:

```bash
mempalace mine ~/notes
mempalace mine ~/.claude/projects/ --mode convos
```

## ⚠️ Verify before trusting (the one uncertain bit)

The actual query call is isolated in `MemPalaceAdapter._search()`. It shells out to
the documented CLI (`mempalace search <query> --limit N --json`) because the CLI is
the most stable interface. **Confirm against your installed MemPalace version:**

1. Run `mempalace search "test" --limit 5 --json` and check the JSON shape.
2. `_parse()` already tolerates `list` and `{"results": [...]}` shapes and the keys
   `text` / `content` / `snippet`, plus `related` / `relations`. Adjust if your
   version differs.
3. If you prefer the Python API (`import mempalace`) over the CLI, swap the body of
   `_search()` — the rest of the adapter (gating, formatting, correlation, graceful
   degradation) stays the same.

## Tests

`tests/test_mempalace_adapter.py` covers: disabled-by-default, graceful degradation
when the CLI is absent, JSON-shape tolerance, formatting/correlation, and that the
adapter is registered only when the env flag is set.

## Migrating mem0 → MemPalace

When you're ready (on your machine, with the package installed), follow the
copy-paste runbook: **`docs/MEMPALACE_MIGRATION_RUNBOOK.md`**. Tooling is ready:

- `scripts/mempalace_preflight.py` — proves the read path + reveals the real CLI
  ingest subcommand. **Run this first.**
- `scripts/migrate_mem0_to_mempalace.py` — dry-run by default, non-destructive,
  idempotent/resumable, backs up `data/mem0`, isolates the one unverified ingest
  call behind `--ingest-cmd`.
- `tests/test_mempalace_migration.py` — CI-safe (no package needed).

## Follow-on (not yet done)

- Decide whether MemPalace should **replace** the `mem0`-based `memory.py` episodic
  store, or run alongside it. (mem0 can phone home; MemPalace is fully local — the
  local-first argument favours migration, but that's a separate change with its own
  data-migration step and tests.)
- Surface MemPalace's temporal-validity metadata in `correlate()` once the query
  shape is confirmed (the preflight prints whether rows carry `related`/`relations`).
