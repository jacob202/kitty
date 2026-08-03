# Kitty operating contracts: models, agents, characters, and Builder

**Status:** executable policy baseline. A label or stored record is not a completed
feature. The checked-in JSON policies and `gateway/operating_policy.py` are the
machine-readable authority for this document.

## The vocabulary

| Concept | Meaning | Example |
| --- | --- | --- |
| Underlying model | The actual provider model that runs and is billed. | `deepseek/deepseek-v4-flash` |
| Model role | A stable Kitty route with a workload and evaluation contract. | `fast`, `think`, `code`, `vision` |
| Router | Selects a role from the turn, risk, and available evidence. It is not another model. | `auto` |
| Agent / harness | A role plus system policy, tools, skills, files, memory scope, permissions, limits, and stopping rules. | Daily Kitty, Tutor |
| Skill | A reusable procedure an agent may invoke. It is not a permission or a tool. | `session-end` |
| Tool | An executable capability with a concrete input/output contract. | `search_memory` |
| Knowledge/files | Material supplied to the agent for the current task or scope. | project brief, ingested docs |
| Permission | Hard enforcement outside the prompt. | Builder read-only from chat |

The UI should ordinarily show the agent and mode, with the underlying model
available as provenance rather than as the main decision:

```text
Agent: Daily Kitty
Mode: Auto
Using: DeepSeek V4 Pro via OpenRouter
```

`kitty-default`, `kitty-small`, and similar strings are internal routes. They are
not user-facing explanations.

## Agents are more than system prompts

A useful agent definition has all of these dimensions:

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

System prompts are useful for role, priorities, workflow, output format,
uncertainty, tool-selection policy, and stopping behavior. They cannot make a
missing tool exist, enforce permission, guarantee recall, supply documentation,
or make an unsuitable model reliable. Prompt, skill, tool, files, memory,
permission, and telemetry remain separate contracts.

## Model roles and lifecycle

Authority: `config/model_roles.json`.

### Current roles

| Role | Public meaning | Current incumbent |
| --- | --- | --- |
| Auto | Daily Kitty chooses the cheapest reliable role | router; no incumbent |
| Fast | routine bounded work | DeepSeek V4 Flash via OpenRouter |
| Think | ambiguity, architecture, synthesis | Qwen3 235B Thinking via OpenRouter |
| Code | implementation and debugging | Qwen3 Coder via OpenRouter |
| Vision | screenshots, documents, photographs | Mistral Small 3.2 via OpenRouter |

The incumbents describe the current configuration, not permanent brand promises.
Kitty roles should outlive provider model names.

### Discovery

Once per week, or when an operator nominates a candidate, inspect configured
provider catalogues and release information. Discovery creates a candidate; it
never changes a live route.

### Evaluation

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

### Promotion

Automatic discovery is allowed. Automatic promotion is not.

A candidate may be promoted only when all safety/evidence gates pass and at
least one of these is true:

1. accepted-outcome rate improves by at least five percentage points;
2. accepted-outcome rate stays within two points while successful-outcome cost
   falls by at least 25%;
3. accepted-outcome rate stays within two points while median time-to-success
   falls by at least 30%.

Any critical regression, malformed rate above 2%, insufficient task count,
insufficient repeat windows, or material tool-use regression rejects promotion.

Run:

```bash
python3 scripts/operating_policy.py model-evaluate \
  --role code \
  --incumbent metrics/incumbent.json \
  --candidate metrics/candidate.json
```

Exit `0` means promote; exit `2` means reject or insufficient evidence.

## Image character contract

Authority: `config/image_character_contract.schema.json` and
`validate_character_contract`.

A character is not a name and a folder of pictures. It is an executable identity
recipe containing:

- a written appearance description;
- features to preserve;
- exclusions such as beautification, rejuvenation, or plastic skin;
- base model family;
- identity method and adapter;
- adapter strength;
- fusion method;
- an explicit prompt and negative prompt;
- an engine recipe;
- references with purpose, provenance, enabled state, quality score, and weights.

### Reference images

The contract supports at most 12 references. Each enabled reference must name:

- purpose: primary face, secondary face, profile, body/build, hair, expression,
  or style-only;
- provenance: real photograph or generated derivative;
- global weight;
- face weight;
- body weight;
- quality score;
- optional notes.

Exactly one enabled primary-face reference is required whenever the identity
method uses references. Generated derivatives are rejected unless the character
explicitly opts in; training or conditioning on generated images can compound
previous model errors.

### Fusion and engine truth

Supported fusion descriptions are `single`, `equal_mean`, `weighted_mean`,
`concat`, and `max`. These are promises the selected engine must actually honor.

`resolve_character_for_engine` refuses when:

- the engine does not support the requested identity method;
- the engine does not support the fusion method;
- too many references are enabled;
- per-image weights are configured but the engine cannot apply them.

The correct behavior is a loud refusal, not a gallery slider that changes
nothing.

Example:

```bash
python3 scripts/operating_policy.py character-validate \
  --character character.json \
  --engine-capabilities engine-capabilities.json
```

The next Image Studio implementation slice must persist this contract, make the
fields understandable in the UI, and pass the resolved recipe into generation.
Until that connection exists, the current character CRUD is storage—not a
working identity feature.

## Builder effectiveness contract

Authority: `config/builder_effectiveness.json`.

Builder integrity gates answer whether state is durable, recoverable, reviewed,
and publishable. They do not answer whether the campaign is a sensible use of
models, tokens, or time.

The effectiveness receipt measures:

- elapsed campaign time;
- processed and accepted packets;
- current packet time;
- consecutive attempts without a substantive diff;
- setup/metadata time;
- supervisor and worker tokens;
- reset/recovery events;
- repeated systemic blockers;
- projected completion time;
- a simple-agent or human baseline.

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
- projected completion exceeds the simple baseline by more than 2x.

These are initial policy values, not universal constants. Change them only with
outcome evidence.

Run:

```bash
python3 scripts/operating_policy.py builder-check --metrics campaign.json
```

Exit `0` means continue. Exit `2` means pause and diagnose. Missing metrics are
reported and never invented.

The reported campaign of seven packets in roughly 24 hours is an automatic pause
under several independent tripwires: campaign wall time, throughput,
setup/metadata fraction, recovery churn, repeated blockers, and comparison with
a simpler execution baseline.

## Session-end requirement

For a Builder-owned session, `session-end` is expected to record elapsed time,
attempts, repair commits, regressions, model/provider evidence, result identity,
and workflow-learning signals. The skill already defines these fields and says
unknown values must remain `null` rather than fabricated.

A missing receipt after the 24-hour campaign can mean:

1. OpenCode did not load the skill;
2. the supervisor did not invoke it;
3. it wrote to an unavailable or wrong location;
4. it recorded generic completion state but missed the economic failure.

The operational test is not “the skill markdown exists.” Run a deliberate
OpenCode session, invoke session-end, and verify all three outputs:

- continuity files validate;
- a KB-effectiveness receipt exists with the right tool and execution owner;
- a workflow signal records the slow, metadata-heavy campaign and its bounded
  prevention rule.

Until that test passes, session-end in OpenCode is **unverified**.

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
