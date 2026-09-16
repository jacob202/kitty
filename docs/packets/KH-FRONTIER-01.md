# KH-FRONTIER-01 — remove the frontier tier

**Initiative:** kitty-hardening-v1
**Owner:** builder
**Depends on:** KH-ROUTE-01
**Free or paid:** free

## What Jacob can do after this

Stop carrying a spend tier that has never been able to run, and stop wondering
whether it is the escalation path when something is stuck.

## Why this is the next thing

Frontier names two models and neither is registered with any provider:

- `openrouter/deepseek/deepseek-v4-pro`
- `openrouter/qwen/qwen3.7-max`

The openrouter block in `opencode.jsonc` registers three models —
`deepseek/deepseek-v4-flash`, `minimax/minimax-m3`, `qwen/qwen3.7-plus` — and
neither frontier model is among them. So `--tier frontier` dies exactly the way
the cheap route died on 2026-09-15, with `UNKNOWN_MODEL` before a single token is
billed.

It is worse than dead weight because of when it would be reached for. Frontier is
the escalation you take when a packet has already failed twice and something
important is stuck. That is the worst possible moment to discover the tier was
never wired to anything.

Jacob's call, 2026-09-16: get rid of it.

One correction worth recording, because it nearly went into this packet as
justification: `frontier_floor_ratio` does **not** reserve a quarter of the
weekly budget for frontier. It is a downgrade threshold — when the remaining
reserve falls to or below 25%, a frontier request is downgraded to cheap.
Removing the tier therefore frees no money. The case for removal is that it
cannot run, not that it costs anything.

## Plan

1. Remove the `frontier` entry from `config/builder_paid_routes.json`.
2. In `gateway/compute_governor.py`, remove `ROUTE_FRONTIER`, its entry in
   `ROUTE_MODELS`, and its pass-cost shape.
3. Remove the frontier downgrade branch. A dispatch that previously downgraded
   from frontier to cheap now simply runs as cheap; nothing should newly fail.
4. Remove `frontier_floor_ratio` from the reserve config and from
   `DEFAULT_RESERVE_CONFIG`, and drop the validation that requires
   `hard_floor_ratio` to sit below it. Loading a config that still carries the
   old key must not crash — Jacob's machine and any checkout in flight will have
   one for a while yet. Ignore it rather than rejecting it.
5. Keep the hard floor. It is the thing that refuses a dispatch with too little
   budget left, and it is not what is being removed here.
6. Remove `--tier frontier` from `gateway/builder_cli.py`, so an attempt to
   escalate is rejected as an unknown tier at the command line instead of
   accepted and failed at the provider.
7. Update `docs/FREE_WORKERS.md` and `docs/CAMPAIGN_PLAYBOOK.md`, both of which
   currently offer frontier as a launch shape.

## Not in scope

Registering the frontier models to make the tier work instead — that decision was
made and went the other way. Changing the cheap route, the free ladder, or the
weekly ceiling. Touching the archived design documents under `docs/archive/`,
which are history and should keep describing what was true when they were
written.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_compute_governor.py tests/test_builder_paid_routing.py tests/test_builder_cli.py tests/test_builder_supervisor.py
python -m ruff check gateway/compute_governor.py gateway/builder_cli.py gateway/builder_paid_routing.py
```

Today these collect 50, 27, 131 and their supervisor siblings, all passing, and
several assert frontier behaviour directly — `test_run_packet_frontier_is_
explicit_paid_escalation` among them. Those assertions are the ones this packet
rewrites, so the file-level pass/fail before and after is the real signal: every
frontier assertion should be gone or inverted, and nothing else in these files
should move.

**Tier 2 — running app.** Not applicable.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if removing the downgrade branch cannot be done without
changing what a *cheap* dispatch decides. Frontier removal must not alter the
cheap path's behaviour under a low reserve; if it does, the ladder is entangled
in a way that deserves its own packet rather than being untangled inside this
one.

## Recovery

Revert the changed files to `HEAD`. Nothing persists: routes are read from config
on each dispatch, so reverting restores the previous behaviour completely. If the
packet half-lands — the config entry gone but the governor still referencing
`ROUTE_FRONTIER` — that combination raises on load rather than running with a
missing route, which is the safe direction, but do not leave it there.
