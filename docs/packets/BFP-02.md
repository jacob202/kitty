# BFP-02-expose — hand the worker the Node it just found

**Initiative:** builder-frontend-proof-v1
**Owner:** builder
**Depends on:** BFP-01-resolve
**Free or paid:** free

## What Jacob can do after this

Still nothing visible — this is step two of five. After it, a Builder worker can
run `node` and `npx` at all, which it cannot do today.

## Why this is the next thing

BFP-01 produces a durable Node path and nothing consumes it. The consuming code
already exists for Python and is three lines:

```python
if validation_venv is not None:
    child_env["VIRTUAL_ENV"] = str(validation_venv)
    child_env["PATH"] = f"{validation_venv / 'bin'}:{child_env['PATH']}"
```

(`gateway/builder_runner.py:1626-1628`), plus the read roots reaching the
sandbox at `gateway/builder_runner.py:1684` as
`extra_read_subpaths=validation_read_roots`. Node needs the identical treatment
and nothing more clever. Both halves matter: `PATH` alone lets the worker *name*
node, and the Seatbelt sandbox then refuses to *read* it.

## Plan

1. Call `_node_toolchain(root)` next to the existing `_validation_toolchain(root)`
   call at `gateway/builder_runner.py:1602`.
2. Prepend the Node bin directory to `child_env["PATH"]`. Order matters: the
   Python venv entry must keep winning for `python`, so add Node without
   displacing it.
3. Merge the Node read roots into the list passed as `extra_read_subpaths`, so
   the sandbox can read the interpreter and its libraries.
4. Keep both behind the same `is not None` guard style already used, so a host
   with no Node produces exactly today's environment. This is the criterion that
   makes the change safe to land before anything depends on it.
5. Cover both branches in `tests/test_builder_runner.py`: Node present, and Node
   absent leaving the environment untouched.

## Not in scope

The Vite cache write path — that is BFP-03, and vitest will still fail after this
packet because of it. That is expected and is not a defect in this packet. Do not
touch `gateway/builder_execution_boundary.py`. Do not add any frontend gate to
any manifest yet; preflight still rejects them until BFP-04.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m integration tests/test_builder_runner.py
python -m ruff check gateway/builder_runner.py
```

`-m integration` is required: without it `pytest.ini:5` deselects all 89 tests in
this file and the command exits 0 having run none of them. Today the gate passes
with 89 tests and no Node ever reaches `child_env`; after this packet the new
branch tests are included and the environment carries a Node bin directory.

**Tier 2 — running app.** Not applicable.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if exposing Node cannot be done without reordering the Python
venv ahead of or behind something else that already depends on that order. The
Python toolchain is load-bearing for every existing packet; a frontend capability
is not worth destabilising it, and that trade is not the worker's to make.

## Recovery

Additive and confined to the environment-construction block plus tests. Revert
`gateway/builder_runner.py` to `HEAD` and re-run. No run directory, worktree or
queue state is affected by a failure here, because the change only takes effect
when the next worker launches.
