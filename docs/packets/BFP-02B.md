# BFP-02B-deps — an interpreter with nothing to run is not a toolchain

**Initiative:** builder-frontend-proof-v1
**Owner:** builder
**Depends on:** BFP-01-resolve, BFP-02-expose
**Free or paid:** free

## What Jacob can do after this

Still nothing visible. This is the step that was missing from the original five,
and without it none of the visual work can be checked by a worker.

## Why this is the next thing

BFP-01 and BFP-02 find `node` and put it on the worker's PATH. That is half the
problem, and the initiative was written as though it were all of it.

`npx vitest` does not run because `node` exists. It runs because
`gateway/kitty-chat/node_modules` exists — that is where the `vitest` executable
lives and where every import in the test resolves from. A Builder worktree has no
`node_modules`: the directory is gitignored, so it exists only in the checkout
that owns the repository. Exposing the interpreter and stopping there leaves
`npx vitest` failing on a missing executable, and `npx tsc` failing the same way.

That matters beyond this packet, because BFP-04 lifts the block on authoring
frontend gates. Lifting it after BFP-03 but without this packet would authorize
eight studio gates that still cannot execute — a check that cannot run, declared
runnable. That is the same class of defect as a gate collecting zero tests, which
this very initiative exists to remove in BFP-05.

Caught in review of this initiative on 2026-09-16, before any of it ran.

## Plan

1. Decide how the locked dependency tree becomes visible at
   `gateway/kitty-chat/node_modules` inside the worker's worktree. The
   constraints are firm and they are what make this a packet rather than a line:
   no network during the run, no writable access to the owning checkout's
   install, and a ten-minute budget that cannot absorb a fresh install.
2. A read-only view of the owning checkout's install is the cheapest candidate.
   It has a known failure recorded against it — a symlink taken as a shortcut
   broke a `next build` during the PR #886 work and had to be replaced with a
   real install — so if this route is taken, prove the exact command shapes run,
   do not assume resolution works because the directory is present.
3. Extend the sandbox read paths in `gateway/builder_execution_boundary.py` to
   cover whatever the dependency tree resolves through, including the real
   directory behind any link.
4. Fail loud when the dependencies cannot be provided. A worker that runs a
   frontend gate against a missing tree produces a failure that looks like the
   code under test is broken, which is the most expensive possible way to be
   wrong.
5. Keep the owning checkout read-only throughout. A throwaway worker with write
   access to the shared install can break every other lane on the machine, and
   the install is 574 MB that nobody wants rebuilt.

## Not in scope

Running `npm ci` inside the worker — no network, and the install alone would
consume the attempt budget. Vendoring or committing dependencies. The Vite cache
write path, which is BFP-03 and is a separate need: even with the tree readable,
Vite writes while it runs. Changing any frontend test, config, or dependency
version.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_builder_runner.py tests/test_builder_execution_boundary.py
python -m ruff check gateway/builder_runner.py gateway/builder_execution_boundary.py
```

`-m "integration or not integration"` is required: `tests/test_builder_runner.py`
is entirely integration-marked and `pytest.ini` deselects those by default, so
the plain command collects 11 of 100 tests and tells you nothing about the
runner.

**Tier 2 — running app.** The real proof, and the one BFP-04 depends on: a
recorded sandboxed run in which `npx vitest run <file> --reporter=dot` and
`npx tsc --noEmit` execute from `gateway/kitty-chat` and return a result. A
passing unit test about provisioning is not that evidence.

**Tier 3 — product acceptance.** Not applicable; nothing user-facing changes.

## Stop condition

Stop and escalate if the dependencies cannot be made resolvable without either
network access or write access to the owning checkout. Both are real limits, not
preferences: the sandbox has no network, and a worker that can write to the
shared install can break every lane on the machine. If neither can be honoured,
the honest outcome is that frontend gates stay unauthorable and BFP-04 does not
land — which is a worse outcome than today, but a truthful one.

## Recovery

Confined to the runner and the execution boundary, both of which are constructed
per launch, so reverting to `HEAD` fully restores current behaviour. Nothing
persists between runs. If an attempt leaves a link or mount behind in a worktree,
that worktree is disposable and should be removed rather than repaired.
