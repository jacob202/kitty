# Kitty Personal AI Platform — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Kitty — a personal AI platform that knows Jacob deeply, runs cheaply, and gets smarter every conversation.

**Architecture:** Open WebUI (face) → Kitty Gateway (brainstem) → LiteLLM (model router) → DeepSeek Flash / Hermes 4 / Claude Sonnet / Qwen local. Graphiti for long-term memory. ChromaDB for knowledge. Honcho for psychological patterns. n8n for automation.

**Spec:** `docs/superpowers/specs/2026-05-09-kitty-personal-ai-platform-design.md`

---

## Phase Index

Each phase has its own plan file. Every plan is self-contained — a subagent or fresh session can execute any single phase with zero prior context.

| Phase | Plan file | What it ships | Gate |
|---|---|---|---|
| **1** | `2026-05-09-kitty-phase-1-infra.md` | Open WebUI + LiteLLM + models working | Chat with Kitty on Day 1 |
| **2** | `2026-05-09-kitty-phase-2-gateway.md` | Kitty Gateway + 5 domain modes + soul prompt | Kitty responds in character, domain switches work |
| **3** | `2026-05-09-kitty-phase-3-memory.md` | Graphiti local memory, facts vs patterns separated | Tell Kitty a fact, close chat, reopen — she remembers |
| **4** | `2026-05-09-kitty-phase-4-knowledge.md` | ChromaDB + LlamaIndex ingestion, test folder first | Upload a PDF, ask a question, get a cited answer |
| **5** | `2026-05-09-kitty-phase-5-onboarding.md` | 8-domain guided interview, answers into Graphiti + ChromaDB | Complete Domain 1, ask "what do you know about me?" |
| **6** | `2026-05-09-kitty-phase-6-ingestion.md` | Full file ingestion: session logs, chat exports, Apple Health, calendar | Ask about a 3-month-old decision — Kitty finds it |
| **7** | `2026-05-09-kitty-phase-7-brief.md` | Morning brief + news via n8n + Pushover phone notification | Trigger brief manually — notification arrives on phone |
| **8** | `2026-05-09-kitty-phase-8-voice.md` | Voice input (faster-whisper) + voice output (Kokoro TTS) | Speak a question — hear Kitty's response |
| **9** | `2026-05-09-kitty-phase-9-documents.md` | PDF pipeline + schematic vision pipeline | Drop in a circuit board photo — Kitty describes every component |
| **10** | `2026-05-09-kitty-phase-10-honcho.md` | Honcho weekly mirror + historical seeding via Hermes local | Honcho produces one real observation about Jacob's patterns |
| **11** | `2026-05-09-kitty-phase-11-backup.md` | Nightly restic backup + FileVault check + Tailscale mobile access | Simulate restore — works. Access Open WebUI from phone. |

---

## Environment (shared across all phases)

**Project root:** `/Users/jacobbrizinski/Projects/kitty`
**Python:** 3.12.13 at `/usr/local/bin/python3`
**Project venv:** `/Users/jacobbrizinski/Projects/kitty/venv`
**Services venv:** `~/kitty-services/venv` (created in Phase 1 — for open-webui and litellm)
**Ollama:** `/usr/local/bin/ollama` (already installed)
**Available local models:** `qwen2.5-coder:7b` (4.7GB), `nomic-embed-text` (274MB)

**API keys already set in `.env`:**
- `OPENROUTER_API_KEY` ✓
- `ANTHROPIC_API_KEY` ✓
- `DEEPSEEK_API_KEY` ✓
- `GEMINI_API_KEY` ✓
- `GROQ_API_KEY` ✓
- `HONCHO_API_KEY` ✓

**Ports:**
- Open WebUI: 3000
- LiteLLM proxy: 8001
- Kitty Gateway: 8000
- Current Kitty (legacy, keep running): 5001

---

## Directory structure created across all phases

```
/Users/jacobbrizinski/Projects/kitty/
├── contracts/              # Pydantic schemas — created Phase 1
│   ├── routing_decision.py
│   ├── memory_event.py     # Phase 3
│   ├── knowledge_chunk.py  # Phase 4
│   ├── honcho_signal.py    # Phase 10
│   └── brief_item.py       # Phase 7
├── prompts/                # Versioned system prompts — created Phase 2
│   ├── soul_v1.md
│   ├── repair_v1.md
│   ├── health_v1.md
│   ├── research_v1.md
│   └── code_v1.md
├── gateway/                # Kitty Gateway — created Phase 2
│   ├── app.py
│   ├── router.py
│   ├── memory.py           # Phase 3
│   └── knowledge.py        # Phase 4
├── kitty_gateway/          # Config files
│   └── litellm_config.yaml # Phase 1
├── scripts/setup/
│   ├── install_phase1.sh
│   └── gate-check.sh       # Phase 1, extended each phase
└── docs/superpowers/plans/ # This directory
```

---

## Gate check commands (quick reference)

```bash
./scripts/setup/gate-check.sh 1   # Infrastructure
./scripts/setup/gate-check.sh 2   # Gateway + domain modes
./scripts/setup/gate-check.sh 3   # Memory
./scripts/setup/gate-check.sh 4   # Knowledge base
./scripts/setup/gate-check.sh 5   # Onboarding
```

---

## Handoff format for session limits

If a session ends mid-phase, the next session needs:
1. The spec: `docs/superpowers/specs/2026-05-09-kitty-personal-ai-platform-design.md`
2. This master plan: `docs/superpowers/plans/2026-05-09-kitty-master-plan.md`
3. The current phase plan file (check which tasks are checked off)
4. Run `git log --oneline -5` to see what was last committed

The next session starts from the first unchecked task in the current phase plan.
