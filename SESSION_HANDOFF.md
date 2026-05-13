# Session handoff — compact-safe

_Use this after “pre-compact sweep”: update once, compact chat, reopen with `SESSION_HANDOFF.md` in context. Canon: **`docs/CURSOR_COMPACT.md`** + **`.cursor/rules/cursor-compact.mdc`**. Repo-wide reminder in **`AGENTS.md`**._

## Product / UX

- **Primary chat UI**: Open WebUI (see `docs/ARCHITECTURE.md`, port 3000 stack).
- **`garage-ui/`**: Canonical path again — **repo root `garage-ui/`** (Next.js reference/custom UI). Not required for documented stack; handy for components, hooks, Vitest — do not treat as prod unless wired.
- **`config/specialists`**: **Not using specialists now** — old specialist snapshots were dropped from the tree (`config/legacy_specialists` removed). Recover from git with `git checkout HEAD -- config/specialists` only if you resurrect that framework.

## Runtime layout (truth for agents)

- **App code**: `gateway/` (FastAPI). Prompt assembly → `gateway/context_builder.get_system_prompt()`; ingestion/search → `gateway/knowledge.py`.
- **`src/`**: Often absent this checkout; treat as archived / docs-only references.

## Tests & eval tooling

- **Smoke eval**: `gateway/smoke_eval.py` + `gateway/eval_domain.py`; artifacts default to `DATA_DIR/eval_artifacts/` (usually `data/eval_artifacts/`).
- **Regression compare**: `scripts/compare_eval_runs.py`.
- **Tests**: `tests/test_context_injection.py`, `tests/test_eval_recall_memory.py`, `tests/test_eval_recall_knowledge.py`, `tests/test_smoke_eval.py`.
- **Fixtures**: `tests/fixtures/evals/` (optional historical payloads).

Verify:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```

## Knowledge base — verify; do not assume

Check live state before bulk re-ingest:

```bash
./venv/bin/python scripts/kitty_manage.py status
```

If index is empty and you need KB: `./venv/bin/python scripts/kitty_manage.py ingest <your-root>` (paths per your setup).

## LLM fallbacks (`gateway/llm_client.py`)

After LiteLLM failure → **AgentRouter → OpenRouter → Gemini → NVIDIA** (`tests/test_llm_routing.py`).

**Built-in AgentRouter model slugs** (cheap-first; env overrides beat these):

| Tier | When | Built-in slug |
|------|------|----------------|
| `kitty-default` / `kitty-fallback-or` tail | Chat, ingest, librarian, vision captions | **`gpt-5.4-mini`** |
| `kitty-agent` / `kitty-parts` | Coding / toolchain | **`gpt-5.1-codex-mini`** (upgrade: `KITTY_AGENTROUTER_CODING_MODEL=gpt-5.3-codex`) |
| `kitty-smart` | Heavier synthesis | **`gpt-5.5`** (not down-tiered by `KITTY_AGENTROUTER_CHAT_MODEL` alone) |

**AgentRouter direct:** Prefer `AGENTROUTER_API_KEY` or `AGENT_ROUTER_TOKEN`. Base URL → **`.../v1`**. Overrides: `KITTY_AGENTROUTER_MODEL_DEFAULT|AGENT|SMART|PARTS`, or `KITTY_AGENTROUTER_CHAT_MODEL` → `AGENTROUTER_MODEL` for default/chat-only. **`Accept: application/json`**, **`User-Agent`** (Chrome-like default), **`KITTY_AGENTROUTER_EXTRA_HEADERS_JSON`**, **`KITTY_AGENTROUTER_NO_ALT_UA_RETRY`**. On **`unauthorized client`** fingerprint 401 the client does **one UA retry**; if still 401 check response body plus Discord/support linked in payload—may need vendor-approved headers or routing via LiteLLM instead of raw Python HTTPS. Other failures: logs include HTTP status + short response body (401 can also mean bad key / duplicate `.env` last-wins / model env corrupted with pasted tokens).

## Journal

Optional **session_id** on synthesize/delete paths for session-scoped journal behavior (`gateway/journal.py`, `gateway/app.py`).

---

## Cursor compact

Detailed steps live in **`docs/CURSOR_COMPACT.md`** (update this handoff → compact → @ handoff next thread).

---

## Prometheus (cloned 2026-05-13)

- **Location**: `Prometheus/` (cloned from https://github.com/EuniAI/Prometheus)
- **Status**: Running on `http://localhost:9002` (API docs at `/docs`)
- **Containers**: `prometheus` (FastAPI), `prometheus_neo4j_container`, `prometheus_postgres_container`
- **Neo4j memory**: Reduced from 6-12GB to 1GB in `docker-compose.yml`
- **API keys**: Copied from kitty `.env` (Anthropic, Gemini, OpenAI, Tavily)
- **JWT**: Generated and set in `Prometheus/.env`
- **Athena**: Disabled (commented out `PROMETHEUS_ATHENA_BASE_URL` — private service)
- **Start**: `cd Prometheus && docker compose up -d`
- **Stop**: `cd Prometheus && docker compose down`

## Kitty fixes (2026-05-13)

- **Fixed `.env` line 18**: `AGENTROUTER_MODEL` value had unquoted space → wrapped in quotes
- **Server**: Was stopped, `.env` fix applied but not restarted (user aborted)
