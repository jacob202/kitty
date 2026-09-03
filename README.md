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

1. [`START_HERE.md`](START_HERE.md) — cold-start reading order.
2. [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md) — where each kind of truth lives.
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current boundaries and state ownership.
4. [`docs/ROADMAP.md`](docs/ROADMAP.md) — the short active delivery sequence.
5. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — verified repository state and explicit unknowns.
6. [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) — the one approved current mission.
7. [`docs/audit/GITHUB_OPERATING_PICTURE_2026-08-04.md`](docs/audit/GITHUB_OPERATING_PICTURE_2026-08-04.md) — dated evidence from the GitHub truth pass.

## Quick start

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env

./kitty            # Gateway + LiteLLM + native UI, then open the browser
./kitty status
./kitty doctor --json
```

Native Kitty is the canonical product at `http://127.0.0.1:4000` for local use. `./kitty up` starts only Gateway + LiteLLM; `./kitty ui` starts only the native UI. Open WebUI remains available only as an optional compatibility/reference client through `scripts/openwebui_local.py`; it is not required for the normal Kitty product path.

**Current remote-access caveat:** `./kitty ui` presently forces an all-interface UI bind while the server-side `/proxy` still rejects non-loopback Hosts. That mismatch is a known defect, not supported Tailnet access. Keep Gateway/LiteLLM and the proxy secret boundary closed; [`KH-REMOTE-01`](docs/packets/KH-REMOTE-01.md) owns the authenticated phone/Tailnet repair.

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

## Durable rules

- Accepted ADRs define architecture and supersession.
- `docs/ROADMAP.md` is the only active delivery order.
- `docs/PROJECT_STATUS.md` is a dated evidence summary, not a live dashboard.
- `docs/ACTIVE_MISSION.md` is the only approved current mission.
- Plans, packets, issue comments, and archived documents are inputs or history unless promoted explicitly.
- Builder execution truth lives in its supported database/API/CLI.
- New context reads go through `memory_graph`; app-state writes use established storage boundaries.
- Never commit secrets or treat generated files under `data/`, `logs/`, or `.next/` as documentation.
- Open WebUI remains loopback-only while its auth-disabled compatibility path is in use. Native Kitty remote access also requires a separately reviewed authenticated boundary; the current bind-all/proxy mismatch is not an exception.

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
