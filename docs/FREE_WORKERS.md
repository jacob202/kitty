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

```bash
# Drive one packet through implement → validate → review with free workers
./kitty builder initiative run-packet <initiative-id> <packet-id> --free --watch

# Drive a whole initiative, packet by packet, on free workers
./kitty builder initiative run <initiative-id> --free --max-attempts 12

# One-shot task card outside the queue (clean isolated worktree required)
bash scripts/opencode_free_train.sh <task-card.md>
```

`--free` wires in `scripts/kittybuilder_opencode_worker.sh` as the worker and
`scripts/kittybuilder_opencode_reviewer.sh` as the reviewer. It replaces
`--worker-command`/`--review-command`; passing both is an error.

## The free-model ladder

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
- Nothing in this path pushes or merges. Publish stays operator-gated
  (`--publish` on `initiative run` still goes through KB-S4b gates).
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
