# Testing Kitty

This file documents the test tiers that actually exist on `main`. Keep it aligned with `pytest.ini`, `Makefile`, `gateway/kitty-chat/package.json`, and `.github/workflows/tests.yml`.

## Current taxonomy

| Tier | Runner | Normal PR requirement? | External network / paid providers? |
| --- | --- | --- | --- |
| Python fast required | pytest | Yes for code scope | No |
| Python process integration | pytest `integration` | Yes for code scope, parallel job | No |
| Frontend unit/component | Vitest | Yes for frontend scope | No |
| Browser smoke | Playwright | Yes for frontend scope | No |
| Controlled-live provider probes | pytest `controlled_live` | Never | Explicit opt-in only; currently empty |

The Python suite has a deliberate latency split. Cheap hermetic behavior, API, persistence, and policy tests stay in the fast tier. Tests whose contract fundamentally requires real subprocess lifecycle, real throwaway git/worktree behavior, or multi-step process orchestration are marked `integration`. Both tiers are required for code changes; CI runs them independently so the developer loop does not pay process-boundary latency on every edit.

`browser` and `merge_gate` are not pytest tiers. Browser tests live under `gateway/kitty-chat/tests/smoke/` and use Playwright. `merge-gate` is the GitHub Actions aggregation job for required deterministic evidence.

Python commands assume the repository's Python 3.12 environment has `requirements.txt`, pytest, pytest-asyncio, and pytest-cov installed. Frontend commands assume `npm ci` has been run and Playwright Chromium is installed.

## Python: fast required suite

From the repository root:

```bash
make test
```

The measured pre-split Python baseline median was 204.94s. Final five-run verification of the reconciled fast tier produced a 108.80s median while retaining 4,714 passing tests, 1 skip, and 29 passing subtests; 312 process-integration tests remain separately required. The timing is evidence, not a permanent threshold.

For local parity with the fast Python PR coverage gate:

```bash
make test-ci
```

`pytest.ini` excludes `integration` and `controlled_live` from the default selection. Normal tests run with Kitty's test harness, which forces test mode, uses a temporary runtime data root, removes paid-provider credentials, disables paid image generation, blocks canonical runtime mutation, and blocks non-loopback network access.

Run the required process/git integration tier explicitly:

```bash
make test-integration
```

Run both required Python tiers sequentially when you want one local full-suite command:

```bash
make test-all
```

Integration is not optional coverage: it is separated for feedback latency and CI parallelism. Tests moved there must name a real boundary that cannot be tested honestly as a cheap unit/behavior test.

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

- `code=true`: `pytest` runs the fast hermetic suite with `gateway` coverage required at 73%, while `pytest-integration` runs the required real-process/git lifecycle tier in parallel; Ruff and mypy are also required.
- `frontend=true`: the `kitty-chat` job runs Vitest and a production build; `browser-smoke` then runs both Playwright browser tiers.
- Non-applicable scopes skip expensive jobs instead of manufacturing green runs.
- `merge-gate` requires both Python jobs for code scope, so the speed split cannot silently reduce required coverage. It is a workflow contract, not a pytest marker.

`.github/workflows/nightly-health.yml` is later-stage evidence. Its suite-profile job recombines FAST + INTEGRATION and profiles the complete required Python suite with the 73% coverage floor. PR CI keeps the tiers separate for latency. Nightly does not authorize controlled-live provider calls.

## Tier rules

Keep all normal PR tests hermetic. Local loopback services, temporary databases, `tmp_path`, mocked transports, and real in-process application components do not by themselves justify integration.

Use `integration` only when the behavior being protected fundamentally depends on real subprocess lifecycle, git/worktree semantics, process-group termination, or similarly expensive orchestration. Do not move a slow test merely because it is slow; first ask whether the same product contract can be covered more cheaply.

Critical product journeys are a separate question from Python tiering. Chat, Image Lab, Builder/Work and other user-visible flows need browser or live acceptance evidence where lower-level tests cannot prove the outcome. Never describe a lower-level mock test as closing a live acceptance gap.
