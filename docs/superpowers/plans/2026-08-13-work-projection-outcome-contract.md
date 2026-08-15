# Outcome Contract — Work Projection Vertical Slice

## Identity
- Task: Gateway authoritative Work projection over Builder
- Execution owner: `interactive`
- Branch/worktree: `feat/campaign-work-projection-v1` / `.worktrees/campaign-work-projection-v1`
- Base SHA: `1172f98e49b46d0d13c69fbf0832875c8255777b`
- Repair-cycle limit: `2`

## User-visible outcome
Kitty clients can read one Gateway endpoint and see real Builder work in product language: current state, current packet/run, blocker, truthful approval availability, validation/review evidence, and next action—without a second task store.

## Acceptance criteria
| ID | Observable criterion | Verification | Evidence |
|---|---|---|---|
| AC-1 | `GET /work` derives items solely from the supported Builder snapshot and performs no Builder writes | focused route/projection tests + architecture fitness | passing test output + diff |
| AC-2 | Active, ready, blocked, paused, failed, completed, and partial/unavailable evidence map truthfully; missing approval link is explicitly unavailable | table-driven projection tests | passing test output |
| AC-3 | A snapshot read failure returns fail-loud `503`, never an empty-success Work list | route failure test | passing test output |
| AC-4 | Real canonical Builder DB can be projected read-only and includes a known KPROOF initiative with matching identity/state | isolated runtime probe against canonical Builder DB | captured JSON summary |
| AC-5 | Separate verifier inspects reviewed SHA/diff and reruns AC-1..AC-4 checks | independent review process | PASS/FAIL/UNVERIFIED report |
## Non-goals
- No Builder mutation, queue, scheduler, or persistence.
- No Discord changes, Console changes, image changes, service restart, publishing, paid calls, credentials, or auth changes.
- No inferred approval state without a durable identity link.

## Prohibited shortcuts
- Do not query Builder SQLite directly from the Work layer.
- Do not infer runtime success from code inspection alone.
- Do not treat the implementer's self-review as independent acceptance.
- Do not convert missing evidence into `completed`, `approved`, or healthy defaults.

## Required evidence artifacts
- This contract and the design/implementation plan.
- Focused RED then GREEN test outputs.
- `git diff --check`, scoped diff, and changed SHA.
- Real read-only projection receipt from the canonical Builder DB.
- Independent verifier report by criterion.

## Handoff facts
- Current implementation state: not started.
- Changed paths: documentation only until TDD RED is recorded.
- Known blocker outside this packet: production Gateway/UI are running from different stale checkouts.
- Exact next action: write the first failing `GET /work`/projection tests and prove RED.

## Final state
`implemented, awaiting verification` until AC-1..AC-5 all pass independently.