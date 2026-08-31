# KT-RESTORE-01 — Restoring a backup gives back exactly what was backed up

**Initiative:** `kitty-finish-truth-20260831-v2`
**Owner:** builder
**Depends on:** none
**Free or paid:** free
**Base:** `origin/main` `295b92fc33a3f1b93da86f3c6bb5fbb54e367105`
**Findings:** `XCUT-B004`, `XCUT-B005`

## What Jacob can do after this
Restore a backup and get back exactly what he backed up, instead of a second copy of everything he already had.

## Why this is the next thing
`gateway/storage_sync.py:187` — `import_all` is documented as replacing every migrated store. It does not. `gateway/storage_sync.py:97` — `import_memories` calls `add_memory` once per record, and the journal import behaves the same way, so a restore is an append. Restore the same file twice and every memory exists three times. This is the only defect in the slate that damages durable data permanently and silently, which is why it goes first.

Separately, `gateway/storage_sync.py:65` — `export_preferences` returns `{}` with a docstring calling it a placeholder, while the module header advertises exporting user data. Every backup taken so far is missing preferences and says nothing about it.

Verified present at the base SHA above.

## Plan
1. Read `gateway/storage_sync.py` end to end. Note which stores `import_all` covers and how each one currently writes.
2. Write the failing tests first in `tests/test_storage_sync.py`: import the same snapshot twice and assert the record counts equal a single import; assert a record present only before the import is gone afterwards; assert `export_preferences` returns real records. Run them and watch them fail.
3. Change each per-store import so the store ends holding the snapshot's records and nothing else. Replace, do not append.
4. Make a part-way failure safe: a store must not be left holding a mixture of old and new records, and the error must say in plain language which store failed.
5. Implement `export_preferences` against the real preferences store.
6. Re-run the tests and the rest of `tests/test_storage_sync.py`.

The risk is step 3: "replace" must not become "delete everything, then fail". Handle the failure path before you delete anything.

## Not in scope
The snapshot file format or its version check. Any HTTP route, CLI command, or UI for backup and restore — whether backup becomes a real screen is an open product decision (`XCUT-B003`). Any store `import_all` does not already cover.

## Verification
**Tier 1 — mechanical.** `python -m pytest -q tests/test_storage_sync.py`. Today no test asserts idempotent restore or non-empty preference export; the tests you add in step 2 must fail against the base SHA and pass after.

**Tier 2 — running app.** None. This packet adds no user-visible surface.

**Tier 3 — product acceptance.** Not required: no user-facing change. If that stops being true, the packet has grown past its fence — stop and split.

## Stop condition
If a store cannot be replaced without a schema or format change, stop. Changing the snapshot format is a separate decision, not something to infer mid-packet.

## Recovery
Nothing here is destructive to the repository; the fence is one module plus tests. If the run fails part-way, the next worker re-reads `storage_sync.py` and starts from step 2. No durable Kitty data is touched by the packet itself — the tests must use a temporary data root, never the real one.
