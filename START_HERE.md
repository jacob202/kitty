# Kitty - Start Here

This is the front door for agents and future Jacob.

## What Kitty Is

Kitty is Jacob's local-first AI companion. The near-term goal is not more spectacle; it is daily-use reliability: Kitty starts cleanly, captures thoughts quickly, resurfaces them, and keeps Jacob's data local.

## Read In This Order

1. `docs/PROJECT_STATUS.md` - live branch truth, current priority, risks, and verification.
2. `docs/AGENT_RUNTIME.md` - entry protocol, hook surface, and repo-owned agent runtime files.
3. `docs/ARCHITECTURE.md` - current runnable stack.
4. `docs/DECISIONS.md` - settled decisions that should not be re-litigated casually.
5. `docs/LEARNINGS.md` - repeated mistakes and guardrails.
6. `docs/AGENT_HANDOFF.md` - latest continuation package.

Read only when relevant:

- `docs/PHASE_B_PLAN.md`
- `docs/PHASE_C_PLAN.md`
- `docs/STORAGE_MIGRATION_PLAN.md`

## Default Commands

```bash
git status --short --branch
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
```

## Current Rule

Do not add cloud auth, push notifications, new agent dashboards, or new storage systems while the local workflow still has rough edges. Make the existing product boring, visible, and trustworthy first.
