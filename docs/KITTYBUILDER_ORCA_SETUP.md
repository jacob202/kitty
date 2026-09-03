# KittyBuilder Orca Setup — Historical Compatibility Pointer

Orca/OpenCode was an earlier experimental Builder execution arrangement. It is
not the current default worker/reviewer path. The full former setup guide is
preserved at
[`archive/legacy-snapshots/KITTYBUILDER_ORCA_SETUP.md`](archive/legacy-snapshots/KITTYBUILDER_ORCA_SETUP.md).

Current Builder operation is owned by:

- [`KITTYBUILDER_QUICKSTART.md`](KITTYBUILDER_QUICKSTART.md) — queue, attempts,
  leases, publication, recovery, and supported CLI;
- [`FREE_WORKERS.md`](FREE_WORKERS.md) — current DSH `--free` / governed `--paid`
  worker and independent-review routing;
- `gateway/builder_cli.py` and tracked DSH adapter/config files — executable
  routing contract.

Do not infer current model routing, ownership, approval tiers, or publication
behavior from the archived Orca/OpenCode guide.
