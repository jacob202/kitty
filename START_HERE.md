# Kitty — Start Here

This is the front door for agents and future Jacob.

## What Kitty Is

Kitty is Jacob's local-first AI companion. It runs on his Mac for one user (D1). The gateway is the product — all clients stay thin (D2). Near-term goal: daily-use reliability. Kitty starts cleanly, captures thoughts quickly, resurfaces them, and keeps Jacob's data local.

## Read In This Order

1. `docs/PROJECT_STATUS.md` — current branch, what's shipped, test state, open PR.
2. `docs/ARCHITECTURE.md` — runnable stack (gateway + LiteLLM + Next.js).
3. `docs/DECISIONS.md` — settled decisions. Read before touching architecture.
4. `docs/LEARNINGS.md` — hard lessons and guardrails. Read before touching risky paths.
5. `.claude/HANDOFF.md` — latest continuation package (known issues, verification commands).
6. `.claude/STATE.md` — live session state (current branch, open PRs, claims).

## Default Commands

```bash
git status --short --branch
./kitty up
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
```

## Current Rules

- All context reads go through `gateway/memory_graph.py` — do not bypass.
- Do not push, force-push, rewrite history, delete files, or touch `.env` without explicit confirmation from Jacob.
- Voice/persona lives in `config/SOUL.md`. Do not modify it without Jacob.
