# Campaign Playbook

How a paid-model session (Claude Code / Kitty chat with Jacob) turns "I want
X" into a running Builder initiative. This is a procedure, not new runtime —
see `docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md` §1.1 for why.

Skip all of this for a narrow fix: `./kitty builder queue add` +
`./kitty builder queue run <id> -- <worker-command>` runs one bounded task
with no clarification, no gate, no initiative. Use the playbook only when the
ask is a feature/campaign, not a one-line change.

## 1. Clarification interview

1. Restate the ask back in one paragraph. Confirm Jacob agrees it's right.
2. List assumptions you're making, each with a disposition (proceed on this
   assumption unless told otherwise — the ADR 0017 `assumptions[]` pattern).
3. Ask Jacob only the questions that would change the manifest. One round.
   If his answers contradict each other, ask a second round; otherwise stop.
4. If you cannot write a validation command for an acceptance criterion,
   the interview isn't done — that's threshold T4 below, not a modeling gap.

## 2. Decide: does this need a prototype packet?

Insert a `<initiative>-proto` packet when **any** hold:

| # | Condition | How it's decided |
|---|-----------|-------------------|
| T1 | Manifest has ≥ 4 implementation packets | count `packets[]` |
| T2 | `allowed_paths` span ≥ 2 subsystems | prefix comparison across the union of allowed_paths |
| T3 | Any packet creates a new UI surface or new top-level module | `git ls-files <path>` empty |
| T4 | Any acceptance criterion has no nameable validation command | authoring-time check |

None fire → skip the prototype, author implementation packets directly.

**Prototype packet shape:**

- `id`: `<initiative>-proto`
- `objective`: working skeleton, fixture data allowed, to expose design
  flaws before the full build
- `acceptance_criteria`: observable-demo only (not test coverage, not
  polish, not edge cases)
- `validation_commands`: the demo command, plus the existing suite
- `policy.max_attempts`: 2 — a prototype needing 3+ attempts means the
  clarification failed; stop, don't grind
- every other packet lists `depends_on: ["<initiative>-proto"]`, directly
  or transitively

## 3. Author the manifest

Manifest schema (`builder_initiative._TOP_LEVEL_KEYS` /
`_PACKET_KEYS` — no other keys are accepted):

- Top level: `manifest_version`, `initiative_id`, `title`, `description`,
  `packets`
- Per packet: `id`, `title`, `objective`, `acceptance_criteria`,
  `allowed_paths`, `validation_commands`, `policy`, `depends_on`

See `docs/packets/examples/prototype-gated-example.json` for a complete
4-packet worked example (1 proto + 3 implementation packets).

## 4. Validate, show Jacob, apply

```bash
./kitty builder initiative validate <manifest.json>   # must be zero errors
# show Jacob the manifest — this is his go/no-go, not a rubber stamp
./kitty builder initiative apply <manifest.json>       # atomic; queues one task per packet
```

## 5. Launch cheat-sheet — the four shapes

- **short / free** — `initiative run-packet <init> <packet> --free --watch`
- **short / paid** — `initiative run-packet <init> <packet> --worker-command "<cmd>" --review-command "<cmd>" --watch`
- **long / free** — `initiative run <init> --free --max-attempts 12` (prototype-gated if authored with one; auto-merges downstream per CP-06 unless `--gate manual`)
- **long / paid** — same as long/free with explicit `--worker-command`/`--review-command`; use only after a free run legitimately exhausts (`docs/FREE_WORKERS.md` cost policy)

Full detail and negative tests: `docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md` §3.

## 6. Paid-session tooling (when available)

If Jacob's global Claude Code commands resolve in this environment, use them
in order: `/goals`, then `/design`, then `/feature-developer` per packet,
`/loop` as the outer driver. **Their absence never blocks — this playbook is
the fallback operating procedure and is sufficient on its own.**

Reviewer sessions: check `second-opinion` (`.claude/skills/second-opinion`)
before burning a repair attempt on a borderline verdict.
