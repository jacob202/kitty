# Deepening

How to deepen a cluster of shallow modules safely, given its dependencies. Assumes the vocabulary in [LANGUAGE.md](LANGUAGE.md) — **module**, **interface**, **seam**, **adapter**.

## Dependency categories

When assessing a candidate for deepening, classify its dependencies. The category determines how the deepened module is tested across its seam.

### 1. In-process

Pure computation, in-memory state, no I/O. Always deepenable — merge the modules and test through the new interface directly. No adapter needed.

### 2. Local-substitutable

Dependencies that have local test stand-ins (PGLite for Postgres, in-memory filesystem). Deepenable if the stand-in exists. The deepened module is tested with the stand-in running in the test suite. The seam is internal; no port at the module's external interface.

### 3. Remote but owned (Ports & Adapters)

Your own services across a network boundary (microservices, internal APIs). Define a **port** (interface) at the seam. The deep module owns the logic; the transport is injected as an **adapter**. Tests use an in-memory adapter. Production uses an HTTP/gRPC/queue adapter.

Recommendation shape: *"Define a port at the seam, implement an HTTP adapter for production and an in-memory adapter for testing, so the logic sits in one deep module even though it's deployed across a network."*

### 4. True external (Mock)

Third-party services (Stripe, Twilio, etc.) you don't control. The deepened module takes the external dependency as an injected port; tests provide a mock adapter.

## Seam discipline

- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't introduce a port unless at least two adapters are justified (typically production + test). A single-adapter seam is just indirection.
- **Internal seams vs external seams.** A deep module can have internal seams (private to its implementation, used by its own tests) as well as the external seam at its interface. Don't expose internal seams through the interface just because tests use them.

## Testing strategy: replace, don't layer

- Old unit tests on shallow modules become waste once tests at the deepened module's interface exist — delete them.
- Write new tests at the deepened module's interface. The **interface is the test surface**.
- Tests assert on observable outcomes through the interface, not internal state.
- Tests should survive internal refactors — they describe behaviour, not implementation. If a test has to change when the implementation changes, it's testing past the interface.

## Structural moves: splitting and relocating modules

A split or relocation is a pure refactor: the observable surface must not
change. What the 2026-09-16 route-layer split taught, in order of how it bit:

- **Sweep references completely.** Use `grep -rln` (names only) for the module
  path — never a truncated content grep — and remember the import graph is not
  the reference graph: lazy imports inside function bodies and path-string test
  fixtures reference the module too. The `routes/extended.py` split touched 26
  files, and two incomplete sweeps let missed lazy imports reach the test run
  instead of the sweep.
- **Hold the surface invariant.** For a route-layer move in Kitty, compute
  `app.openapi()["paths"]` (with the repo venv) plus each path's method set,
  sorted, before and after — byte-identical output is proof the API did not
  move, stronger than any unit test. Pair it with the route-registration and
  duplicate-operation-id tests.
- **Claim the old path, not just the new one.** Kitty's mutation fence checks
  staged paths against active coordination claims; deleting a claimed path — or
  one another resource maps, like `ui:action-grammar` here — is blocked until a
  claim covers the *old* path. Add it to `coordination/resources.yaml` under a
  claimed scope, claim that scope, then drop the dead entry in a follow-up
  commit so the registry holds no ghost paths.
