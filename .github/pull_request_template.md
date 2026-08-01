## Summary
- what changed and why

## Test plan
- [ ] commands run
- [ ] exact pass/fail counts

## Scope and risk
- Area: <!-- backend / frontend / docs / ci / mixed -->
- Risk: <!-- low / medium / high -->
- User-facing impact:
- Manual approval: <!-- NO / YES (required for auth/secrets/env/CI/destructive scope) -->

## Product acceptance (required for user-facing changes)
- User goal: <!-- what a person is trying to accomplish, in ordinary language -->
- Starting state and dependent services:
- Running-app steps and visible result:
- Failure/recovery path tested:
- Viewports tested: <!-- iPhone 14 Pro-class + desktop -->
- Evidence: <!-- ordered screenshots or short recording from the running app -->
- Independent task-completion reviewer:
- Remaining limitations or dead ends:

- [ ] Every visible primary control either completes its task or is disabled with one clear recovery action.
- [ ] I tested required services both available and unavailable/misconfigured.
- [ ] There is no horizontal page overflow, clipped dialog, obscured action, or off-screen primary navigation at the mobile viewport.
- [ ] Errors explain what failed and what the user can do next; no raw server error is the primary message.
- [ ] Normal user workflows do not require packet IDs, KTF phases, ports, env vars, YAML, MCP, LiteLLM, terminal commands, or Mac file paths.
- [ ] A reviewer who did not implement the change completed the task in the running app.

See `docs/PRODUCT_ACCEPTANCE.md`. A route, component, unit test, or screenshot alone is not proof that the user task works.

### Not user-facing override
Use only when this PR is genuinely not user-facing. Checking this replaces the product-acceptance block above — it does not satisfy it — and a reviewer must confirm the reason before merge.

- [ ] Not user-facing; the product-acceptance block above is not applicable.
- Reason (required when checked): <!-- one line naming the change class, e.g. "backend-only — gateway route, no UI touched" -->

## Guardrails
- [ ] I did not touch secrets/auth/env paths without explicit approval.
- [ ] I kept the diff scoped to the stated task.
- [ ] I included observable evidence for behavior changes (logs, screenshots, or command output).
- [ ] Manual approval received for risky scope (auth/secrets/env/CI/destructive changes).
