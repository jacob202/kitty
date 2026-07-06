# MemPalace migration runbook

Goal: move Kitty's episodic memory from **mem0** to **MemPalace** (local-first,
typed knowledge graph) — safely, and with a clean rollback.

This is written so you can follow it top-to-bottom without re-reading any code.
Everything here runs **on your machine** (the container can't install MemPalace).

> **Just want Claude to drive it?** Paste this into a session, on your machine,
> after `pip install mempalace`:
>
> > "Run the MemPalace migration from docs/MEMPALACE_MIGRATION_RUNBOOK.md. Start
> > with the preflight, show me its output, and stop before --execute so I can
> > confirm."

---

## Why a runbook (the one real risk)

The MemPalace adapter and migration were written **without** a MemPalace package
to test against. So two things must be *proven on real hardware* before trusting
them: (1) the **search/read** shape the adapter parses, and (2) the **ingest**
command the migration calls. The preflight proves #1 and shows you #2. Until the
preflight passes, do not run `--execute`.

Nothing is destructive: mem0 data is never modified, and MemPalace stays
off until you set the env flag — so rollback is trivial (step 8).

---

## 0. Prerequisites

```bash
cd /path/to/kitty
python3.11 -m pip install mempalace        # the only new dependency
ollama serve &                             # mem0's embedder must be reachable
```

## 1. Back up mem0 (belt and braces — the script also does this)

```bash
cp -r data/mem0 data/mem0_manual_backup_$(date +%Y%m%d)
```

## 2. Verify the package (read path + real CLI names)

```bash
python scripts/mempalace_preflight.py
```

- Must end in **`✓ PASS`**. If it fails, it tells you exactly what to fix.
- Read the printed **`mempalace --help`** block and note the real *ingest*
  subcommand (e.g. `add`, `remember`, `store`). You'll pass it in step 5.
- If the printed search JSON keys differ from `text`/`content`/`snippet` or
  `related`/`relations`, update `gateway/mempalace_adapter.py::_parse()` to match
  (it's a few lines), then re-run the preflight.

## 3. (If needed) confirm the search args match your version

The adapter runs `mempalace search <q> --limit N --json`. If your version differs,
update the argv in both `MemPalaceAdapter._search()` and the preflight, then re-run
step 2.

## 4. Dry-run the migration (writes nothing)

```bash
python scripts/migrate_mem0_to_mempalace.py
```

Confirm the printed count and sample look like your real memories. Still nothing
written.

## 5. Execute the migration

Use the ingest subcommand you saw in step 2 (example uses `add`):

```bash
python scripts/migrate_mem0_to_mempalace.py --execute --ingest-cmd "mempalace add"
```

- Backs up `data/mem0` first, writes a manifest to
  `data/mempalace_migration_state.json`, and **skips anything already migrated** —
  so if it's interrupted, just run the same command again to resume.

## 6. Enable MemPalace in Kitty

```bash
export KITTY_MEMPALACE_ENABLED=1        # add to .env to make it persistent
```

(With this set, `memory_graph` registers the adapter and MemPalace results join
the unified context. With it unset, Kitty behaves exactly as before.)

## 7. Verify it's live

```bash
python scripts/mempalace_preflight.py    # search now returns your migrated facts
```

Or start the app and ask Kitty something only your memories would know.

## 8. Rollback (if anything looks off)

```bash
unset KITTY_MEMPALACE_ENABLED            # and remove it from .env
```

mem0 is untouched, so Kitty is instantly back to its previous behaviour. Delete
`data/mempalace_migration_state.json` if you want a fully clean re-try.

---

## After migration — finish the two follow-ons

These were intentionally left for *after* the package is confirmed:

1. **Typed knowledge edges in `correlate()`** — the preflight prints whether
   search rows carry a `related`/`relations` field. Paste one populated row to
   Claude and it'll finish surfacing typed edges (currently a count) in
   `MemPalaceAdapter.correlate()`.
2. **Retire mem0 (optional)** — once you trust MemPalace, decide whether to make
   it the *primary* episodic store (swap `gateway/context_builder.py`'s memory
   source) or keep both. This is a deliberate, separate change with its own tests.

## What's tested in CI

`tests/test_mempalace_migration.py` covers the migration's pure logic — dry-run
writes nothing, idempotency/resume via the manifest, record normalization, and
that one failed item doesn't abort the run. These run **without** the MemPalace
package (all external calls injected/mocked), so CI stays green until you migrate.
