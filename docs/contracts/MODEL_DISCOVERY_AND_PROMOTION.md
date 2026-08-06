# Kitty model discovery and promotion

Kitty-branded model roles are stable product contracts. Provider model IDs are
replaceable incumbents underneath them.

```text
Daily Kitty / Auto
  -> Fast | Think | Code | Vision
  -> current provider model
```

A provider announcing a model does not make it a Kitty model. The lifecycle is:

```text
discover -> review queue -> evaluate -> eligible -> reviewed route change
```

Discovery and promotion are deliberately separate.

## Weekly discovery

`gateway/model_discovery.py` reads OpenRouter's public model catalogue and stores
an owner-readable snapshot at:

```text
data/model-discovery/openrouter.json
```

The snapshot contains:

- model ID and public name;
- creation time and context length;
- input/output modalities;
- supported parameters;
- provider pricing metadata;
- suggested Kitty roles;
- evaluation status, role, notes, and last evaluation time;
- newly listed and removed model IDs;
- configured roles whose incumbent is absent from the current catalogue;
- `promotion_performed: false`.

The first normal run establishes a quiet baseline. It does not flood the review
queue with every model OpenRouter already carries. To queue the current catalogue
explicitly, use `--include-existing`.

```bash
python3 scripts/model_discovery.py check --force
python3 scripts/model_discovery.py check --force --include-existing
python3 scripts/model_discovery.py show
```

Later checks preserve prior dispositions and report only real catalogue changes.
A missing configured incumbent triggers a local macOS notification. New models
trigger a smaller candidate notification.

## Weekly local service

```bash
python3 scripts/model_discovery.py install-autostart
```

This installs `com.kitty.model-discovery`, which checks at login and every seven
days. The process receives no OpenRouter, OpenAI, GitHub, or other provider
credentials. Catalogue discovery does not require a paid request and cannot edit
LiteLLM or `config/model_roles.json`.

Remove it without deleting the candidate history:

```bash
python3 scripts/model_discovery.py uninstall-autostart
```

## Candidate review states

Allowed states are:

- `not_evaluated`
- `queued`
- `evaluating`
- `eligible`
- `deferred`
- `rejected`

`queued`, `evaluating`, and `eligible` require a target role. `eligible` means the
candidate has satisfied the evaluation policy; it does **not** mean Kitty changed
a production route.

Examples:

```bash
python3 scripts/model_discovery.py disposition \
  vendor/model-id \
  --status queued \
  --role code \
  --notes "Evaluate against the current Code incumbent"

python3 scripts/model_discovery.py disposition \
  vendor/model-id \
  --status rejected \
  --role code \
  --notes "Higher malformed tool-call rate"
```

Dispositions are preserved when the provider catalogue is refreshed.

## Evaluation

The unit is an accepted outcome, not a token. Candidate and incumbent metrics
must include:

- representative sample size;
- repeated evaluation windows;
- accepted-outcome rate;
- cost per accepted outcome, including retries and supervision;
- median time to accepted outcome;
- malformed/incomplete response rate;
- tool-call success rate;
- critical regressions.

Run:

```bash
python3 scripts/operating_policy.py model-evaluate \
  --role code \
  --incumbent incumbent-metrics.json \
  --candidate candidate-metrics.json
```

A candidate is eligible only when all evidence and safety gates pass and it wins
through quality, successful-outcome cost, or time-to-success according to
`config/model_roles.json`.

## Promotion

Promotion is an explicit reviewed change:

1. mark the candidate `eligible` with the evaluation evidence location;
2. update the role incumbent in `config/model_roles.json`;
3. update the matching LiteLLM route;
4. run `python3 scripts/operating_policy.py validate`;
5. run focused role tests and the full trust/CI suites;
6. merge only when the role policy and actual upstream align.

`gateway/model_policy_alignment.py` fails CI when a role and its live LiteLLM
upstream diverge. Discovery snapshots that claim `promotion_performed: true` are
rejected as corrupt.

## Current proof boundary

Repository tests prove catalogue diffing, quiet baselines, candidate review-state
persistence, incumbent absence detection, notifications, credential-free launchd
configuration, policy evaluation, and non-promotion invariants.

They do not prove that the LaunchAgent is installed on Jacob's Mac or that the
live OpenRouter catalogue currently contains every configured incumbent. Those
are host/runtime checks.
