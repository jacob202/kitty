# Handoff & compact (all tools + Cursor)

Last updated: **2026-05-13**

**Single canonical doc** for: saving session state before you drop context, and Cursor’s **Compact chat** shortcut to the same habit.

---

## Universal pattern (every AI environment)

Long transcripts are expensive and noisy. **Durable truth belongs in git-backed Markdown** before you truncate or start a new chat.

1. **Sweep** — skim the last exchanges; anything the next session must not re-infer → write it down.
2. **Write** — update **`SESSION_HANDOFF.md`** (repo root): what works, what broke, commands, files, risks, “not doing X,” next step.
3. **Reconcile** — if you use **`SESSION_SUMMARY.md`**, align it with the handoff so they don’t contradict.
4. **Compact / new thread** — clear ephemeral chat; tracked files stay.
5. **Resume** — first message in the new session: **@`SESSION_HANDOFF.md`** (plus **`AGENTS.md`** for full rules).

Never paste secrets, API keys, or full `.env` into handoffs.

---

## Cursor (Compact chat)

Cursor can **Compact** a thread without deleting repo files.

**Before compact:** refresh **`SESSION_HANDOFF.md`**; optional glance at **`AGENTS.md`** if you changed rules/stack.

**After compact:** start the next chat with **`@SESSION_HANDOFF.md`** (“read handoff first”).

---

## Other tools

| Tool | Compact | Resume |
|------|---------|--------|
| Claude Code | `/clear` or new session | `@SESSION_HANDOFF.md` |
| Codex / CLI | new conversation | Paste path to `SESSION_HANDOFF.md` |
| Gemini | new chat | Attach handoff from workspace |
| Web playgrounds | export if you care | Prefer repo handoff |

---

## Where durable facts go

| Horizon | File |
|---------|------|
| This week / session | `SESSION_HANDOFF.md`, `SESSION_SUMMARY.md` |
| Roadmap & phases | `docs/UNIFIED_IMPLEMENTATION_PLAN.md` + root `TASKS.md` |
| Durable decisions | `docs/DECISIONS.md` |
| Approved build work | `specs/*.md` |

Rule file for Cursor automation: **`.cursor/rules/cursor-compact.mdc`** (points here).
