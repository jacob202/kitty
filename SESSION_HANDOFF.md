# Session Handoff — 2026-05-09

## What was built this session (Phases 1–6 complete)

| Phase | Commit | What it does |
|---|---|---|
| 1 | f8bdf44 | LiteLLM proxy (port 8001) + Open WebUI (port 3000) + kitty-services venv |
| 2 | ef46c29 | Kitty Gateway FastAPI (port 8000) — soul injection, domain routing |
| 3 | 939c95f | Mem0 memory layer — ChromaDB + Ollama embeddings + DeepSeek extraction |
| 4 | f0b076d | ChromaDB knowledge base + LlamaIndex ingestion pipeline |
| 4b | 1ecd5cc | Doc-type-aware chunking (service_manual/book/health/session_log) + JSONL parser |
| 5 | 4daa8cd | Guided onboarding interview — 8 domains, facts → Mem0 + ChromaDB |
| 6 | 1e9fda5 | Full ingestion sweep — ChatGPT export + Claude.ai extractor + journal.db extractor |

**Test suite: 575 passing, 0 failures**
**ChromaDB: 1,580 chunks** (63 Claude Code sessions + 7 ChatGPT archives ingested)

---

## How to start all services

```bash
cd ~/Projects/kitty

# Terminal 1 — LiteLLM model router
bash kitty_gateway/start_litellm.sh

# Terminal 2 — Kitty Gateway (Kitty's brain)
set -a && source .env && set +a
venv/bin/uvicorn gateway.app:app --host 127.0.0.1 --port 8000

# Terminal 3 — Open WebUI (the chat interface)
bash kitty_gateway/start_openwebui.sh

# Optional Terminal 4 — MLX local model (for medical/financial queries)
bash kitty_gateway/start_mlx.sh
```

Open WebUI → Settings → Admin Panel → Connections → OpenAI API:
- URL: `http://localhost:8000/v1` (Gateway, not LiteLLM directly)
- Key: `kitty-local-key-change-me`

---

## First thing Jacob should do

Run the onboarding interview (makes Kitty actually know you):
```bash
python scripts/onboard.py --domain identity   # start with Domain 1
python scripts/onboard.py --status            # see progress
python scripts/onboard.py                     # resume all remaining domains
```

Ingest existing documents:
```bash
python scripts/ingest.py data/knowledge/test/   # test with sample doc
python scripts/ingest.py /path/to/your/pdfs/    # any folder of PDFs/txt/md
```

---

## Next phases (not yet built)

| Phase | Plan file | What it builds |
|---|---|---|
| **6** | `2026-05-09-kitty-phase-6-ingestion.md` | ✅ DONE — ChatGPT (1538 chunks), Claude Code sessions, Claude.ai extractor ready |
| **7** | needs writing | Morning brief + news via n8n + Pushover phone notification |
| **8** | needs writing | Voice input (faster-whisper already built) + Kokoro TTS — wire to Gateway |
| **9** | needs writing | PDF pipeline + schematic vision (LlamaParse for image-heavy docs) |
| **10** | needs writing | Honcho weekly pattern mirror + historical seeding |
| **11** | needs writing | restic backup (external drive + Backblaze B2) + Tailscale mobile access |

**Start next session from Phase 7.**

### Claude.ai export — pending ingest
When Claude.ai export zip is accessible, run:
```bash
# Unzip export into:  data/imports/claude/
# (needs: conversations.json, memories.json, projects/, design_chats/)
python scripts/ingest_phase6.py   # will pick it up automatically
```

---

## Key file locations

| Thing | Path |
|---|---|
| LiteLLM config | `kitty_gateway/litellm_config.yaml` |
| Soul prompt | `prompts/soul_v1.md` |
| Domain prompts | `prompts/repair_v1.md`, `health_v1.md`, `research_v1.md`, `code_v1.md` |
| Gateway app | `gateway/app.py` |
| Memory module | `gateway/memory.py` |
| Knowledge module | `gateway/knowledge.py` |
| Onboarding module | `gateway/onboarding.py` |
| Onboarding CLI | `scripts/onboard.py` |
| Ingestion CLI | `scripts/ingest.py` |
| Gate check | `scripts/setup/gate-check.sh 1` |
| Onboarding state | `data/onboarding_state.json` |
| Mem0 store | `data/mem0/` |
| Knowledge DB | `data/knowledge_db/` |

---

## Known issues / decisions made

- `ANTHROPIC_API_KEY` in `.env` is invalid — Claude routes through OpenRouter instead (`openrouter/anthropic/claude-sonnet-4-6`)
- Gemini Flash fallback removed from litellm_config — GEMINI_API_KEY was quota-limited causing flaky routing
- Private local model = MLX Qwen3.5-4B-4bit (not Ollama) — already downloaded at `~/.cache/huggingface/hub/`
- LiteLLM health endpoint requires auth header: `Authorization: Bearer kitty-local-key-change-me`
- Open WebUI v0.9.4 — Connections setting is under Admin Panel → Settings → Connections (not regular settings)

---

## Next session prompt

"Continue building Kitty from Phase 6. Read SESSION_HANDOFF.md and the master plan at docs/superpowers/plans/2026-05-09-kitty-master-plan.md. Phases 1–5 are complete (571 tests passing). Start Phase 6: full ingestion sweep of the 25 Claude Code session transcripts at ~/.claude/projects/-Users-jacobbrizinski-Projects-kitty/*.jsonl and any other existing data sources. Use subagents where warranted."
