# Kitty

Kitty is Jacob's local-first personal AI system. It owns conversation behavior, context, memory, projects, tools, Tutor, model policy, and user-facing workflows while keeping models and clients replaceable.

KittyBuilder is the separate engineering control plane. It owns accepted Missions, queues, workers, attempts, leases, retries, validation, reviews, budgets, evidence, and PR publication.

## Current operating model

| Surface | Role | Default |
|---|---|---|
| Native Kitty (`kitty-chat`) | Canonical user-facing product surface (ADR 0039) | local port `4000`; intended loopback security boundary |
| Gateway | Product authority and API | `127.0.0.1:8000` |
| LiteLLM | Model routing and fallback | `127.0.0.1:8001` |
| KittyBuilder | Durable engineering execution control plane | supported DB/API/CLI |
| Open WebUI | Optional compatibility/reference client | `127.0.0.1:3000` |

The Gateway owns product truth and the native Kitty frontend is its canonical user-facing surface. Open WebUI and other clients are optional, replaceable views. Kitty must remain useful when KittyBuilder is unavailable, and Builder execution truth must never be inferred from GitHub comments or handoff prose.

```text
Native Kitty frontend
  → Kitty Gateway
    → context + memory + tools + projects + Tutor
    → LiteLLM / provider chain
    → approved Mission → KittyBuilder → Result/Evidence
```

## Start here

For repository work, begin with [`START_HERE.md`](START_HERE.md). It owns the
cold-start receipt and canonical reading order. [`docs/README.md`](docs/README.md)
is the documentation directory map; [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md)
routes each kind of truth to its owner.

## Quick start

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt

cd gateway/kitty-chat && npm ci && cd ../..
python3.12 -m venv ~/kitty-services/venv-litellm
~/kitty-services/venv-litellm/bin/pip install -r gateway/requirements.litellm.txt

cp .env.example .env
# Add at least one configured model-provider credential to .env (OpenRouter is the current default).

./kitty doctor --json  # fail-loud preflight before first launch
./kitty            # Gateway + LiteLLM + native UI, then open the browser
./kitty status
./kitty doctor --json
```

Native Kitty is the canonical product at `http://127.0.0.1:4000` for local use. `./kitty up` starts only Gateway + LiteLLM; `./kitty ui` starts only the native UI. Open WebUI remains available only as an optional compatibility/reference client through `scripts/openwebui_local.py`; it is not required for the normal Kitty product path.

**Remote-access caveat:** `kitty health` can report the UI socket reachable on the Tailscale IP, but that is not proof that normal `/proxy`-backed product workflows are authorized remotely. `./kitty ui` still binds broadly while the server-side proxy rejects non-loopback Hosts. Keep Gateway/LiteLLM and the proxy secret boundary closed; [`KH-REMOTE-01`](docs/packets/KH-REMOTE-01.md) owns authenticated phone/Tailnet access.

## Verification

```bash
git status --short --branch
./kitty context --agent
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
```

Repository CI does not prove local credentials, provider balances, launchd state, real paid routes, or Jacob's installed Open WebUI database. Runtime claims require supported local verification and explicit charge authorization where applicable.

## Manage the local stack

```bash
./kitty status        # supported service summary
./kitty doctor --json # environment/runtime diagnostics
./kitty down          # stop Kitty-managed services
./kitty               # start the normal local product path again
```

Architecture, roadmap, mission, engineering, and execution rules live in their
canonical owners linked from `START_HERE.md`; this README intentionally does not
duplicate them.

## Repository navigation

| Need | Location |
|---|---|
| Code and data-flow map | [`docs/reference/CODEBASE_MAP.md`](docs/reference/CODEBASE_MAP.md) |
| Product purpose | [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) |
| Architecture decisions | [`docs/DECISIONS.md`](docs/DECISIONS.md) and [`docs/adr/`](docs/adr/) |
| Builder operation | [`docs/KITTYBUILDER_QUICKSTART.md`](docs/KITTYBUILDER_QUICKSTART.md) |
| Documentation index | [`docs/README.md`](docs/README.md) |
| Historical material | [`docs/archive/`](docs/archive/) |

## Image-history decision

Previously removed personal images remain in Git history by explicit owner decision. This maintenance work does not rewrite, purge, enumerate, or otherwise alter that history.
