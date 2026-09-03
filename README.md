# Kitty

Kitty is Jacob's local-first personal AI system. It owns conversation behavior, context, memory, projects, tools, Tutor, model policy, and user-facing workflows while keeping models and clients replaceable.

KittyBuilder is the separate engineering control plane. It owns accepted Missions, queues, workers, attempts, leases, retries, validation, reviews, budgets, evidence, and governed publication.

## Current operating model

| Surface | Role | Default |
|---|---|---|
| Native Kitty (`gateway/kitty-chat`) | Canonical user-facing product surface (ADR 0039) | local port `4000` |
| Gateway | Product authority and API | `127.0.0.1:8000` |
| LiteLLM | Model routing and fallback | `127.0.0.1:8001` |
| KittyBuilder | Durable engineering execution control plane | supported DB/API/CLI |
| Open WebUI | Optional compatibility/reference client | local-only compatibility path |

The Gateway owns product truth. Native Kitty is the canonical frontend; Open WebUI and other clients are replaceable views. Builder execution truth comes from Builder's supported projections, not GitHub comments or handoff prose.

## Install and run

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt

cd gateway/kitty-chat && npm ci && cd ../..
python3.12 -m venv ~/kitty-services/venv-litellm
~/kitty-services/venv-litellm/bin/pip install -r gateway/requirements.litellm.txt

cp .env.example .env
# Add at least one configured model-provider credential to .env.

make hooks             # one-time per clone
./kitty doctor --json  # fail-loud preflight
./kitty                # Gateway + LiteLLM + native UI; opens the browser
./kitty status
./kitty down            # stop Kitty-owned services
```

`./kitty up` starts Gateway + LiteLLM only. `./kitty ui` starts the native UI only. Product runtime and remote-access boundaries are owned by [`docs/reference/LAUNCHER_CONTRACT.md`](docs/reference/LAUNCHER_CONTRACT.md); authenticated phone/Tailnet access remains tracked by [`KH-REMOTE-01`](docs/packets/KH-REMOTE-01.md) and must not be approximated by exposing the Gateway directly.

## Verify a change

Use the repository targets rather than hand-written equivalents so local verification matches CI and runtime provenance rules:

```bash
make test
make ui-test && make ui-build     # when frontend code changed
make smoke-test-hermetic          # when a user-visible frontend workflow changed
./kitty doctor --json             # when runtime/setup behavior changed
```

Run the narrowest relevant checks for focused work; see [`TESTING.md`](TESTING.md) for the full test tiers. Repository CI does not prove local credentials, provider balances, launchd state, or paid-provider availability.

## Documentation

Do not infer authority from a filename, detail level, or date.

- [`START_HERE.md`](START_HERE.md) owns the canonical cold-start procedure and reading order.
- [`docs/README.md`](docs/README.md) is the human map of current authorities, supporting references, execution inputs, dated evidence, and history.
- [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md) routes each kind of project truth to its owner.
- [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) is the highest design authority.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) is the only active delivery sequence.
- [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) owns the approved Mission and acceptance contract.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) is dated shipped/limitation evidence, not a live dashboard.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) and [`docs/adr/`](docs/adr/) preserve durable decisions and supersession.

## Repository navigation

| Need | Location |
|---|---|
| Code/data-flow map | [`docs/reference/CODEBASE_MAP.md`](docs/reference/CODEBASE_MAP.md) |
| Product purpose | [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) |
| Builder operation | [`docs/KITTYBUILDER_QUICKSTART.md`](docs/KITTYBUILDER_QUICKSTART.md) |
| PR/review workflow | [`docs/WORKFLOW.md`](docs/WORKFLOW.md) |
| Test tiers | [`TESTING.md`](TESTING.md) |
| Candidate plans | [`docs/plans/README.md`](docs/plans/README.md) |
| Builder plan/spec output convention | [`docs/superpowers/README.md`](docs/superpowers/README.md) |
| Historical material | [`docs/archive/`](docs/archive/) |

Runtime data under `data/`, logs under `logs/`, and generated frontend output under `.next/` are not source documentation. Never commit secrets.
