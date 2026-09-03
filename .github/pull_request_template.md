## Summary
- what changed and why

## Test plan
- [ ] commands run
- [ ] exact pass/fail counts

> Summary/Test plan are useful review context, not merge-policy ceremony.

## User outcome
- User outcome advanced: <!-- what becomes true for Jacob/user because of this PR -->
- Governing outcome/acceptance contract: <!-- Mission, packet demo contract, issue, or explicit user request -->
- Exact running candidate or exact repository state used for proof:
- Evidence that proves the outcome rather than only the implementation:
- Isolated data root: <!-- required when automated acceptance/runs write app state; never Jacob's canonical app data -->

> A commit, packet, test suite, subagent `DONE`, green PR, or merge is implementation evidence. It does not by itself close the user outcome. User-facing runtime work requires proof on the exact running candidate.

## Scope and risk
- Area: <!-- backend / frontend / docs / ci / mixed -->
- Risk: <!-- low / medium / high -->
- User-facing impact:

## Product acceptance (required only when `gateway/kitty-chat/src/` or `public/` changes)
- User goal: <!-- what a person is trying to accomplish, in ordinary language -->
- Starting state and dependent services:
- Running-app steps and visible result:
- Failure/recovery path tested:
- Viewports tested: <!-- iPhone-class + desktop -->
- Evidence: <!-- ordered screenshots or short recording from the running app -->
- Independent task-completion reviewer:
- Remaining limitations or dead ends:

- [ ] Every visible primary control either completes its task or is disabled with one clear recovery action.
- [ ] I tested required services both available and unavailable/misconfigured.
- [ ] There is no horizontal page overflow, clipped dialog, obscured action, or off-screen primary navigation at the mobile viewport.
- [ ] Errors explain what failed and what the user can do next; no raw server error is the primary message.
- [ ] Normal user workflows do not require packet IDs, KTF phases, ports, env vars, YAML, MCP, LiteLLM, terminal commands, or Mac file paths.
- [ ] A reviewer who did not implement the change completed the task in the running app.

See `docs/PRODUCT_ACCEPTANCE.md`.

## Guardrails
- [ ] I kept the diff scoped to the stated task.
- [ ] Sensitive scope has explicit final-head approval when required.

Sensitive scope (auth/security, CI policy, approval/action boundaries, publication/destructive paths, secrets/env, dependency roots) requires `risk/approved` plus:

<!-- Risk approval format: Risk approval: APPROVE <full-head-SHA> — <reason> -->

It also requires trusted independent review for the exact current head. Automated review is advisory for ordinary PRs. If independent review is unavailable or a finding is independently proven false, the explicit exact-head escape hatch is:

<!-- Review override format: Review override: APPROVE <full-head-SHA> — <reason> -->

with label `review/override-approved`. Any push makes old approval/review evidence stale.

Large PR size is advisory only; split a PR when doing so improves reviewability, not to satisfy a mechanical threshold.
