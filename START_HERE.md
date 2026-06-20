# Kitty - Start Here

This is the front door for agents and future Jacob.

## What Kitty Is

Kitty is Jacob's local-first AI companion. The near-term goal is not more spectacle; it is daily-use reliability: Kitty starts cleanly, captures thoughts quickly, resurfaces them, and keeps Jacob's data local.

## Read In This Order

1. `docs/PROJECT_STATUS.md` - current branch, status, dirty work, and verification.
2. `docs/ARCHITECTURE.md` - current runnable stack.
3. `docs/PHASE_B_PLAN.md` - next implementation plan.
4. `docs/STORAGE_MIGRATION_PLAN.md` - storage migration details.
5. `docs/DECISIONS.md` - current settled decisions.
6. `docs/LEARNINGS.md` - hard lessons and guardrails.
7. `docs/AGENT_HANDOFF.md` - latest continuation package.

## Default Commands

```bash
git status --short --branch
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
```

## Current Rule

Do not build new mobile, cloud sync, agent dashboards, or extra memory systems in Phase B. Make the existing product boring, visible, and trustworthy first.
