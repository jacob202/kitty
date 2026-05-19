# Kitty scripts

Run from repo root with `PYTHONPATH=.` or `./venv/bin/python`.

## Layout

| Directory | Purpose |
|-----------|---------|
| `curation/` | Book/KB pipeline: dedup, ingest, canonical library, curation workers |
| `ops/` | Gateway ops, spend reports, Open WebUI tooling, agent helpers |

## Common commands

```bash
# Spend estimate (shim at repo root still works)
python3 scripts/spend_report.py --since 2026-05-18

# KB assignment
python3 scripts/assign_kb_files.py --dry-run

# Curation worker (orchestrated from scale_curation / dispatch_pilot)
python3 scripts/curation/curation_worker.py <book_id> <source_path>
```

## Root shims

`scripts/spend_report.py` and `scripts/assign_kb_files.py` forward to `ops/` and `curation/` so existing docs and habits keep working.
