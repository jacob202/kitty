# Kitty - Start Here

This is the front door for agents and future Jacob.

## What Kitty Is

Kitty is Jacob's local-first AI companion. The near-term goal is not more spectacle; it is daily-use reliability: Kitty starts cleanly, captures thoughts quickly, resurfaces them, and keeps Jacob's data local.

## Read In This Order

1. `docs/PROJECT_STATUS.md` - current branch, status, dirty work, and verification.
2. `docs/ARCHITECTURE.md` - current runnable stack.
3. `docs/DECISIONS.md` - settled architecture decisions.
4. `docs/LEARNINGS.md` - hard lessons and guardrails.
5. `docs/AGENT_HANDOFF.md` - latest continuation package.

For the full tagged doc index (🟢 canonical / 🔵 active / 📘 guide / 🗄️ historical / ⚙️ generated), see `docs/README.md`.

## Default Commands

```bash
git status --short --branch
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
```

## Current Rule

Phase B and C are shipped. Do not build new mobile, cloud sync, agent dashboards, or extra memory systems. Make the existing product boring, visible, and trustworthy first.
