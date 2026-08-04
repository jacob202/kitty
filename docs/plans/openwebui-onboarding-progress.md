# Open WebUI daily driver — onboarding progress

Branch: `feat/openwebui-tomorrow-ready` · PR: #384

Machine-readable acceptance state: `docs/plans/openwebui-onboarding-checklist.json`
Operator runbook: `docs/runbooks/OPENWEBUI_TOMORROW.md`

## Current objective

Finish and prove the Open WebUI daily-driver baseline. Do not add Image Studio or another feature to this branch before the existing settings, agents, model routes, Kitty tools, lifecycle, persistence, and recovery paths pass final acceptance.

The repository implementation is substantially complete. The remaining release gates are:

1. final-head CI is green;
2. `bootstrap --accept-charges` passes on Jacob's Mac;
3. `verify --accept-charges` passes after restart on Jacob's Mac;
4. a final independent review is recorded and every actionable finding is resolved.

Image Studio and James work are out of scope for PR #384 and remain on `feat/image-studio-next-four`.

## Product boundary

Open WebUI is a pinned, replaceable local shell. It does not own Kitty's routing, provider policy, memory, projects, Tutor, tools, or Builder state. Those remain Gateway responsibilities.

The shell is intentionally:

- pinned to Open WebUI `0.10.2`;
- isolated under `~/kitty-services/openwebui`;
- unauthenticated only on `127.0.0.1`;
- launched with an owner-only umask and a minimal allowlisted environment;
- connected only to Kitty Gateway as its OpenAI-compatible backend;
- prevented from persisting database overrides of the checked-in runtime settings.

## Configured daily-driver surface

### Models

| Menu | Kitty route | Intended upstream in OpenRouter/auto mode |
|---|---|---|
| Kitty Auto | classifier-selected | complexity, domain, and modality routing |
| Kitty Fast | `kitty-small` | `deepseek/deepseek-v4-flash` |
| Kitty Think | `kitty-think` | `qwen/qwen3-235b-a22b-thinking-2507` |
| Kitty Code | `kitty-code` | `qwen/qwen3-coder` |
| Kitty Vision | `kitty-vision` | `mistralai/mistral-small-3.2-24b-instruct` |

Only Auto may reclassify a turn. Explicit menu choices stay pinned. Auto preserves domain-deep signals and routes image content to Vision before the text-only endpoint loses modality information.

When an exact provider cannot honor all advertised aliases, model discovery collapses to one provider-labelled row rather than presenting choices that do not change execution.

### Agents

| Agent | Base | Kitty tools | Vision |
|---|---|---:|---:|
| Daily Kitty | Auto | yes | yes |
| Research | Think | yes | no |
| Coding | Code | no | no |
| Tutor | Auto | yes | no |
| Builder Operator | Auto | yes | no |

Agents are created or repaired idempotently on start. Daily Kitty is the default and the five purposeful agents are pinned.

### Bounded Kitty tools

The shell receives a small authenticated OpenAPI surface rather than the full Gateway schema:

- unified memory search and explicit remember;
- notes and ingested-document search;
- life-first projects and one next step;
- today's calendar state;
- grounded Tutor answers;
- read-only bounded Builder status.

Builder reads do not initialize or migrate the control-plane database. Result counts are bounded so a model cannot place the user's entire memory, document corpus, or initiative corpus into a paid prompt.

## Settings applied

The checked-in runtime configuration disables or constrains features that would make the shell unpredictable:

- `WEBUI_AUTH=False` only with loopback binding;
- `ENABLE_OPENAI_API=True` and `ENABLE_OLLAMA_API=False`;
- `ENABLE_PERSISTENT_CONFIG=False`;
- Daily Kitty as the default model and all five agents pinned;
- telemetry, community sharing, update checks, arena models, and unrelated discovery disabled;
- Gateway base URL and secret derived with the same repository `.env` precedence as the canonical Kitty launcher;
- ambient provider, GitHub, Python-path, and unrelated credentials excluded from the Open WebUI process.

## Lifecycle and recovery implementation

The operator layer checks rather than assumes:

- installed version and venv health;
- service PID ownership and listening-port identity;
- concurrent starts and unhealthy tracked processes;
- launchd enablement and loaded state;
- usable single-admin database state;
- bounded provider streaming with actionable failures;
- verified SQLite backup publication;
- restore refusal while running, pre-restore backup, source validation, and atomic replacement;
- rollback to a Kitty-specific Next.js identity without unloading Gateway or LiteLLM.

## Feature acceptance commands

Read-only configuration and projection checks:

```bash
python3 scripts/openwebui_local.py verify
```

Bounded live provider and Daily Kitty checks:

```bash
python3 scripts/openwebui_local.py verify --accept-charges
```

Full fresh-machine path:

```bash
python3 scripts/openwebui_local.py bootstrap --accept-charges
```

The verifier checks hardened settings, Gateway model discovery, all five live agent records, tool registration, memory, notes, projects, calendar, Tutor contract, and Builder projection. With charge authorization it also sends one small turn through every advertised model route and one end-to-end Daily Kitty turn through Open WebUI.

## Repository evidence

The branch includes focused tests for:

- Open WebUI install, environment, process, launchd, admin repair, backup, restore, rollback, and smoke behavior;
- model discovery, explicit pins, exact-provider menu truthfulness, domain-aware Auto, image Auto routing, and direct OpenRouter normalization;
- streaming failure schema and actionable user copy;
- provider-policy-safe memory extraction;
- bounded authenticated tool projections;
- feature-level acceptance behavior and charge gating.

CI is the authority for the final test result. Earlier Mac observations in prior versions of this document are useful debugging history, but they are not accepted as proof for the rebuilt final PR head.

## Historical defects that shaped the current implementation

Earlier host work exposed several real failure classes that now have explicit code or acceptance coverage:

- AgentRouter was explicitly selected with a revoked token, preventing fallback;
- Open WebUI inherited Kitty's `PYTHONPATH`, shadowing its installed MCP SDK;
- concurrent first sign-ins created duplicate pending admin rows;
- failure streams produced blank assistant messages;
- stale or duplicate Gateway secrets caused local 401 responses;
- Auto did not preserve domain or image signals;
- model menu rows could be placebo choices under exact-provider routing;
- read-only Builder access could mutate absent state;
- backups and restores could publish or install partial databases;
- lifecycle commands could race launchd or signal unrelated processes;
- continuity files described unrelated work and invalid SHAs;
- onboarding documents incorrectly treated Image Studio as the active slice.

Those observations explain the safeguards. They do not waive the final Mac acceptance.

## Current blockers

- Live installed state, launchd, credentials, provider balances, real responses, and persisted chats cannot be proven from repository CI.
- PR Agent Review is currently skipped, so an independent final review still needs to be obtained or explicitly recorded.

## Next action

On Jacob's Mac, from the branch checkout:

```bash
python3 scripts/openwebui_local.py bootstrap --accept-charges
python3 scripts/openwebui_local.py verify --accept-charges
```

Fix every reported failure and rerun until clean. Keep PR #384 in draft until that evidence and the independent final review are recorded.