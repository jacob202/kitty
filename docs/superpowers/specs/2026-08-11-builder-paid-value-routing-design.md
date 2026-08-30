# Builder Paid Value Routing Design

**Status:** Approved by Jacob in chat on 2026-08-11.
**Implements:** KTB-PAID-01 from `docs/research/KITTY_KITTYBUILDER_ARCHITECTURE_CORRECTION_2026-07-28.md`.

## Goal

Add an explicit governed paid OpenRouter execution lane without weakening or replacing the current free lane. Optimize for cost per independently accepted packet rather than cost per token.

## Route policy

- `cheap`: default paid tier for routine implementation. Worker is DeepSeek V4 Flash through OpenRouter.
- `frontier`: explicit escalation tier for risky/blocker work. Worker is DeepSeek V4 Pro through OpenRouter.
- Review always runs in a separate read-only agent and uses a separately configured model route.
- Paid execution is opt-in. No accidental free-to-paid fallback is allowed.
- Route/model choices live in checked-in config; credentials remain outside the repository.
## Safety and economics

- `config/builder_paid_routes.json` is the authority for paid enablement, model allowlists, governor route, and per-pass projected-cost ceiling.
- The existing compute governor remains the spend authority. A paid run must receive `run`/`downgrade` permission before an attempt opens.
- Existing packet `max_attempts`, runtime deadline, stopping rule, worktree/lease fencing, validation, review, publication, and provider-exhaustion semantics remain unchanged.
- The selected route, projected cost, model, provider, and governor decision are written into the attempt manifest/evidence.
- Disabling `paid_openrouter_enabled` restores free/explicit-command-only behavior without data migration.

## CLI

`./kitty builder initiative run ... --paid --tier cheap|frontier`

`cheap` is the default tier. `--paid` is mutually exclusive with `--free`, explicit worker/reviewer commands, and model overrides. Frontier is explicit and must still pass governor reserve rules.

## OpenCode boundary

Add `paid-builder` and `paid-reviewer` agents. The free agents remain unchanged. Existing adapter mechanics may be reused only by parameterizing the agent name while preserving `free-builder` / `free-reviewer` as the defaults.

## Acceptance

1. Existing free tests remain green and free commands still select free agents.
2. Paid dry-run/config resolution explains model, route, and projected cost without calling a model.
3. Disabled paid config blocks paid execution before attempt creation.
4. Paid CLI selects the configured models/provider and passes the intended risk tier into the governor.
5. Attempt evidence records governor route/projected cost plus model/provider.
6. No paid fallback occurs unless `--paid` is explicitly present.
