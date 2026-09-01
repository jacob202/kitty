# Builder Model Routing — Free + Paid Value Lanes

KittyBuilder has two explicit execution lanes. `--free` is genuinely zero-cost
and never falls into a paid model. `--paid` is the governed value lane: routine
implementation defaults to DeepSeek V4 Flash and routine review to MiniMax M3,
while frontier spend is an explicit escalation. Both lanes use the same durable Builder attempts, worktrees,
validation, review, evidence, and publication rails.

## Who does what

| Stage | Who | Cost |
| ----- | --- | ---- |
| Author the packet (objective, allowed paths, acceptance, validation) | Claude/Codex | paid, once |
| Implement the packet in an isolated worktree | free ladder or governed paid worker | free or bounded paid |
| Independent review of the attempt | separate read-only reviewer model | same selected lane |
| Deterministic validation (declared test commands) | the runner itself | free |
| Final diff review + merge decision | Jacob (with Claude if needed) | paid, small |

Route choice is explicit and durable. Free exhaustion pauses honestly; it does
not silently spend. Paid execution is selected with `--paid` and is admitted
only after the compute governor authorizes the route and projected cost.

## One-command launch

Both adapters gate on the same zero-cost builder ladder the free train uses
(`opencode/deepseek-v4-flash-free` → `opencode/mimo-v2.5-free` →
`opencode/nemotron-3-ultra-free` → `opencode/north-mini-code-free` →
OpenRouter free fallbacks). The free reviewer defaults to a different free
model and remains read-only. Free endpoints rate-limit and flake; the ladder is
what lets one attempt survive clean provider failures without burning the
attempt budget.

The paid lane is separate: `--paid` selects the configured `cheap` route, and
`--paid --tier frontier` requests the frontier route. The governor may downgrade
frontier to cheap; Builder switches the actual worker and reviewer models before
opening an attempt, so the evidence can never say "cheap" while a frontier model
actually runs. The production cheap pair is DeepSeek V4 Flash for implementation and
MiniMax M3 for independent review, with Qwen 3.7 Plus as the bounded reviewer
fallback. Outside explicit `--free` runs, required review goes directly to the
governed paid reviewer instead of walking the free ladder. Reviewer models force
OpenRouter `provider.sort=price` with provider fallbacks allowed; a clean primary
review failure may hand off once to the configured different-model fallback.
Explicit `--free` remains a real zero-spend contract. OpenRouter is the preferred
reviewer router. AgentRouter is dead and must not be recommended; Freebuff and
9Router are optional only, never dependencies. Keep the bare OpenRouter model
slugs and explicit price sorting rather than relying on `:floor` or the repeatedly
stalling `deepseek-v4-flash-0731` variant.

Hand-off rules (fail-loud, no debris):

- A model may hand off to the next free model **only** when it failed cleanly:
  no result contract written, no change to `HEAD` or the worktree.
- Any partial work stops fallback immediately and fails the attempt with the
  worktree preserved for inspection.
- A written result with a non-zero exit is refused, never trusted.
- The reviewer ladder additionally treats any worktree mutation as fatal —
  review is read-only, verified before and after.

Overrides:

```bash
KITTYBUILDER_MODEL=opencode/mimo-v2.5-free          # force one builder model
KITTYBUILDER_MODELS="modelA modelB"                  # replace the builder ladder
KITTYBUILDER_REVIEW_MODEL=...                        # force one reviewer model (free adapter default stays free)
KITTYBUILDER_REVIEW_MODELS="modelA modelB"           # replace the reviewer model list
KB_MODEL_STARTUP_TIMEOUT_SECONDS=30                  # max silence before worker fallback
KB_REVIEW_MODEL_STARTUP_TIMEOUT_SECONDS=30           # max silence before reviewer fallback
```

`--free --model <id>` accepts only an explicitly free model identifier. Paid
models require `--paid`; inherited model-ladder overrides are cleared when the
free preset is selected. Keep the reviewer disjoint from the builder model —
the review is only worth anything if it is independent.

```bash
./kitty builder initiative run-packet <initiative> <packet> --free
./kitty builder initiative run-packet <initiative> <packet> --paid
./kitty builder initiative run-packet <initiative> <packet> --paid --tier frontier
```

## Safety rails (already enforced, don't re-litigate)

- `opencode.jsonc` denies push, PR create/merge, destructive git, `rm`,
  external directories, and subagent spawning even under `--auto`. Free and
  paid execution use separate `free-*` and `paid-*` agent definitions.
- The adapters verify task/attempt identity and bundle SHA-256 before any
  model runs, stage runner files into the worktree, and only copy validated
  contract JSON back out.
- Publish auto-merges by default (`gate=auto`); pass `--gate manual` to park
  at `awaiting_review` for operator review.
- Free endpoints may log prompts. Public repo code and task instructions
  only — never `.env`, credentials, runtime personal data, or private
  memories.

## Paid value lane

`config/builder_paid_routes.json` is the checked-in allowlist and per-attempt
ceiling. Routine paid implementation uses DeepSeek V4 Flash through OpenRouter; routine paid
review uses MiniMax M3. Frontier execution is a separate explicit tier
and uses the stronger configured worker/reviewer pair. Reviewer independence is
by model family: when the implementation itself is DeepSeek, select a different
configured paid reviewer rather than self-family review.
The compute governor remains the spend authority and receipts are durable.

Routine independent review has a 240-second outer budget. PR review uses at most
two different models with a 90-second timeout per model. The 30-second startup
silence detector remains in force for Builder reviewer adapters.

## Timeouts

The worker timeout (`--timeout`, default 3600s) remains the hard budget for the
whole ladder walk, not a fresh budget for every model. A responsive model gets
the remaining usable budget rather than an artificial `budget / model_count`
slice, so real work is not killed mid-edit.

OpenCode runs in JSON-event mode. A top-level provider `error` event fails that
model immediately. A model that emits only local `step_start` bookkeeping and
then stays silent has 30 seconds by default to produce meaningful model
activity (`text`, `tool_use`, reasoning, or a finished step); otherwise Builder
terminates it cleanly and tries the next model. Once meaningful activity begins,
the startup deadline is disabled and the model keeps the remaining packet
budget. The worker and reviewer startup windows can be tuned independently with
`KB_MODEL_STARTUP_TIMEOUT_SECONDS` and
`KB_REVIEW_MODEL_STARTUP_TIMEOUT_SECONDS`.

A model that times out cleanly (no result contract and no worktree change) may
hand off to the next model. Any partial work still stops fallback immediately.
A valid worker/reviewer contract is itself a completion signal: Builder stops a
model process that lingers after writing the contract, validates the contract,
and continues. The outer Builder timeout remains authoritative.

## Multi-Agent Orchestration via Orca

For workflows that benefit from parallel or phased agents, use Orca
orchestration (skill: `.agents/skills/orca-orchestration/SKILL.md`).

```
# Split independent packets across parallel free workers
orca orchestration task-create --spec "RE-C1: classifier + routing" --json
orca orchestration task-create --spec "RE-C2: context budget" --json
orca orchestration dispatch --task <id> --to <term> --inject --json

# Run a phased pipeline (audit → fix → review)
orca orchestration task-create --spec "Phase 1: audit" --json
orca orchestration task-create --spec "Phase 2: fix" --deps '["task_1"]' --json
orca orchestration run --spec "audit pipeline" --max-concurrent 1 --json

# Hand off in-progress work between agents
orca orchestration send --to @idle --type handoff --subject "..." --body "..."
```

The Orca orchestration layer is complementary to the Builder queue — Orca
manages live agent sessions and worktree isolation; Builder owns durable task
state and publication rails. Use Orca for parallel execution within a session;
use Builder for multi-session campaigns with evidence-gated auto-merge.

## Compute governor — spend once per unchanged SHA

The free/paid split above stops paid models from doing typing work. It does not
stop an agent from planning the same task twice, reviewing its own review, or
re-auditing an unchanged tree on the next wake-up. `gateway/compute_governor.py`
is the gate in front of dispatch that does.

Every dispatch must declare a concrete artifact, acceptance tests, allowed
scope, exclusions, a risk class, and a stopping condition. A dispatch missing
any of those is rejected, not downgraded — the answer to vague work is not a
cheaper model.

One planning pass and one independent review are allowed per unchanged
`(task_type, subject_ref, head_sha)`. Each settled pass writes a durable receipt
to `data/compute_governor/receipts.db`. A second pass on the same SHA is
rejected unless the head SHA moved, the dispatch fingerprint changed
(requirements, scope, acceptance tests), or a human named an override reason. A
pass that *failed* does not consume the allowance — that work is still owed.

These work kinds are always rejected: `analysis_only`, `prompt_polishing`,
`repeat_audit`, `review_of_review`, `duplicate_packet`, `speculative_cleanup`.

Routing follows ADR 0021, in three tiers:

| Route | Model | When |
| ----- | ----- | ---- |
| `free` | the zero-cost OpenCode ladder above | whenever a free worker can carry the packet |
| `cheap` | DeepSeek V4 Flash + MiniMax M3 | routine paid implementation + independent review |
| `frontier` | DeepSeek V4 Pro + Qwen3.7 Max | explicit risky/blocker escalation subject to reserve floors |

Reserve pressure protects the frontier route, not the work itself. Below
`frontier_floor_ratio` a frontier dispatch downgrades to Flash; below
`hard_floor_ratio` it defers. Routine work is never stalled by a ratio floor —
a stalled repair costs more than it saves — but nothing runs on money that is
not there: if a pass projects more than the reserve has left, it defers or
downgrades on the arithmetic rather than the ratio.

### Where the budget number comes from

At the snapshot prices in `gateway/token_spend_report.py` (the single price
source; the governor imports it rather than keeping its own copy):

| Pass | Worker + reviewer | Token shapes | Cost |
| ---- | ----------------- | ------------ | ---- |
| routine | DeepSeek V4 Flash + MiniMax M3 | worker 60k in / 8k out + review 30k in / 3k out | CAD 0.0624 |
| frontier | DeepSeek V4 Pro + Qwen3.7 Max | worker 120k in / 15k out + review 30k in / 3k out | CAD 0.1563 |

At those conservative snapshot prices, ~10 tasks x 3 head SHAs x
(plan + review + implement), at 85% routine, models to about **CAD 6.65** — about
**CAD 9.97** with 50% retry headroom. The configured **CAD 6.00/week** remains a
hard reserve ceiling rather than a promise to fund that whole synthetic week:
Builder gates each paid attempt on the full configured worker+reviewer pair and
defers or downgrades before the remaining reserve can be overrun. Thresholds live in
`config/compute_governor.json`. Generic governor route pricing and Builder's
configured paid-pair pricing have separate regression tests, so route or price
changes cannot silently turn into zero-cost or under-budgeted Builder receipts.

```bash
./kitty governor explain dispatch.json   # dry run: run / defer / downgrade / reject, with reasons
./kitty governor ledger                  # this week's local usage estimate
./kitty governor receipts                # what was actually spent, per pass
```

### Where the gate actually fires

`run_packet` consults the governor when it is given a `governor_db`, right after
the packet's durable base SHA is resolved and before any attempt is created.
The requested route is part of the dispatch identity: explicit free runs are
authorized as `free` with zero estimated spend, while paid routes are checked
against reserve policy. Refusals and route downgrades are durable events.

`./kitty builder initiative run-packet` passes it **by default** — a real
dispatch spends real money, so the receipt check is opt-out (`--no-governor`),
not opt-in. `--governor-override "<reason>"` re-authorizes a pass that already
settled at this base SHA, and lands as its own visible receipt rather than
being folded into the first one. Library callers that omit `governor_db` are
ungoverned, which keeps the loop's unit tests exercising loop behaviour rather
than budget behaviour.

The weekly ledger is **Kitty's own arithmetic over its token ledger**. It is an
estimate for steering, not a provider invoice, and it never equals a provider's
meter.
