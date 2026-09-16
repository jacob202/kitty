# BFP-04-authoring — stop refusing the gates that now work

**Initiative:** builder-frontend-proof-v1
**Owner:** builder
**Depends on:** BFP-02B-deps, BFP-03-cache
**Free or paid:** free

## What Jacob can do after this

Ask for a change to how Kitty looks and have Builder be allowed to take the job.

## Why this is the next thing

Even with Node working, no one can write a UI packet, because the authoring tool
refuses to accept one. `scripts/packet_preflight.py:294-305` rejects any
validation command containing Node tooling with this message:

> validation command needs Node tooling — a Builder worktree has no node_modules
> (it is gitignored) and the runner exposes no Node toolchain, so this gate
> cannot run.

The second half of that sentence stops being true the moment BFP-03 lands. The
same claim is recorded in `docs/packets/PACKET_STANDARD.md` as failure **F9**,
and §2 of that document says a rule may not be relaxed "without new evidence that
supersedes the old". BFP-01 through BFP-03 are that evidence. This packet spends
it, and leaves the trail intact.

## Plan

1. Narrow the Node-tooling rule in `scripts/packet_preflight.py` so `npx` and
   direct `node` commands are accepted.
2. Keep rejecting `npm run`. That rule has independent evidence behind it —
   `docs/packets/014-make-the-gates-honest.md` records it exiting 194 and
   reporting a success it never proved — and nothing in this initiative touches
   that. Keep rejecting a pinned interpreter version for the same reason.
3. Amend F9 in `docs/packets/PACKET_STANDARD.md`. Keep the row and its evidence;
   add what superseded it and when. Do not delete the history — the next author
   needs to know the rule existed and why, or it grows back.
4. Update §6's "every shape Builder can run today" list so it matches reality.
5. Extend `tests/test_packet_preflight.py` with both the newly accepted shape and
   the still-rejected ones.

## Not in scope

The zero-test-collection check — that is BFP-05, and it shares this file, which
is why it depends on this packet instead of running beside it. Do not author any
actual UI manifest here. Do not relax the forbidden-path rules, the empty-fence
rule, or anything else preflight checks.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_packet_preflight.py
python -m ruff check scripts/packet_preflight.py
```

Today this collects 9 tests and passes, and a manifest carrying
`cd gateway/kitty-chat && npx vitest run tests/Rail.test.tsx --reporter=dot`
is rejected with the message quoted above. After this packet the same manifest
passes preflight and an `npm run` gate is still rejected.

**Tier 2 — running app.** Not applicable.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if the evidence does not exist — that is, if no recorded run
shows a sandboxed worker executing the exact `npx vitest` and `npx tsc` shapes
from `gateway/kitty-chat` and getting a real result. Not "a Node command":
`node --version` succeeding proves the interpreter resolves and says nothing
about whether the dependency tree does, and that distinction is the reason this
packet gained BFP-02B as a dependency.

Relaxing the rule on code that was written but never observed working is how F9
happened the first time. Relaxing it far enough to authorize eight studio gates
that still cannot execute would be worse: a check declared runnable that cannot
run is the same defect as a gate collecting zero tests, which this initiative
exists to remove. No evidence, no relaxation.

## Recovery

Revert `scripts/packet_preflight.py` and `docs/packets/PACKET_STANDARD.md` to
`HEAD`. Nothing else consumes this change until a manifest with a frontend gate
is authored, so a failed attempt has no downstream effect. If a UI manifest was
already authored against a half-landed version of this packet, re-run preflight
against it before applying it.
