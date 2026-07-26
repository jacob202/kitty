# Free Workers — Token-Efficient Delegation

The point: Claude/Codex tokens are the scarce resource; free OpenCode models
are not. Kitty's delegation loop is built so the expensive model does the
thinking once (packets, contracts, review of the final diff) and zero-cost
models do the typing. This doc is the operating manual for that split.

## Who does what

| Stage | Who | Cost |
| ----- | --- | ---- |
| Author the packet (objective, allowed paths, acceptance, validation) | Claude/Codex | paid, once |
| Implement the packet in an isolated worktree | free OpenCode builder ladder | free |
| Independent read-only review of the attempt | free OpenCode reviewer ladder | free |
| Deterministic validation (declared test commands) | the runner itself | free |
| Final diff review + merge decision | Jacob (with Claude if needed) | paid, small |

A packet that a free model can't finish after the bounded repair loop comes
back as honest evidence (`exhausted`, with transcripts and manifests) — that,
and only that, is when paid tokens re-enter.

## One-command launch

Both adapters walk the same zero-cost ladder the free train uses
(`opencode/deepseek-v4-flash-free` → `opencode/mimo-v2.5-free` →
`opencode/nemotron-3-ultra-free` → `opencode/north-mini-code-free` →
OpenRouter free fallbacks). Free endpoints rate-limit and flake; the ladder is
what makes a single attempt survive that without burning the attempt budget.

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
KITTYBUILDER_REVIEW_MODEL=...                        # force one reviewer model
KITTYBUILDER_REVIEW_MODELS="modelA modelB"           # replace the reviewer ladder
```

`--free --model <id>` on the CLI is shorthand for forcing one builder model.
Keep the reviewer ladder disjoint from the builder model actually used — the
review is only worth anything if it's independent.

## Safety rails (already enforced, don't re-litigate)

- `opencode.jsonc` denies push, PR create/merge, destructive git, `rm`,
  external directories, and subagent spawning even under `--auto`, and pins
  the `free-builder`/`free-reviewer` agents to free providers only.
- The adapters verify task/attempt identity and bundle SHA-256 before any
  model runs, stage runner files into the worktree, and only copy validated
  contract JSON back out.
- Publish auto-merges by default (`gate=auto`); pass `--gate manual` to park
  at `awaiting_review` for operator review.
- Free endpoints may log prompts. Public repo code and task instructions
  only — never `.env`, credentials, runtime personal data, or private
  memories.

## What still costs paid tokens (keep it that way)

1. Writing good packets. A vague packet wastes free attempts and then paid
   diagnosis; a tight one (docs/packets/TEMPLATE.md) is the whole trick.
2. Reading the final diff before merge.
3. Unblocking an `exhausted` packet — read the attempt manifests under
   `data/kittybuilder/` and the transcripts before spending anything else.

## Timeouts

The worker timeout (`--timeout`, default 3600s) covers the whole ladder walk
for one attempt, not one model. If every free endpoint is slow the attempt
fails loudly at the deadline; that is an availability fact worth seeing, not
a bug in the loop.

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

Routing follows ADR 0021: `routine` risk goes to the free ladder above;
`risky` and `blocker` may take a frontier route, and `blocker` must name the
verified failure. Reserve pressure only ever affects the paid route — free
routine work is never stalled by budget, because a stalled repair costs more
than it saves. Below `frontier_floor_ratio` a frontier dispatch downgrades to
free; below `hard_floor_ratio` it defers. Thresholds live in
`config/compute_governor.json`.

```bash
./kitty governor explain dispatch.json   # dry run: run / defer / downgrade / reject, with reasons
./kitty governor ledger                  # this week's local usage estimate
./kitty governor receipts                # what was actually spent, per pass
```

The weekly ledger is **Kitty's own arithmetic over its token ledger**. It is an
estimate for steering, not a provider invoice, and it never equals a provider's
meter.
