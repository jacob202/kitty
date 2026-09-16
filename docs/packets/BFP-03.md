# BFP-03-cache — give Vite the one folder it needs to write

**Initiative:** builder-frontend-proof-v1
**Owner:** builder
**Depends on:** BFP-01-resolve, BFP-02-expose, BFP-02B-deps
**Free or paid:** free

## What Jacob can do after this

Still nothing visible, but this is the step where a Builder worker can actually
run a UI test instead of just finding the program that runs it.

## Why this is the next thing

After BFP-02 a worker can execute `node`, and vitest will still fail. Vite writes
a dependency-optimisation cache while it runs. The sandbox built by
`gateway/builder_execution_boundary.py` grants write access to a short list of
paths (`write_paths`, threaded through at lines 80, 95, 109 and 182) and denies
everything else, so the first cache write is refused and the run dies.

The naive fixes are both wrong and both have already cost time here. Making the
shared `gateway/kitty-chat/node_modules` writable would let a throwaway worker
corrupt the 574 MB install the whole machine shares. Symlinking that directory
into the worker's worktree is the shortcut that broke a build during the PR #886
work and had to be replaced with a real install. The correct move is smaller:
point Vite's cache at a directory inside the run directory, which is per-run and
already disposable, and grant write access to exactly that.

## Plan

1. Add a scoped writable-cache parameter to the boundary in
   `gateway/builder_execution_boundary.py`, following the existing `write_paths`
   plumbing rather than inventing a second mechanism.
2. In `gateway/builder_runner.py`, choose a cache directory beneath the existing
   per-run `run_dir` and pass it in. Do not place it in the worktree, and never
   inside `node_modules`.
3. Add `gateway/kitty-chat/vitest.config.ts` to the packet fence and configure
   Vite's `cacheDir` from `KITTY_BUILDER_VITE_CACHE_DIR`, defaulting to the
   existing project cache location outside Builder. Set that variable to the
   per-run directory alongside the Node exposure added in BFP-02.
4. Prove the fence still holds: a test asserting a path *outside* the granted
   directory is still refused. A packet that widens a sandbox has to show what it
   did not widen — that assertion is the point of this packet, not a nicety.
5. Cover the boundary change in `tests/test_builder_execution_boundary.py` and
   the runner wiring in `tests/test_builder_runner.py`.

## Not in scope

Running an actual vitest invocation inside the sandbox as part of this packet's
Tier 1 — the gates here stay Python.

Making the dependency tree resolvable at all: that is BFP-02B, which this packet
now depends on. The two are separate needs and both are required. BFP-02B makes
`node_modules` readable from the worktree; this packet makes the single directory
Vite writes to writable. Neither alone is enough.

Changing `gateway/kitty-chat/vitest.config.ts`: another lane is already editing
that file in `.worktrees/fix-ui-test-env-20260916`, and touching it here would
collide.

The exact `npx vitest` and `npx tsc` shapes stay prohibited in authored packets
until a sandboxed run proves the dependencies are available without network
access or writable shared state. BFP-04 owns lifting that prohibition and may
only do so against that recorded evidence.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_builder_execution_boundary.py tests/test_builder_runner.py
python -m ruff check gateway/builder_execution_boundary.py gateway/builder_runner.py
```

The marker expression is deliberate: `tests/test_builder_runner.py` is entirely
integration-marked and `tests/test_builder_execution_boundary.py` is not, so
plain `pytest` would silently run 11 of the 100 tests. Today this command
collects 100 and passes; after this packet it passes with the new cache and
refusal cases included.

**Tier 2 — running app.** The real proof that Node now works end to end is a
worker running `npx vitest run` inside the sandbox and getting a result rather
than a permission error. Record that run's log in the packet's evidence. This is
the first moment the initiative's claim is testable rather than argued.

**Tier 3 — product acceptance.** Not applicable; nothing user-facing changes.

## Stop condition

Stop and escalate if Vite cannot be pointed at a cache directory outside
`node_modules` by configuration alone. Widening the sandbox to cover a shared
checkout is not an acceptable alternative and is not the worker's call to make —
a throwaway worker with write access to the shared install can break every other
lane on the machine.

## Recovery

If an attempt leaves the boundary half-changed, revert both
`gateway/builder_execution_boundary.py` and `gateway/builder_runner.py` to `HEAD`
and re-run; the sandbox is constructed per launch, so a reverted file fully
restores previous behaviour. If a run already created a stale cache directory
under a run directory, it is disposable — delete it. Never resolve a failure here
by removing the write-refusal test.
