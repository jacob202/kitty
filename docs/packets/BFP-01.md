# BFP-01-resolve — find a Node that will still be there tomorrow

**Initiative:** builder-frontend-proof-v1
**Owner:** builder
**Depends on:** none
**Free or paid:** free

## What Jacob can do after this

Nothing visible yet — this is the first of five steps that let Builder build and
check the look of the app instead of only the machinery underneath it.

## Why this is the next thing

Builder hands each worker a Python environment and nothing else. The proof is
blunt: `grep -ci node gateway/builder_runner.py` returns **0**. The runner has
never heard of Node. `_validation_toolchain` at `gateway/builder_runner.py:227`
looks for `venv/` or `.venv/`, puts its `bin` on the child `PATH`
(`gateway/builder_runner.py:1626-1628`) and passes its read roots to the sandbox
(`gateway/builder_runner.py:1684`). There is no second function doing the same
for Node, so no worker can run a single frontend check.

The trap that makes this its own packet: on this machine `which node` resolves to

```
/Users/jacobbrizinnski/.local/state/fnm_multishells/842_1789519811103/bin/node
```

That directory is named for the shell that created it. It is correct in the
shell you are reading this in and gone by the time an overnight worker starts. A
worker handed that path fails with `node: command not found` and burns an
attempt on an error that has nothing to do with the work. The durable install is

```
/Users/jacobbrizinnski/.local/share/fnm/node-versions/v22.23.2/installation/bin
```

Resolving to the durable path — and proving in a test that the per-shell one is
rejected — is the whole job here.

## Plan

1. Add `_node_toolchain(repo_root)` beside `_validation_toolchain` in
   `gateway/builder_runner.py`. Same return shape: `(bin_dir | None, read_roots)`.
2. Resolve in order: an explicit override environment variable if one is already
   honoured nearby, then the fnm `node-versions/*/installation/bin` directories,
   then a system install. Reject any candidate whose path contains a
   `fnm_multishells` segment — that is the risk this packet exists to remove.
3. Return `(None, [])` when nothing resolves. Never raise: this runs on the
   launch path, and an exception here kills a run before the worker starts.
4. Read the filesystem only. Do not shell out to `node --version` to verify a
   candidate; a subprocess on the launch path can hang, and existence plus the
   executable bit is enough.
5. Extend `tests/test_builder_runner.py` with the cases in the acceptance
   criteria, including a fake multishell directory that must lose to a stable one.

## Not in scope

Putting Node on the worker `PATH` — that is BFP-02. Sandbox write paths — BFP-03.
Do not touch `scripts/packet_preflight.py`; it is BFP-04's and sharing it here
would collide. Do not install, upgrade or pin a Node version, and do not add a
dependency.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m integration tests/test_builder_runner.py
python -m ruff check gateway/builder_runner.py
```

Note the `-m integration` — every test in that file carries the `integration`
marker and `pytest.ini:5` deselects it by default, so the command without it
reports `no tests collected (89 deselected)` and exits **0** having proved
nothing. Today the gate passes with 89 tests in ~40s and no `_node_toolchain`
exists; after this packet the same command passes with the new cases included.
Because a new test cannot fail before it is written, the honest check for a
reviewer is: the named tests exist, and they fail when `_node_toolchain` is
reverted.

**Tier 2 — running app.** Not applicable. Nothing user-visible changes.

**Tier 3 — product acceptance.** Not applicable for the same reason.

## Stop condition

Stop and escalate if no Node installation can be resolved anywhere on the host
without running a subprocess or reaching the network. Returning `(None, [])` is
the correct answer to "Node is absent"; inventing a path, shelling out to find
one, or adding an install step is not, and the rest of the initiative is built
on this function being cheap and honest.

## Recovery

Safe to re-run from scratch: the change is additive and confined to one function
plus its tests. If a half-finished attempt leaves a broken
`gateway/builder_runner.py`, revert that file to `HEAD` and start again — no
state outside the worktree is touched.
