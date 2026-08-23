# Testing Kitty

This file documents the test tiers that actually exist on `main`. Keep it aligned with `pytest.ini`, `Makefile`, `gateway/kitty-chat/package.json`, and `.github/workflows/tests.yml`.

## Current taxonomy

| Tier | Runner | Normal PR requirement? | External network / paid providers? |
| --- | --- | --- | --- |
| Python required suite | pytest | Yes for code scope | No |
| Frontend unit/component | Vitest | Yes for frontend scope | No |
| Browser smoke | Playwright | Yes for frontend scope | No |
| Controlled-live provider probes | pytest `controlled_live` | Never | Explicit opt-in only; currently empty |

There is **no separate Python `integration` tier today**. Hermetic tests that use `tmp_path`, temporary SQLite databases, FastAPI `TestClient`, subprocesses, or multiple Kitty components remain in the normal Python suite when they are cheap and important.

`browser` and `merge_gate` are not pytest tiers. Browser tests live under `gateway/kitty-chat/tests/smoke/` and use Playwright. `merge-gate` is the GitHub Actions aggregation job for required deterministic evidence.

Python commands assume the repository's Python 3.12 environment has `requirements.txt`, pytest, pytest-asyncio, and pytest-cov installed. Frontend commands assume `npm ci` has been run and Playwright Chromium is installed.

## Python: default required suite

From the repository root:

```bash
make test
```

For local parity with the Python PR coverage gate:

```bash
make test-ci
```

`pytest.ini` excludes only `controlled_live`. Normal tests run with Kitty's test harness, which forces test mode, uses a temporary runtime data root, removes paid-provider credentials, disables paid image generation, blocks canonical runtime mutation, and blocks non-loopback network access.

Target one Python file:

```bash
python3.12 -m pytest tests/test_test_harness_network_guard.py -q
```

Target one Python test:

```bash
python3.12 -m pytest tests/test_test_harness_network_guard.py::test_external_dns_is_blocked_before_network_io -q
```

Profile the 50 slowest tests using the same default selection:

```bash
python3.12 -m pytest tests/ -q --tb=short --durations=50
```

## Frontend: Vitest

Run all unit/component tests:

```bash
cd gateway/kitty-chat && npm test
```

Target one frontend test file:

```bash
cd gateway/kitty-chat && npm test -- tests/AsyncState.test.tsx
```

Target one named frontend test:

```bash
cd gateway/kitty-chat && npm test -- tests/AsyncState.test.tsx -t "renders loading state"
```

## Browser: Playwright smoke

The standard browser target builds the production Next.js UI, then runs the Playwright smoke matrix. The suite uses local seams and does not require a paid provider:

```bash
make smoke-test
```

The stronger hermetic target starts fake LiteLLM plus a real Gateway against temporary state and exercises browser → Gateway → storage end to end:

```bash
make smoke-test-hermetic
```

Target one standard Playwright spec after a production build exists:

```bash
cd gateway/kitty-chat && npm run test:smoke -- tests/smoke/boot.spec.ts
```

The Playwright configs bind isolated loopback ports. The standard config excludes `chat-real-gateway.spec.ts`; the hermetic config selects the real-Gateway seam and PR #528 acceptance coverage. Neither tier authorizes external provider traffic.

## Controlled-live provider probes

`controlled_live` is a reserved pytest safety boundary for deliberately authorized external-provider contract probes. It is not part of PR CI, push-to-main CI, or nightly health, and there are currently **no tests marked `controlled_live`**.

Inspect the current selection without making a provider call:

```bash
python3.12 -m pytest --collect-only -q -m controlled_live
```

With the current empty selection, pytest exits 5 after reporting no selected tests. That is an inventory result, not a product-test failure.

Before a future controlled-live test can open external network access, the harness requires explicit live authorization, explicit charge authorization, exactly one allowed external request, and a declared maximum cost no greater than USD $0.10. The opt-in invocation contract is:

```bash
KITTY_TEST_ALLOW_LIVE=1 \
KITTY_TEST_CHARGE_OK=1 \
KITTY_TEST_LIVE_MAX_REQUESTS=1 \
KITTY_TEST_MAX_COST_USD=0.10 \
python3.12 -m pytest -m controlled_live -q
```

Do not set those flags around the normal suite. Paid/live execution remains an explicit operator choice and is never needed to validate this testing architecture.

## What CI runs

`.github/workflows/tests.yml` is scope-aware on pull requests and pushes to `main`:

- `code=true`: pytest runs the normal hermetic suite with `gateway` coverage required at 73%, alongside Ruff and mypy.
- `frontend=true`: the `kitty-chat` job runs Vitest and a production build; `browser-smoke` then runs both Playwright browser tiers.
- Non-applicable scopes skip expensive jobs instead of manufacturing green runs.
- `merge-gate` aggregates the deterministic jobs required for the detected scope. It is a workflow contract, not a pytest marker.

`.github/workflows/nightly-health.yml` is later-stage evidence. Its suite-profile job reruns the same default Python selection with the 73% coverage floor and `--durations=50`; separate jobs perform repository hygiene and delivery-metric analysis. Nightly does not authorize controlled-live provider calls.

## Tier rules

Keep normal local and PR tests hermetic. Local loopback services, temporary databases, `tmp_path`, mocked transports, and real in-process application components do not by themselves justify a separate integration tier.

Create or reintroduce a marker only when there is a durable execution boundary with a distinct cost, dependency, or safety contract. Update this file, the runner configuration, and CI together so every documented command remains executable on the same commit.
