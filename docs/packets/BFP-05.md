# BFP-05-honest-gates — refuse a check that runs nothing and calls it green

**Initiative:** builder-frontend-proof-v1
**Owner:** builder
**Depends on:** BFP-04-authoring
**Free or paid:** free

## What Jacob can do after this

Trust that when Builder says a job passed its checks, checks were actually run.

## Why this is the next thing

`pytest.ini:5` reads:

```
addopts = -m "not integration and not controlled_live" --strict-markers
```

Every test in `tests/test_builder_runner.py` carries the `integration` marker. So
a packet whose gate is the perfectly ordinary-looking

```
python -m pytest -q tests/test_builder_runner.py
```

produces this:

```
no tests collected (89 deselected) in 0.08s
```

and exits **0**. The gate passes. It ran nothing. A worker could delete the
entire file's subject matter and this check would still report success. Every
packet in this initiative was drafted with that exact command before the
deselection was noticed, which is how confident the mistake looks.

This is not a hypothetical class of error: `docs/packets/PACKET_STANDARD.md` §6
already requires that "the gate must fail before the change and pass after", and
a gate that collects nothing can never fail, so it silently violates a rule the
standard has held since August. Preflight checks that the *paths* in a command
exist. It does not check that the command selects a single test.

## Plan

1. In `scripts/packet_preflight.py`, for each validation command that invokes
   pytest, run the same command with `--collect-only -q` and read the count.
2. Report an ERROR when the selection is empty. Name the file and the number
   deselected, and say that a marker expression is the fix. The message has to
   lead to `-m integration`, not to deleting the gate — a deleted gate is the
   worse outcome and the one a hurried reader will reach for.
3. Pass non-pytest commands through untouched; `ruff` and the like are out of
   scope for this check.
4. Keep it read-only. Collection must not execute a test, write a file, or leave
   a cache that changes a later run. Preflight's contract is that it mutates
   nothing, and that is why people are willing to run it.
5. Extend `tests/test_packet_preflight.py`: an all-deselected command is
   rejected, the same command with a marker expression is accepted, a
   non-pytest command is ignored, and a healthy manifest still exits 0.

## Not in scope

Changing `pytest.ini`. The default deselection is deliberate — integration tests
are slower and CI runs them separately — and this packet makes that default
visible rather than fighting it. Do not re-mark any existing test. Do not audit
or rewrite historical manifests under `data/kittybuilder/manifests/`; they are
preserved evidence, and the check applies to what gets authored from now on.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_packet_preflight.py
python -m ruff check scripts/packet_preflight.py
```

Today this collects 9 tests and passes, and preflight accepts a manifest whose
only gate is `python -m pytest -q tests/test_builder_runner.py` — the exact
command that proves nothing. After this packet that manifest is rejected with a
message naming the 89 deselected tests, and the same manifest with
`-m integration` is accepted.

**Tier 2 — running app.** Not applicable.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if collection cannot be made reliably read-only — for example
if it turns out that collecting a particular file imports something with a side
effect. A preflight that can change state is worse than no preflight, because
people run it casually and often, and a check nobody trusts to be safe is a check
nobody runs.

## Recovery

Revert `scripts/packet_preflight.py` to `HEAD`. If this check lands and starts
rejecting a manifest someone is mid-way through authoring, that rejection is
correct: fix the gate with a marker expression rather than reverting the check.
The one failure mode worth watching is a false positive on a command shape the
parser mishandles — if that happens, narrow the parser, never widen the pass.
