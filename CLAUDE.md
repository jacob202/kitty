# Kitty - Claude Code

Start here: `START_HERE.md`.

## Project Paths

- Active project: `~/Projects/kitty` (NOT Desktop backups)
- Always verify the Git common directory belongs to `~/Projects/kitty`; an
  isolated worktree may live below that canonical checkout
- If working directory is under `~/Desktop/` or a backup folder, STOP and ask
  the user to confirm

## Cold-start bootloader

Do this before relying on inherited context:

1. Verify the canonical checkout and current worktree.
2. Inspect `git status --short --branch`, HEAD, worktrees, and `origin/main`.
3. Run `./kitty context --agent`; stop on failed freshness checks.
4. Follow the receipt's reading order beginning with `docs/AUTHORITY_MAP.md`.
5. Read `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, and `.claude/STATE.md`.
6. Read `.claude/HANDOFF.md` only when its structured status is `valid`.
7. Inspect Builder through `./kitty builder ... --json` when Builder state is
   relevant.
8. Re-verify scope, evidence, packet class, and authorization before acting.

## Execution Defaults

- When the user requests a feature/fix, complete the full approved loop:
  implement, install/setup, verify locally, and preserve evidence.
- After any non-trivial code change, run the narrowest tests that actually cover
  it and report exact pass/fail counts. Not the full suite: naming the specific
  files is the point. Full suite, lint, typecheck, and build are `/qg` (or
  `/qg all`) on request, and CI runs them on every PR. `AGENTS.md` states this
  same rule — change both or neither.
- Local commits are expected.
- Interactive-agent pushes still require Jacob's explicit approval. Builder may
  push its own approved packet branches, create/update PRs, mark them ready,
  and evidence-gated merge low-risk work only under ADRs 0018 and 0021.

## Auth & Environment

- Before any `gh` or git push, check for a stale `GITHUB_TOKEN` environment
  variable and unset it if it conflicts with `gh auth`.
- For LiteLLM/MLX setups, prefer existing local MLX models over pulling new
  Ollama models; verify keys are exported in the current shell, not merely
  present in `.env`.

## Working Contract

Jacob describes outcomes in plain language. You are the engineer: decode intent,
protect him from hidden technical mistakes, and leave durable evidence. Be
direct when an idea has a problem. Do not flatter bad plans into existence.

Put working detail in files and evidence artifacts. Chat gets the outcome,
failures, and decisions Jacob must make.

## Initiative

See `.claude/rules/initiative.md`. Persona and noticing rules live in
`config/SOUL.md`.

## Non-Negotiables

1. Fail loud. No silent exception swallowing, fake defaults, or invented data.
2. Verify before claiming. Done means a command ran and its output was read.
   If a claim cannot be checked, say so explicitly.
3. Keep diffs small. Do not reformat or rewrite unrelated code.
4. Do not force-push human branches, rewrite history, delete user data, touch
   secrets/auth/env, spend money, or add heavy dependencies without explicit
   confirmation.
5. **Builder carve-out:** under approved packets and ADRs 0018/0021, the
   operator-context Builder path may commit, push its disposable packet branch,
   create/update a PR, mark it ready, and merge only low-risk evidence-gated
   work. Workers never receive GitHub credentials or approve themselves.
6. Auto-merge is forbidden for dependency/lockfile/CI/auth/security/destructive/
   schema/human-judgment work, path collisions, unverifiable gates, or scope
   expansion. Such work may stop at a draft PR when authorized.
7. New durable architecture decisions go in `docs/DECISIONS.md` / `docs/adr/`;
   workflow lessons go in `docs/LEARNINGS.md`.
8. `docs/ROADMAP.md` is the only active roadmap. Other plans are inputs, not
   authority.

## Session State

Read `.claude/HANDOFF.md` and `.claude/STATE.md` at the start of every session,
but trust either only while its identity and invalidation conditions remain
valid.

These are shared files, not a session journal. Before writing either: fetch and
read the live `origin/main` copy. Do not clobber a different active workstream.
Isolated Builder worker attempts must not touch `.claude/`.

## Authority

`docs/AUTHORITY_MAP.md` is the only routing map for project truth. This file is
a bootloader and Claude-specific glossary, not a second status, architecture,
or roadmap authority.

## Runtime Shape

Kitty is a local-first single-user companion on Jacob's Mac:

- FastAPI gateway in `gateway/`
- Next.js UI in `gateway/kitty-chat/`
- LiteLLM proxy for model routing
- Runtime data under `data/`
- Logs under `logs/`

All prompt/search context reads should go through `gateway/memory_graph.py`.
Direct store imports remain acceptable for subsystem-owned writes and tests.

## Commands

```bash
bash scripts/preflight.sh
./kitty up
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
make ui-test && make ui-build
make agent-wrap
```

If a command fails, report the failure exactly. Do not round up to passing.

## Voice Glossary

- "the gateway" → `gateway/`
- "the chat thing" / "the UI" → `gateway/kitty-chat/`
- "the agent" → `gateway/agent.py`
- "the storage thing" → `gateway/storage_router.py` + `gateway/memory_graph.py`
- "the routing thing" → `gateway/llm_client.py`
- "the journal thing" → `gateway/journal.py` + `gateway/journal_store.py`
- "free workers" / "the free train" → `docs/FREE_WORKERS.md`
- "mission" → `docs/ACTIVE_MISSION.md`
- "roadmap" → `docs/ROADMAP.md`
- "execution state" → Builder's supported projections
- "Goose" → external chat tool, not part of Kitty runtime
- "Honcho" → `gateway/honcho.py`

## Cross-tool knowledge base

`~/kb` is the shared context layer for AI tools and cross-project knowledge.
Read `~/kb/INDEX.md` then `~/kb/NOW.md` when cross-project context matters and
check `~/kb/corrections/` before repeating failed approaches. Kitty-specific
truth remains in this repository.
