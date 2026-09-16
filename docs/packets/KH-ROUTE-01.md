# KH-ROUTE-01 — refuse a route that names a model nothing serves

**Initiative:** kitty-hardening-v1
**Owner:** builder
**Depends on:** none
**Free or paid:** free

## What Jacob can do after this

Find out that Builder is pointed at a model that does not exist by running
`kitty builder initiative doctor`, instead of by noticing a day later that
nothing was built.

## Why this is the next thing

This is the outage of 2026-09-15. Builder was switched on and executed nothing
for a day. `config/builder_paid_routes.json` named
`openrouter/deepseek/deepseek-v4.1-flash`; the provider block in
`opencode.jsonc` registered only `deepseek-v4-flash`. Every dispatch died the
same way:

```
kitty-dsh: UNKNOWN_MODEL: pi-ai provider "openrouter" has no configured model
"deepseek/deepseek-v4.1-flash"
ERROR: every paid model failed cleanly without producing a result
```

Task `kb_mu3mf8yo_6762` burned all three attempts across runs
`run_mu3mjrh2_a37b`, `run_mu3n36xr_04a2` and `run_mu3nmmyt_57bb`, then blocked
its packet.

Two things made it invisible. No money moved, because the provider rejected the
request before billing, so the spend ledger showed a quiet week rather than a
broken one. And nothing validates a route against the registry, so a config that
cannot possibly work looks exactly like one that can. The repair that followed
also went the wrong way first — it edited the route down to the old model, and
only the tests pinning the upgraded pair caught it.

The gap is narrow and worth closing precisely: a route is a promise about a
model, and nothing checks the promise against the list of models this repository
is willing to serve.

## Plan

1. In `gateway/builder_paid_routing.py`, read the openrouter provider block from
   `opencode.jsonc` and check every model a route names against it.
2. Fail resolution with a message naming both the model and `opencode.jsonc`.
   The reader's next move is to register the model or correct the route, and the
   message should make clear which file holds each.
3. Validate reviewer fallbacks on the same terms. A fallback that cannot serve is
   the same outage one step later, and is worse because it only appears once the
   primary has already failed.
4. Surface it in `gateway/doctor.py` as a FAIL that lists every offending route.
   Stopping at the first would have hidden that both cheap and frontier were
   broken, which is exactly what happened when this was diagnosed by hand.
5. Keep a healthy configuration silent. A check that reports something on a good
   day gets filtered out on a bad one.

## Not in scope

Fixing any route this check finds — `KH-FRONTIER-01` owns the frontier route,
and the cheap route is already repaired. Validating against the provider's live
catalogue over the network; the failure being caught is local configuration
disagreeing with itself, and a network call on the doctor path is a new failure
mode rather than a fix. Changing what any route is set to.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_builder_paid_routing.py tests/test_doctor.py
python -m ruff check gateway/builder_paid_routing.py gateway/doctor.py
```

The marker expression is not decoration: `pytest.ini` deselects
integration-marked tests by default, and a gate that collects nothing still
exits 0. Today these two files collect 27 and 75 tests and pass, and no
validation of route models exists; after this packet the new cases are included
and an unregistered model fails resolution.

**Tier 2 — running app.** Not applicable; no user-visible surface changes.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if the provider registry cannot be read without importing
something that starts a provider client or reaches the network. The doctor must
stay cheap and offline; a check that can hang is worse than the gap it closes,
because people stop running it.

## Recovery

Additive and confined to two modules plus their tests. Revert both to `HEAD` and
re-run. The check has no persistent state, so a failed attempt leaves nothing
behind. If it lands and immediately reports a FAIL, that is the check working —
the frontier route is known-broken and `KH-FRONTIER-01` removes it.
