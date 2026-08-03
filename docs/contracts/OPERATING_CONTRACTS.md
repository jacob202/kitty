# Kitty operating contracts: models, agents, characters, and Builder

**Status:** executable policy plus bounded runtime integration. A label, stored
record, settings screen, or green unit test is not a completed feature.

Machine-readable authorities:

- `config/model_roles.json`
- `config/builder_effectiveness.json`
- `config/image_character_contract.schema.json`
- `gateway/operating_policy.py`

## Vocabulary

| Concept | Meaning | Example |
| --- | --- | --- |
| Underlying model | The actual provider model that runs and is billed. | `deepseek/deepseek-v4-flash` |
| Model role | A stable Kitty route with a workload and evaluation contract. | Fast, Think, Code, Vision |
| Router | Selects a role from the turn, risk, and evidence. It is not another model. | Auto |
| Agent / harness | A role plus system policy, tools, skills, files, memory scope, permissions, limits, and stopping rules. | Daily Kitty, Tutor |
| Skill | A reusable procedure an agent may invoke. It is not a permission or executable capability. | `session-end` |
| Tool | An executable capability with an input/output contract. | `search_memory` |
| Knowledge/files | Material supplied for a task or scope. | project brief, ingested docs |
| Permission | Enforcement outside the prompt. | Builder read-only from chat |

A normal product surface should show the useful decision and expose the provider
model only as provenance:

```text
Agent: Daily Kitty
Mode: Auto
Using: DeepSeek V4 Pro via OpenRouter
```

`kitty-default`, `kitty-small`, and similar strings are internal routes, not
user-facing explanations.

## Agents are more than system prompts

A complete harness may define:

```yaml
id: research
model_role: think
system_policy:
  - evidence and citation rules
skills:
  - deep-research
  - aim42-software-improvement
tools:
  - web-search
  - search-notes
  - search-memory
files:
  - current project brief
memory:
  read: project-scoped
  write: findings-only
permissions:
  builder: read-only
limits:
  max_cost_usd: 1.00
  max_runtime_minutes: 45
stop_conditions:
  - source quality is inadequate
  - the requested action needs approval
```

System prompts help with role, priorities, workflow, format, uncertainty,
tool-selection policy, and stopping behavior. They cannot make a missing tool
exist, enforce permission, supply current documentation, guarantee recall, or
make an unsuitable model reliable.

```text
Prompt      = behavioural policy
Skill       = reusable procedure
Tool        = executable capability
Files       = scoped evidence/context
Permission  = hard enforcement
Telemetry   = proof
```

## Model roles and lifecycle

Authority: `config/model_roles.json`.

### Current roles

| Role | Public meaning | Current incumbent |
| --- | --- | --- |
| Auto | Daily Kitty selects the cheapest reliable role | router; no incumbent |
| Fast | routine bounded work | DeepSeek V4 Flash via OpenRouter |
| Think | ambiguity, architecture, synthesis | Qwen3 235B Thinking via OpenRouter |
| Code | implementation and debugging | Qwen3 Coder via OpenRouter |
| Vision | screenshots, documents, photographs | Mistral Small 3.2 via OpenRouter |

The incumbents describe current configuration, not permanent brand promises.
Kitty roles should outlive provider model names.

`gateway/model_policy_alignment.py` compares this policy with the actual LiteLLM
routes. CI fails if someone silently repoints a branded role without updating
its incumbent record and evaluation evidence.

### Discovery: noticing new models

`gateway/model_discovery.py` and `scripts/model_discovery.py` inspect OpenRouter's
catalogue, diff it against a local owner-readable snapshot, and record:

- newly listed and removed model IDs;
- context length and modalities;
- supported parameters;
- provider pricing metadata;
- likely Fast, Think, Code, or Vision candidacy;
- `evaluation_status: not_evaluated`.

Discovery never edits `config/model_roles.json`, LiteLLM, or a running route. The
snapshot explicitly records `promotion_performed: false`, and the loader rejects
a discovery file that claims otherwise.

Manual commands:

```bash
python3 scripts/model_discovery.py check --force
python3 scripts/model_discovery.py show
python3 scripts/model_discovery.py due
```

Weekly local checks can be installed with:

```bash
python3 scripts/model_discovery.py install-autostart
```

The LaunchAgent contains no provider, GitHub, or OpenAI credentials. It records
catalogue candidates only. **The service exists in this branch but is not proven
installed on Jacob's Mac until that command is run and `launchctl` is inspected.**

### Evaluation and promotion

Evaluate a candidate against the incumbent on representative historical tasks.
The unit is an accepted outcome, not a token.

Required measurements include:

- accepted-outcome rate;
- cost per accepted outcome, including retries and supervision;
- median time to accepted outcome;
- malformed or incomplete output rate;
- tool-call success;
- critical regressions;
- representative sample size and repeated evaluation windows.

A candidate may be promoted only when all evidence/safety gates pass and at
least one condition is met:

1. accepted-outcome rate improves by at least five percentage points;
2. accepted-outcome rate stays within two points while successful-outcome cost
   falls by at least 25%;
3. accepted-outcome rate stays within two points while median time-to-success
   falls by at least 30%.

Any critical regression, malformed rate above 2%, insufficient task count,
insufficient repeat windows, or material tool-use regression rejects promotion.

```bash
python3 scripts/operating_policy.py model-evaluate \
  --role code \
  --incumbent metrics/incumbent.json \
  --candidate metrics/candidate.json
```

Exit `0` means promote. Exit `2` means reject or insufficient evidence.
Promotion remains an explicit reviewed change.

## Image character contract

Authorities:

- `config/image_character_contract.schema.json`
- `gateway/operating_policy.py`
- `gateway/image_character_contracts.py`

A character is not a name plus a photo folder. It is an executable identity
recipe containing:

- a written appearance description;
- features to preserve;
- exclusions such as beautification, rejuvenation, or plastic skin;
- base model family;
- identity method, adapter model, and strength;
- fusion method;
- explicit positive and negative prompt fragments;
- engine recipe and compatibility limits;
- references with purpose, provenance, enabled state, quality score, and global,
  face, and body weights.

### References and weighting

The contract supports at most 12 references. Each reference declares:

- purpose: primary face, secondary face, profile, body/build, hair, expression,
  or style-only;
- provenance: real photograph or generated derivative;
- global, face, and body weights;
- quality score and notes;
- enabled/disabled state.

Exactly one enabled primary-face reference is required when identity conditioning
is used. Generated derivatives are rejected unless explicitly allowed. Weighted
fusion must add to 100%; equal fusion must actually use equal weights. Disabled
references are validated too, so an invalid hidden row cannot become active
later and bypass the contract.

### Persistence and API

Each character contract is stored atomically beside the character at:

```text
data/image-studio/characters/<character-id>/character-contract-v1.json
```

The file is owner-readable JSON with mode `0600`. Current routes are:

```text
GET    /image/characters/{id}/contract
PUT    /image/characters/{id}/contract
DELETE /image/characters/{id}/contract
GET    /image/characters/{id}/resolved
POST   /image/characters/{id}/generate
```

A legacy character with only metadata/photos returns a conflict explaining that
it is not generation-ready. Generation resolves the contract before creating an
image job, so unsupported controls fail before spending or leaving a fake failed
job.

### Current engine truth

The existing Kitty ComfyUI character workflow can honestly support only:

- SDXL;
- one enabled reference;
- `single` fusion;
- IP-Adapter identity conditioning;
- exact strengths `0.5`, `0.7`, or `0.85`;
- the workflow's fixed checkpoint, sampler, and scheduler;
- no character LoRA stack;
- no per-reference or per-region weighting.

The contract supports richer future engines, but this engine refuses those
settings instead of pretending the controls work.

Runtime readiness now requires the matching SDXL adapter:

```text
ip-adapter-plus_sdxl_vit-h.safetensors
```

The older code paired an SDXL checkpoint with an SD1.5 FaceID adapter filename
and considered identity ready when *any* adapter file existed. The new runtime
probe checks the exact file through ComfyUI `/object_info` and refuses otherwise.

**Repository tests prove the refusal and argument wiring. They do not prove that
the exact SDXL adapter is currently installed on Jacob's live ComfyUI worker or
that a real generated image has acceptable likeness.**

The current frontend also does not yet provide a polished contract editor. The
API is functional; a user-friendly Image Studio surface remains required before
calling character setup complete.

## Builder effectiveness contract

Authority: `config/builder_effectiveness.json`.

Builder integrity gates answer whether state is durable, recoverable, reviewed,
and publishable. They do not answer whether a campaign is a sensible use of
models, tokens, or time.

Default tripwires pause when:

- a campaign exceeds four hours;
- a small packet exceeds 45 minutes;
- accepted throughput falls below one packet per hour after the observation
  window;
- two consecutive attempts produce no substantive diff;
- setup/metadata exceeds 25% of elapsed time;
- supervisor tokens exceed worker tokens;
- reset/recovery churn reaches three events;
- the same systemic blocker recurs twice;
- projected completion exceeds a simple baseline by more than 2x.

`gateway/builder_run.py` now invokes this policy by default after each durable
packet result. It records the metrics and decision as an `initiative_decision`
event and pauses the initiative rather than merely printing a warning.

The canonical loop currently owns these measurements directly:

- campaign elapsed time;
- processed and accepted packet counts;
- current packet duration.

It does not yet own trustworthy cumulative token splits, metadata time, reset
counts, repeated blocker count, projection, or simple baseline. Those remain
`null`. After the observation window, missing required telemetry itself pauses
the campaign instead of allowing Builder to run blind indefinitely.

An operator may disable the guard only through the explicit
`effectiveness_guard=False` API parameter for bounded diagnostics. Normal
`initiative run` behavior is guarded.

Standalone evaluation remains available:

```bash
python3 scripts/operating_policy.py builder-check --metrics campaign.json
```

The reported seven packets in roughly 24 hours is an automatic pause under
multiple independent tripwires.

## Session-end / OpenCode verification

`gateway/session_end_audit.py` and `scripts/audit_session_end.py` distinguish a
skill file from execution proof.

The audit requires:

- the canonical repository `session-end` skill;
- a hash-chain-validated effectiveness receipt;
- `tool=opencode` and `execution_owner=builder`;
- elapsed time, attempts, repair commits, regressions, tokens, and cost;
- initiative, packet, and result identity;
- explicit model and provider evidence;
- a validated workflow signal linked to the exact same session.

OpenCode log evidence is supplemental. A duplicate-skill warning does not count
as successful loading or invocation.

```bash
python3 scripts/audit_session_end.py
```

Exit `0` means verified. Exit `2` means the expected outputs are absent or
incomplete. **This audit has not yet been run against Jacob's local OpenCode logs
and KB stores in this branch, so the 24-hour session-end behavior remains
unverified rather than presumed broken or working.**

## Feature completion rule

A feature exists only when a user can:

1. understand what it does;
2. configure it safely—or avoid configuration because Kitty owns the choice;
3. use it end to end;
4. inspect what actually happened;
5. recover from failure;
6. see evidence that the advertised behavior occurred.

Schemas, routes, settings screens, green unit tests, and plans are necessary
parts. None of them alone is completion.
