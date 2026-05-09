# Kitty — Personal AI Platform Design
_Spec date: 2026-05-09 · Revised after multi-model review (v4 — Antigravity design review)_

---

## Vision

Kitty is a personal AI platform that knows Jacob deeply, gets smarter every day, and is genuinely useful in his actual life — not just a generic chatbot. She handles research, repair, health, productivity, and vibe coding. She notices his patterns, calls them out gently, and proactively works to improve both her own performance and his daily experience. Everything runs locally or cheaply, with no important personal data sent to cloud services he doesn't control.

---

## Hardware Constraint (8GB Mac — read this first)

Jacob's Mac has 8GB unified memory. This changes the local model strategy:

| Always-on services | ~1.5GB |
|---|---|
| Open WebUI + Kitty Gateway | ~300MB |
| Mem0 (local memory graph) | ~400MB |
| ChromaDB | ~200MB |
| n8n | ~200MB |
| Remaining headroom | ~6.5GB |

A large local model (8B+) needs 5-6GB alone — it cannot run alongside everything else.

**Model strategy for 8GB:**
- **Default (non-sensitive):** DeepSeek Flash via cloud — $0.001/msg, fast, good quality
- **Agent tasks + structured output:** Hermes 4 via OpenRouter — current gen, hybrid reasoning, superior JSON schema adherence. No RAM cost — runs in cloud. Cheap per call.
- **Sensitive/private queries (medical, financial):** Qwen 2.5 4B via Ollama (local, ~2.5GB) — loaded on demand, unloaded after. Never leaves Mac.
- **Complex reasoning:** Claude Sonnet — reserved for synthesis, code review, complex multi-step.
- **Rule:** Never load a local model unless the query is explicitly sensitive. Cloud is cheap enough for everything else.

**On Hermes Agent (the platform, not the model):**
Hermes Agent is a separate application by Nous Research — a self-improving agent platform with 40+ built-in tools, cross-session memory, cron scheduling, and multi-channel access (Telegram, WhatsApp, Discord). It uses Hermes models internally. Worth evaluating as a replacement for the Kitty Gateway + n8n combination — especially the multi-channel piece (talk to Kitty via Telegram on your phone instead of needing Open WebUI mobile). To be assessed before Phase 1 starts.

---

## The Stack

| Piece | Tool | Plain English |
|---|---|---|
| Face / Interface | Open WebUI | The app Jacob opens and talks to. Mobile-friendly, voice-ready, customizable with Kitty's name and personality. |
| Kitty's brainstem | Kitty Gateway (FastAPI, not Flask) | Custom Python service that sits between Open WebUI and everything else. Injects soul, pulls memory, routes domain, calls Honcho. FastAPI used (not Flask) — async by default, handles LLM streaming without blocking, native Pydantic integration. |
| Kitty's soul | SOUL.md → system prompt | Who she is — personality, values, communication style. Loaded by Kitty Gateway on every request. |
| Agent brain | Hermes 4 (via OpenRouter, cloud) | Current gen. Hybrid reasoning, best-in-class JSON schema adherence. Used for agent tasks, routing decisions, structured extraction. No local RAM cost. |
| Private local brain | Qwen 2.5 4B-Instruct (Ollama, local, ~2.5GB) | On-demand only for medical/financial queries. Must use -Instruct variant — base model won't follow medical instructions reliably. Never leaves Mac. Unloaded from RAM after use. |
| Cheap fast brain | DeepSeek Flash (cloud) | Default for non-sensitive queries. ~$0.001/msg. |
| Smart brain | Claude Sonnet (API) | Complex reasoning, synthesis, code review. Reserved. |
| Model routing | LiteLLM | Picks the right model, tracks cost, enforces spend cap, falls back automatically. |
| Long-term memory | Mem0 (self-hosted, SQLite backend) | Replaces Mem0. Mem0 requires Neo4j/FalkorDB via Docker — too heavy for 8GB Mac (600-800MB before Kitty answers a message). Mem0 self-hosted uses SQLite, runs in-process, ~100MB. Same fact extraction and user memory. Migrate to Mem0 later if graph traversal is actually needed. |
| Knowledge base | ChromaDB + LlamaIndex | Stores everything Kitty knows — docs, PDFs, session logs. LlamaIndex reads files in; ChromaDB stores and searches them. |
| Psychology layer | Honcho (already built) | Watches every conversation for behavioral patterns. Feeds Mem0's inference namespace. Reports weekly. |
| Automation | n8n (self-hosted) | Runs scheduled tasks: morning brief, news digest, weekly pattern mirror. Sends push notifications via Pushover/NTFY to Jacob's phone. |
| Voice input | faster-whisper (already built) | Wrapped in a FastAPI app exposing OpenAI-compatible `/v1/audio/transcriptions`. Open WebUI plugs in natively. |
| Voice output | Kokoro TTS (local) | Wrapped in a FastAPI app exposing OpenAI-compatible `/v1/audio/speech`. Open WebUI plugs in natively. On-demand only. |
| Document parser | LlamaIndex + PyMuPDF + pdfplumber | PyMuPDF is the primary free parser. pdfplumber is the secondary (handles complex tables better). Both free, no cost per page. LlamaIndex supports both. |
| Complex doc parser | LlamaParse (optional, $0.003/page) | Only used for image-heavy documents: schematics, circuit boards, scanned records. Never for regular PDFs. |
| Image/schematic analysis | Claude Sonnet vision | Describes circuit boards and schematics in detail. Combined with OCR. Online image search augments results. |
| Coding guidance | Claude Code (already have it) | Jacob's vibe coding tool. Kitty generates a PLAN.md artifact; Jacob runs `claude "implement PLAN.md"` manually. |
| Backup | restic (nightly, dual target) | Encrypts and backs up to external drive (primary) AND Backblaze B2 cloud bucket (secondary, ~$0.005/GB/month). Both targets protect against simultaneous Mac + drive failure. |
| Remote access | Tailscale (free) | Zero-trust VPN. Jacob accesses Kitty from phone at `http://kitty-mac:3000` without exposing anything to the internet. |

---

## Architecture

```
Jacob (phone or Mac)
      ↓  [Tailscale — secure, no port forwarding]
  Open WebUI  (port 3000)
      ↓  [OpenAI-compatible API call]
  Kitty Gateway  (port 8000, thin Flask app — Kitty's real brain)
  ├── Load SOUL.md → build system prompt
  ├── Classify domain → pick 1-2 context modes
  ├── Pull facts from Mem0  [Jacob stated: "owns 2010 Honda"]
  ├── Pull patterns from Mem0  [Honcho inferred: "in research loop"]
  ├── Pull relevant docs from ChromaDB
  └── Call Honcho to log this conversation's signal
      ↓
  LiteLLM  (model router)
  ├── Sensitive query → Hermes 3 3B (Ollama, local, on-demand)
  ├── Normal query → DeepSeek Flash (cloud, $0.001)
  └── Complex query → Claude Sonnet (API, reserved)
      ↓
  Response → back through Kitty Gateway → Open WebUI → Jacob

Voice path (parallel):
  Jacob speaks → faster-whisper FastAPI → transcript → Kitty Gateway
  Kitty Gateway response → Kokoro TTS FastAPI → audio → Jacob hears Kitty

Background (n8n, no Jacob needed):
  7am daily   → Kitty Gateway generates brief → n8n pushes to Open WebUI chat + Pushover notification
  Daily        → RSS news digest → summarized → appended to brief
  Weekly       → Honcho pattern mirror → n8n pushes gentle observation to Jacob
  Nightly      → restic backup → all data dirs → external drive
```

---

## Engineering Contracts (lock before building)

Before any service writes data, the schemas live in `/contracts/` as Pydantic models. Every service imports from there — nothing hardcodes its own schema.

```
contracts/
  memory_event.py      # fact or pattern written to Mem0
  knowledge_chunk.py   # document chunk written to ChromaDB
  honcho_signal.py     # psychological signal from a conversation
  brief_item.py        # one item in the morning brief
  routing_decision.py  # what model was chosen and why
```

The `Router` class has a pure function signature so routing logic is unit-testable:
```python
def route(intent: str, context: RoutingContext) -> RoutingDecision:
    ...
```
Spend cap + auto-downgrade is a decorator on top — not buried in routing logic.

---

## Prompt Versioning

All system prompts live in `/prompts/` with version tags. Loaded at runtime by Kitty Gateway. Can be rolled back independently of code.

```
prompts/
  soul_v1.md           # Kitty's core personality
  repair_v1.md         # Repair & Technical domain
  health_v1.md         # Health & Medical domain
  research_v1.md       # Research domain
  code_v1.md           # Code & Build domain
```

---

## Observability (lightweight, 6 lines per turn)

Every interaction logs a structured JSON trace with a correlation ID:
```json
{
  "correlation_id": "abc123",
  "user_request": "...",
  "domain_classified": "repair",
  "memory_fetched_ms": 45,
  "llm_call_ms": 820,
  "model_used": "hermes4-openrouter",
  "response_tokens": 312
}
```
Tail-sampled to a rotating log file. Used for debugging latency spikes, weird recall, and the weekly self-optimization loop.

**Weekly self-optimization (`optimize_loop.py`):** Aggregates 4 metrics (usefulness, latency, cost, correction rate), adjusts routing thresholds, proposes prompt tweaks. Manual approval before any change applies.

---

## Graceful Degradation

If Mem0 or ChromaDB is unavailable, Kitty Gateway falls back to an ephemeral in-memory store for that session only — with a visible warning. Jacob gets a degraded but working Kitty, not a crash.

Session closure hook: when a chat session ends, short-term memory moves to Mem0 (long-term) and transient ChromaDB chunks are pruned. Prevents unbounded database growth.

---

## Phase Gate Script

One script verifies each phase is actually done:

```bash
./gate-check.sh <phase-number>
# Runs test command, checks latency/cost targets, prints rollback command if failed.
```

---

## Data Model (privacy labels on everything)

Every piece of memory and every document carries these fields before it's stored:

```
source:          where it came from (claude_export, apple_health, jacob_statement, honcho_inferred)
sensitivity:     low | medium | high | medical | financial
allowed_models:  [local_only] or [cloud_ok] or [any]
retention_days:  how long to keep (or -1 for permanent)
created_at:      timestamp
confidence:      0.0–1.0 (1.0 = Jacob confirmed, 0.5 = inferred, 0.1 = tentative)
human_confirmed: true/false
namespace:       facts | patterns | knowledge | brief
```

**Strict separation in Mem0:**
- `facts` namespace — things Jacob stated directly. "Jacob owns a 2010 Honda Civic." Confidence 1.0 when confirmed.
- `patterns` namespace — things Honcho inferred. "Jacob tends to research heavily before acting." Confidence 0.5–0.8, never presented as fact.

Medical, financial, and psychological data: `sensitivity: high`, `allowed_models: [local_only]`. These never leave the Mac.

---

## Domain Context Modes (live from Phase 2)

Five modes active from day one of Kitty Gateway. Classification uses a cheap LLM call (DeepSeek Flash or Hermes 3B). Multi-domain allowed — a question can activate two modes at once.

| Mode | Activates when | What changes | Fallback |
|---|---|---|---|
| Soul / default | General, personal, life | Full Kitty personality, psychological context from Mem0 | Always available |
| Repair & Technical | Car, electronics, schematics, "how do I fix" | Pulls vehicle history, service manuals, repair context | Soul if no repair docs found |
| Health & Medical | Symptoms, blood results, meds, fitness | Pulls medical profile — **local model only**, framed as research + questions for doctor | Soul |
| Research | "Look this up," deep dives | Firecrawl pipeline, cites all sources, never synthesizes without grounding | Soul |
| Code & Build | "I want to build," vibe coding | Architect mode — generates PLAN.md, checks complexity, no code before plan | Soul |

Low-confidence classification → default to Soul mode.

---

## Onboarding Pipeline

Runs once. Idempotent — safe to rerun without creating duplicate memories. Three phases.

### Phase 1 — Guided Interview (Kitty asks Jacob)

Conversational, one domain per sitting. No forms. Jacob answers in his own words. All answers stored in Mem0 (`facts` namespace, `human_confirmed: true`) and ChromaDB.

**Domain 1 — Identity & Values**
- Who are you, what are you trying to build in your life?
- What does "getting your life back on track" actually mean to you?
- What are your non-negotiables?

**Domain 2 — Health & Medical** _(local model only, sensitivity: medical)_
- Current conditions, medications, supplements
- Blood test results (upload PDF or paste numbers)
- Sleep patterns, energy levels throughout the day
- Goals (lose weight, gain energy, fix specific issues)
- What you've already tried

**Domain 3 — Fitness**
- Current level, what you do, what you hate
- Goals, limitations, injuries, equipment available

**Domain 4 — Automotive & Repair**
- Vehicles owned (make, model, year, known issues)
- Skill level, tools available, repair history

**Domain 5 — Productivity & Work**
- Work style (hyperfocus, scattered, deadline-driven)
- Biggest time wasters, what a good day looks like vs bad
- Current projects and goals

**Domain 6 — Finances** _(local model only, sensitivity: financial)_
- Goals (not required to share numbers, just direction)
- Canadian-specific context (province, situation)
- Passive income ideas already considered

**Domain 7 — Learning & Interests**
- Topics deep into right now, things wanting to learn
- How he best learns (video, doing, reading, talking through)

**Domain 8 — Relationships & Social**
- Who matters, where more connection wanted
- Anything Kitty should help maintain

### Phase 2 — File Ingestion

LlamaIndex ingestion pipeline. All sources processed into ChromaDB with full data model labels. Idempotent — checks hash before re-ingesting.

| Source | Parser | Sensitivity |
|---|---|---|
| Kitty session logs (`data/sessions/`) | Plain text | low |
| STANDUP + DECISIONS docs | Plain text | low |
| SOUL.md content | Plain text | low |
| Claude.ai export (JSON) | Custom script | low |
| ChatGPT export (JSON) | Custom script | low |
| Apple Health export | **Dedicated Python parser** (not LlamaIndex — see note) | medical |
| Google Calendar (.ics) | ical parser | medium |
| OBD logs | Existing OBD parser | low |
| Text-based PDFs | PyMuPDF (free) | varies |
| Image-heavy PDFs / schematics | LlamaParse ($0.003/page, optional) | varies |

**Apple Health note:** The export is a single XML file that can be 500MB+. Do not feed it through LlamaIndex. A dedicated Python script parses the XML, extracts only: sleep, resting heart rate, weight, steps, HRV, workouts — aggregates into weekly summaries — outputs clean JSON. That JSON gets ingested into ChromaDB. Raw XML through an LLM pipeline burns tokens and produces garbage.

### Phase 3 — Honcho Seeding

After phases 1 and 2, Honcho replays the historical data using **Hermes 3 3B (local, free)** — not Claude Sonnet. This keeps the backfill cost at $0. It takes longer (hours, not minutes) but runs in the background. Jacob's psychological profile is built before a single live conversation happens.

---

## Morning Brief

n8n fires at 7am:
1. Calls Kitty Gateway → generates brief based on calendar, Mem0 patterns, open projects
2. Pulls news digest (RSS, no scraping): tech/AI, Canadian news, Jacob's domain topics
3. Creates new Open WebUI chat session via API
4. Pushes Pushover/NTFY notification to Jacob's phone with a link to the chat

Brief format: one casual opener, 3-5 news items (one sentence + source each), one open project reminder, one pattern observation if Honcho flagged something. Never more than a 90-second read.

---

## Vibe Coding Handoff

Kitty generates a `PLAN.md` or `IMPLEMENTATION.md` artifact in the workspace. Jacob opens terminal and runs:
```
claude "implement the steps in PLAN.md"
```
Manual handoff only. No automated Claude Code triggering — interactive prompts and shell complexity aren't worth the friction early on.

---

## Lightweight Eval Smoke Suite (keep, don't delete)

Heavy eval infrastructure archived. Small smoke suite kept with 5 gates. Run after any significant change.

| Gate | Test command | Pass condition |
|---|---|---|
| Chat works | Ask "who am I?" | Responds in character with Jacob's name |
| Model routing | Ask a simple question | Routes to DeepSeek Flash, not Claude |
| Memory recall | State a new fact, close chat, open new chat, ask about it | Kitty remembers |
| Document retrieval | Ask about a specific detail from an ingested doc | Returns correct answer with source |
| Morning brief | Trigger brief manually | Generates non-empty brief, pushes notification |

---

## What Gets Kept From Existing Kitty

| Component | Location | Status |
|---|---|---|
| Honcho | `src/space_kitty/honcho.py` | Keep — core psychology layer |
| faster-whisper | `src/api/transcription_service.py` | Keep — wrap in FastAPI with OpenAI-compatible endpoint |
| Morning brief | `src/core/morning_brief.py` | Keep — wire to n8n |
| Firecrawl pipeline | `src/tools/research_pipeline.py` | Keep — research domain tool |
| ChromaDB | `src/memory/chroma_manager.py` | Keep — reduce to single interface |
| OBD parser | `src/tools/obd_parser.py` | Keep — repair domain tool |
| Domain classification | `src/core/query_router.py` (simplified) | Keep classification logic, remove model routing |
| Semantic cache + token tracking | Extract from `scripts/kitty_builder.py` | Keep these two things only |
| Skill engine + command engine | `src/core/skill_engine.py`, `command_engine.py` | Keep |

---

## What Gets Cut / Archived

| Component | Action | Why |
|---|---|---|
| Custom model routing (4+ files) | Archive | Replaced by LiteLLM |
| 6 of 8 memory files | Archive | Replaced by Mem0 + single ChromaDB interface |
| Heavy eval infrastructure | Archive | Replaced by 5-gate smoke suite |
| Swarm executor | Archive | Premature |
| Observability/metrics dashboard | Archive | Not needed for personal use |
| Duplicate orchestrators | Archive all but CoreOrchestrator | Consolidate |
| garage-ui | Freeze (don't delete) | Replaced by Open WebUI as primary interface |
| KittyBuilder (most of it) | Archive | Claude Code replaces it |
| Zep CE | Never install | Deprecated — replaced by Mem0 |

---

## Build Order

Each phase ships something Jacob can actually use and has a verification gate.

**Phase 1 — Open WebUI + LiteLLM + models**
Install Open WebUI and LiteLLM simultaneously (they need each other from day one). Wire Claude Sonnet and one Ollama model (Hermes 3 3B or Qwen 2.5 4B). Jacob can have a basic conversation.
_Gate: Open WebUI loads. Sending a message gets a Claude response._

**Phase 2 — Kitty Gateway + domain modes + soul**
Build the thin Flask Gateway. Load SOUL.md as system prompt. Wire 5 domain modes with basic classification. Open WebUI points to Gateway instead of LiteLLM directly.
_Gate: Ask "who am I?" → responds as Kitty, not generic AI. Ask about a car → domain switches to Repair mode._

**Phase 3 — Mem0 memory**
Install Mem0 locally. Wire into Gateway. Every conversation starts populating Jacob's memory graph. Separate facts and patterns namespaces from day one with privacy labels.
_Gate: Tell Kitty a new fact. Close chat. Open new chat. Ask about it. She remembers._

**Phase 4 — ChromaDB + small ingestion test**
Set up LlamaIndex ingestion pipeline. Run it on a small test folder (5-10 docs) first. Verify retrieval works before ingesting everything.
_Gate: Upload one PDF. Ask a specific question about it. Kitty answers with a citation._

**Phase 5 — Onboarding: guided interview**
Build 8-domain interview inside Kitty. Jacob completes one domain per sitting. All answers flow into Mem0 + ChromaDB with privacy labels.
_Gate: Complete Domain 1. Ask Kitty "what do you know about me?" — she summarizes accurately._

**Phase 6 — Onboarding: file ingestion**
Run full ingestion pipeline: session logs, chat exports, Apple Health (dedicated parser), calendar, OBD logs, existing PDFs.
_Gate: Ask about a specific detail from a 3-month-old Claude conversation. Kitty finds it._

**Phase 7 — Morning brief + news via n8n**
Install n8n. Configure 7am brief. Wire RSS news sources. Wire Pushover/NTFY for phone notifications.
_Gate: Trigger brief manually. It generates and sends a push notification to phone._

**Phase 8 — Voice input + output**
Wrap faster-whisper in FastAPI (OpenAI-compatible endpoint). Add Kokoro TTS same way. Wire both into Open WebUI's audio settings.
_Gate: Speak a question. Kitty responds. Hear the response in Kitty's voice._

**Phase 9 — Document + schematic pipeline**
Full LlamaIndex ingestion for text PDFs (PyMuPDF). Vision pipeline for schematics (Claude Sonnet describes, OCR extracts, image search augments). LlamaParse for any doc that fails local parsing.
_Gate: Drop in a circuit board photo. Ask "what does this capacitor do?" — Kitty identifies it._

**Phase 10 — Honcho weekly mirror + seeding**
Run Honcho backfill on historical data using Hermes 3 3B locally (free, runs overnight). Wire n8n weekly trigger for pattern observation.
_Gate: Honcho produces one observation about a real pattern Jacob has shown._

**Phase 11 — Backup + security**
Enable FileVault if not already on. Set up nightly restic backup. Set up Tailscale for secure phone access.
_Gate: Simulate data loss scenario on a test folder. Verify restore works._

---

## Migration Path (current Kitty → new Kitty)

Current Kitty runs on port 5001. Open WebUI runs on port 3000. They run side by side.

- Phases 1-3: New stack is being built. Current Kitty stays running on 5001.
- Phase 4-6: New stack is being fed data. Jacob can use either.
- Phase 7+: New stack is primary. Current Kitty on 5001 is kept as fallback but not the default.
- After Phase 11: Current Kitty is archived. Single stack remains.

No period without a working assistant.

---

## Tools Reference (plain English)

- **Open WebUI** — the chat interface. Free, self-hosted.
- **Kitty Gateway** — the custom Python service that IS Kitty's brain. Open WebUI talks to this.
- **Hermes 3 3B** — free AI model, runs locally via Ollama. Check `ollama.com/library/hermes3` for latest version (may be Hermes 4 by the time you read this).
- **Ollama** — the app that runs local models on your Mac.
- **LiteLLM** — one library that talks to all AI providers. Handles routing, cost tracking, spend caps, fallbacks.
- **Mem0** — replaces Zep CE (which is deprecated). Local-first graph memory. Stores facts and inferred patterns separately.
- **ChromaDB** — the document/knowledge database. Already in Kitty.
- **LlamaIndex** — reads files into ChromaDB. The ingestion pipeline.
- **LlamaParse** — optional, $0.003/page. Only for image-heavy docs.
- **Honcho** — psychological pattern extraction. Already built.
- **n8n** — visual automation. Runs morning brief, news, weekly mirror on schedule.
- **faster-whisper** — speech-to-text. Already built. Wrapped in FastAPI.
- **Kokoro TTS** — text-to-speech. Free, local. Wrapped in FastAPI.
- **Firecrawl** — web research scraper. Already built.
- **Tailscale** — free VPN. Secure phone access without exposing anything to internet.
- **restic** — backup tool. Nightly encrypted backup to external drive.
- **Pushover / NTFY** — push notification to Jacob's phone. Used by n8n for morning brief.

---

## What This Is Not

- Not a commercial product. Personal use only.
- Not a replacement for doctors or lawyers. Medical/legal output is always framed as research and questions to ask, never diagnosis or advice.
- Not finished on day one. It ships something useful in Phase 1 and gets better with every phase.
- Not a system that re-ingests the same data twice. Idempotent pipelines throughout.
