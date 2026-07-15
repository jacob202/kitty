# KittyBench

Regression benchmarks for the KittyBuilder pipeline. Each fixture tests a
core behavior that must not regress across refactors.

## Fixture selection criteria

- **Deterministic** — no LLM calls, no network, no filesystem state that varies
- **Fast** — each test under 500ms
- **High-signal** — exercises a boundary the unit tests might miss
- **Stable** — passes on current HEAD, unlikely to flake

## Adding a fixture

1. Identify a shipped packet whose validation is deterministic
2. Extract the validation into a test function
3. Document: packet ID, what it tests, why chosen
4. Name the file `test_packet_<id>.py`

## Current fixtures

| File | Packet | What It Tests | Why Chosen |
|---|---|---|---|
| `test_builder_state_machine.py` | KB-S1 | Queue state transitions, lease fencing, illegal transitions | Core of the Builder execution model |
| `test_isc_criteria.py` | ISA-lite | Success criteria derivation, checking, formatting, parsing | Used by every Builder packet |

## Running

```bash
python3.12 -m pytest tests/bench/ -v
```
