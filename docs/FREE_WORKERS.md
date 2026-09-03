# KittyBuilder Model Routing — DSH Free + Paid Lanes

KittyBuilder has two explicit model-execution lanes. Both run through the same
DeepSeek Harness (DSH) worker/reviewer adapters and the same durable Builder
attempt, worktree, validation, review, evidence, and publication machinery.
The route changes; the execution authority does not.

- `--free` is zero-spend. It accepts only explicitly free OpenRouter models and
  never falls through to a paid route.
- `--paid` uses the governed OpenRouter value route and requires the compute
  governor. `--tier cheap` is the default; `--tier frontier` is an explicit
  escalation request.
- Omitting both is not an implicit default: supply `--free`, `--paid`, or an
  explicit custom worker command.

The command contract lives in `gateway/builder_cli.py`. Adapter behavior lives
in `scripts/kittybuilder_dsh_worker.sh`, `scripts/kittybuilder_dsh_reviewer.sh`,
and `scripts/kittybuilder_dsh.sh`. Paid model/ceiling configuration lives in
`config/builder_paid_routes.json`.

## Prerequisites

The DSH execution paths require:

- the `dsh` CLI;
- Kitty's tracked `kitty-forge` preset under `config/dsh/presets/`;
- an `OPENROUTER_API_KEY` available to the adapter (the launcher may read it
  from the repository `.env`);
- an eligible Builder initiative/packet and isolated task worktree.

Missing provider capacity or a missing DSH runtime fails visibly. A `--free`
request is never rescued by spending money.

## Current routes

### Free

`--free` resolves the tracked DSH worker and read-only DSH reviewer adapters.
The worker currently tries these checked-in zero-cost defaults in order:

1. `openrouter/poolside/laguna-xs-2.1:free`
2. `openrouter/tencent/hy3:free`

The default free reviewer is
`openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`.

Force one free model for a CLI run with `--model`; it must be
`openrouter/free` or an `openrouter/...:free` identifier:

```bash
./kitty builder initiative run-packet <initiative> <packet> \
  --free --model openrouter/poolside/laguna-xs-2.1:free --watch
```

Free provider availability is external and can change. The adapter source is
the authority for the current fallback list; documentation must not invent a
replacement model when one disappears.

### Paid

`--paid` resolves the same DSH adapters with a governed paid route. Current
checked-in routes are:

| Tier | Worker | Independent reviewer | Per-attempt configured ceiling |
| --- | --- | --- | ---: |
| `cheap` | DeepSeek V4 Flash | MiniMax M3; Qwen 3.7 Plus fallback | CAD 0.10 |
| `frontier` | DeepSeek V4 Pro | Qwen 3.7 Max | CAD 0.50 |

The exact model IDs and ceilings are owned by `config/builder_paid_routes.json`.
The cheap lane's primary **DeepSeek V4 Flash + MiniMax M3** pair currently
projects to **CAD 0.0624** for the configured attempt assumptions. That value is
a route estimate, not a spend guarantee; the CAD 0.10 ceiling and compute
governor remain authoritative.
The compute governor still decides whether a requested paid dispatch may run,
downgrade, or defer; the configured ceiling is not a promise that the full
amount will be spent.

```bash
./kitty builder initiative run-packet <initiative> <packet> --paid --watch
./kitty builder initiative run-packet <initiative> <packet> \
  --paid --tier frontier --watch
```

## Shadow execution versus publication

`initiative run-packet` drives one packet through implement → validate → review
in **shadow mode**. It does not push, open a PR, or merge.

For a multi-packet initiative, `initiative run` is also non-publishing unless
`--publish` is present:

```bash
# Execute without publication.
./kitty builder initiative run <initiative> --free

# Execute and enter Builder's publication path.
./kitty builder initiative run <initiative> --paid --publish

# With --publish, auto is the default gate; manual parks for operator review.
./kitty builder initiative run <initiative> --paid --publish --gate manual
```

`--gate auto` means the evidence-gated Builder publication/auto-merge policy; it
is not permission for an arbitrary agent to merge an unrelated PR. `--gate
manual` parks the packet at the review boundary for a human merge decision.

## Fail-loud fallback rules

A worker model may hand off to the next configured model only after a **clean**
failure:

- no result contract was written;
- `HEAD` did not change;
- the worktree did not change.

Any partial mutation stops fallback and preserves the worktree for inspection.
A result contract paired with a non-zero process exit is refused. The reviewer
is read-only and must leave both `HEAD` and the worktree unchanged.

Builder binds task/attempt identity, bundle hashes, review SHA, and diff hash
before trusting worker/reviewer results. Deterministic validation is executed by
trusted Builder orchestration rather than accepted from model narration.

## Timeouts

`--timeout` defaults to 3600 seconds for packet execution. The DSH adapters also
have bounded startup/review windows so an unavailable model can fail cleanly
without consuming the whole packet budget. Relevant adapter settings include:

```bash
KB_MODEL_STARTUP_TIMEOUT_SECONDS=30
KB_REVIEW_MODEL_STARTUP_TIMEOUT_SECONDS=30
KB_REVIEW_TIMEOUT_SECONDS=240
```

Once a model has begun meaningful work, the remaining packet budget—not a fresh
per-model budget—stays authoritative. A clean timeout may fall through to the
next configured model; partial work may not.

## Compute governor

Paid Builder dispatch goes through `gateway/compute_governor.py`. The governor
uses durable receipts to prevent repeated paid planning/review on unchanged
work and enforces the current reserve policy in `config/compute_governor.json`.
Do not copy price snapshots into operating instructions; provider pricing and
route configuration change independently.

Useful read-only commands:

```bash
./kitty governor explain dispatch.json
./kitty governor ledger
./kitty governor receipts
```

`initiative run-packet` and `initiative run` pass the governor database by
default. `--no-governor` is an explicit bypass for non-paid/custom execution;
`--paid --no-governor` is rejected. `--governor-override "<reason>"` records a
human reason when a previously settled pass at the same base SHA must run again.

## Safety boundaries

- Builder owns task, attempt, lease, worker, review, recovery, and publication
  truth. DSH is a replaceable execution adapter, not another queue.
- Workers run in isolated task worktrees and receive bounded packet/context
  artifacts. They do not gain authority to widen allowed paths.
- Review uses a separate read-only model path and is bound to the exact review
  SHA/diff.
- Free endpoints may log prompts. Never expose `.env`, credentials, runtime
  personal data, or private memories to a free route.
- Provider/model unavailability is reported as unavailable; it does not justify
  a silent route change or paid fallback.
- Cross-agent communication belongs in `workspace_global`; interactive ownership
  remains separate from Builder's durable execution state.

For queue lifecycle, fencing, recovery, and operator commands, use
[`KITTYBUILDER_QUICKSTART.md`](KITTYBUILDER_QUICKSTART.md).
