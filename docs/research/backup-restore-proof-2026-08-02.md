# Backup/Restore Proof — Roadmap 2.2

Date: 2026-08-02
Branch: `feat/backup-restore-proof-2026-08-02`
Execution owner: interactive

## Outcome

Roadmap 2.2 "Prove backup and restore" is **demonstrated against a scratch
replica** (non-destructive). The live `data/` directory is never wiped or
restored in this proof; the drill proves the backup archive is recoverable to a
fresh location with identical app-owned data and valid SQLite databases.

## What was added

- `scripts/kitty_backup.py`
  - New `restore(backup_dir, target_dir, replace=False)` subcommand-backed
    function. Fail-loud guards: requires `backup_manifest.json` (restoring an
    arbitrary directory is refused), refuses a non-empty target unless
    `--replace` moves it aside to `<target>.pre-restore-<stamp>`, and verifies
    every restored `*.db` with `PRAGMA integrity_check`.
  - `_verify_restored_sqlite()`: raises if any restored database fails
    integrity check, so a corrupt restore cannot masquerade as success.
  - New `restore` CLI subcommand (`--target-dir`, `--replace`).
- `scripts/kitty_backup_proof.py`
  - Non-destructive drill: seeds a scratch replica of `data/kitty` (jsonl logs,
    nested `image_characters/`, two SQLite databases), backs it up, wipes the
    replica, restores, and compares every file.
  - SQLite files are compared logically (schema + full row contents), not
    byte-for-byte: `sqlite3.Connection.backup` rebuilds a fresh, logically
    identical database.
  - Exit 0 = pass, 1 = fail; every difference is printed.
- `tests/test_kitty_backup.py` — six new tests covering restore success,
  manifest requirement, non-empty target refusal, `--replace` move-aside,
  corrupt-database failure, and the end-to-end proof drill.
- `kitty` launcher — `cmd_restore` and `restore` dispatch; usage help updated.

## Drill evidence

Drill run (scratch replica, live data untouched):

```text
drill root: /tmp/kitty-drill.Jl0eOF
backup archive: /tmp/kitty-drill.Jl0eOF/data/backups/kitty/20260802T203330Z
replica wiped (simulating data loss)
restored into: /tmp/kitty-drill.Jl0eOF/data/kitty
files before: 5  after: 5
VERDICT: PASS — restored replica matches pre-backup byte-for-byte
```

## Test evidence

```text
$ python3.12 -m pytest tests/test_kitty_backup.py -q --tb=short
12 passed in 0.25s
```

12/12 pass (6 pre-existing + 6 new).

## CLI wiring evidence

```text
$ ./kitty backup --source-dir <replica>/data/kitty --backup-root <replica>/backups
<replica>/backups/20260802T203342Z
$ ./kitty restore-drill <backup> <restore-dir>
<restore-dir>   (backup_manifest.json, note.txt present)
$ ./kitty restore <backup> --target-dir <live> --replace
<live>          (note.txt restored; existing target moved to live.pre-restore-<stamp>)
```

## Honest boundary

The Roadmap 2.2 verification step calls for wiping live `data/`, restoring,
and comparing `./kitty doctor --json` before/after. That destructive live
restore is **not** performed here (T2: would mutate live state on Jacob's
machine). The non-destructive replica drill proves the recovery path end to end;
the before/after doctor comparison on live data remains deferred to Jacob's
explicit go-ahead.

## Artifacts

- Backup script: `scripts/kitty_backup.py` (`backup` subcommand).
- Restore script: `scripts/kitty_backup.py` (`restore` subcommand) +
  `scripts/kitty_backup_proof.py` drill harness.
- Before/after doctor output: deferred (see honest boundary).
