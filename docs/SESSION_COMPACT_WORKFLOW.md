# Session compact workflow (all AI coding tools)

**Use this pattern in every environment** where you collaborate with an AI on this repo: Cursor, Claude Code, Gemini CLI, Codex, OpenRouter “playground” chats, JetBrains AI, etc.

The problem is the same everywhere: **long transcripts are expensive, easy to lose, and full of noise**. The fix is the same: **move durable truth to git-tracked Markdown before you truncate or start a new conversation**.

---

## Universal steps (tool-agnostic)

1. **Sweep** — scroll the last few exchanges; anything an agent must know to continue without re-deriving belongs in a file.
2. **Write** — update **`SESSION_HANDOFF.md`** (repo root). Include: what works, what broke, exact commands, filenames, open risks, “explicitly not doing X,” next action.
3. **One narrative** — reconcile with **`SESSION_SUMMARY.md`** if you use both; do not keep two conflicting truths.
4. **Compact / new thread** — wipe or leave the old chat; tracked files stay.
5. **Resume** — first message in the new session: attach or @-mention **`SESSION_HANDOFF.md`** (and **`AGENTS.md`** for full rules).

**Never** paste secrets, API keys, or full `.env` into handoff files.

---

## Tool-specific hooks

| Tool | How you “compact” | How you resume |
|------|-------------------|----------------|
| **Cursor** | **Compact chat** (or new Composer) | `@SESSION_HANDOFF.md` + “read handoff first”; see also `docs/CURSOR_COMPACT.md` |
| **Claude Code** | `/clear`, new session, or workspace thread reset | Same handoff file; point Claude at `@SESSION_HANDOFF.md` |
| **OpenAI Codex / CLI chats** | New conversation / exhausted context | Paste a one-line pointer: repo path + “read SESSION_HANDOFF.md” |
| **Gemini (IDE / CLI)** | Start new chat when context fills | Attach `SESSION_HANDOFF.md` via workspace or paste path |
| **OpenRouter / web playgrounds** | N/A — copy/export if you cared about reasoning; prefer repo handoff | — |
| **Any cloud agent (PR bots, etc.)** | Job ends after one task | Leave handoff updated for the human or the next agent |

There is **no universal button** labeled “compact” outside Cursor; the **behavior** (“save handoff, then discard ephemeral context”) is what you standardize across tools.

---

## Optional longer-form decisions

Anything that must survive **beyond the current week** belongs in **`docs/DECISIONS.md`** or a spec under **`specs/`**, not only in the handoff.

---

## Canonical links

| File | Role |
|------|------|
| `SESSION_HANDOFF.md` | Scratchpad **you** refresh before ditching context |
| `AGENTS.md` | Repo-wide agent rules (**all** assistants) |
| `docs/CURSOR_COMPACT.md` | Cursor-only shortcut (points here) |
