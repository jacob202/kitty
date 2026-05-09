# Kitty — Personal AI Platform Design
_Spec date: 2026-05-09_

---

## Vision

Kitty is a personal AI platform that knows Jacob deeply, gets smarter every day, and is genuinely useful in his actual life — not just a generic chatbot. She handles research, repair, health, productivity, and vibe coding. She notices his patterns, calls them out gently, and proactively works to improve both her own performance and his daily experience. Everything runs locally or cheaply, with no important personal data sent to cloud services he doesn't control.

---

## The Stack (what each piece is and does)

| Piece | Tool | Plain English |
|---|---|---|
| Face / Interface | Open WebUI | The app Jacob opens and talks to. Replaces garage-ui. Mobile-friendly, voice-ready, customizable. |
| Kitty's soul | Custom system prompt + SOUL.md | Who she is — personality, values, communication style. Lives inside Open WebUI. |
| Free agent brain | Hermes 3 (via Ollama, local) | Handles routine agent tasks for free. Never leaves Jacob's Mac. |
| Smart brain | Claude Sonnet (via API) | For complex reasoning, synthesis, code review. Used only when needed. |
| Cheap fast brain | DeepSeek Flash / Gemini Flash | For simple fast calls. Under $0.001 per message. |
| Model routing | LiteLLM | Automatically picks the right model. Falls back if one is down. Tracks cost. Replaces all custom routing code. |
| Long-term memory | Zep (self-hosted) | Remembers facts about Jacob across all conversations. Runs locally — medical/personal data stays private. |
| Knowledge base | ChromaDB + LlamaIndex | Database of everything Jacob has given Kitty — docs, PDFs, session logs, schematics. LlamaIndex reads the files in; ChromaDB stores and searches them. |
| Psychology layer | Honcho (already built) | Watches every conversation for patterns. Feeds Zep with psychological signal. Reports weekly. |
| Automation | n8n (self-hosted) | Runs scheduled tasks without Jacob. Morning brief, news digest, weekly pattern mirror. |
| Voice input | faster-whisper (already built) | Jacob talks, Kitty transcribes. Already works. |
| Voice output | Kokoro TTS (local, free) | Kitty talks back. Runs on Mac. No cloud needed. |
| Document parser | LlamaIndex + LlamaParse | Reads PDFs, schematics, medical docs, websites into ChromaDB. LlamaParse ($0.003/page) used for complex image-heavy docs. |
| Image/schematic analysis | Claude Sonnet vision | Describes circuit boards, schematics in detail. Combined with OCR for component labels. |
| Coding guidance | Claude Code (already have it) | Jacob's vibe coding tool. Kitty acts as architect/guide before Claude Code writes anything. |

---

## Architecture (how it all connects)

```
Jacob talks or types (voice or text)
            ↓
      Open WebUI
      (Kitty's face — personalized, themed, his name)
            ↓
   Open WebUI Pipeline (custom Python layer)
   ├── Injects Kitty's soul / system prompt
   ├── Pulls relevant memory from Zep
   ├── Pulls relevant knowledge from ChromaDB
   ├── Routes to domain context (repair / medical / fitness / code / research)
   └── Calls Honcho to log psychological signal
            ↓
        LiteLLM
   ├── Simple tasks → Hermes 3 (local, free)
   ├── Complex tasks → Claude Sonnet
   └── Quick cheap tasks → DeepSeek Flash
            ↓
      Response back to Jacob

Background (always running, no Jacob needed):
   n8n scheduler
   ├── 7am daily → Morning brief fires → appears in Open WebUI + phone
   ├── Daily → News digest from 5+ sources → summarized, no ads
   └── Weekly → Honcho pattern mirror → "hey, noticed something"
```

---

## Onboarding Pipeline

Onboarding runs once. Two phases — active interview first, then file ingestion. Honcho gets seeded from both.

### Phase 1 — Guided Interview (Kitty asks Jacob questions)

Kitty conducts a structured interview across 8 domains. One domain per session, conversational tone, no forms. Jacob answers in his own words. All answers go into Zep and ChromaDB.

**Domain 1 — Identity & Values**
- Who are you, what do you do, what are you trying to build in your life?
- What does "getting your life back on track" actually mean to you?
- What are your non-negotiables?

**Domain 2 — Health & Medical**
- Current conditions, medications, supplements
- Blood test results (upload PDF or paste numbers)
- Sleep patterns, energy levels throughout the day
- Goals (lose weight, gain energy, fix specific issues)
- What you've already tried

**Domain 3 — Fitness**
- Current level, what you do, what you hate
- Goals, limitations, injuries
- Equipment available

**Domain 4 — Automotive & Repair**
- Vehicles owned (make, model, year, known issues)
- Skill level (total beginner to experienced)
- Tools available
- Repair history or ongoing issues

**Domain 5 — Productivity & Work**
- Work style (hyperfocus, scattered, deadline-driven)
- Biggest time wasters
- What a good productive day looks like vs. a bad one
- Current projects and goals

**Domain 6 — Finances**
- Goals (not required to share numbers, just direction)
- Current approach to money
- Canadian-specific context (province, tax situation if relevant)
- Passive income ideas he's already considered

**Domain 7 — Learning & Interests**
- Topics he's deep into right now
- Things he wants to learn
- How he best learns (video, doing, reading, talking through)
- Skills he wants to build

**Domain 8 — Relationships & Social**
- Who matters in his life
- Where he wants more connection
- Anything he wants Kitty to help him maintain (e.g., "remind me to check in with X")

### Phase 2 — File Ingestion

Automated pipeline processes these sources and loads them into ChromaDB:

| Source | How to get it | What Kitty learns |
|---|---|---|
| Kitty session logs | Already in `data/sessions/` | Months of Jacob's thinking, decisions, patterns |
| STANDUP docs | Already in `docs/` | Project history and priorities |
| DECISIONS.md | Already in `docs/` | Every major decision and why |
| SOUL.md content | Already in memory files | Values, psychology, communication style |
| Claude.ai export | Settings → Export data | Full conversation history |
| ChatGPT export | Settings → Export data | Full conversation history |
| Apple Health export | Health app → Export all health data | Sleep, activity, heart rate patterns |
| Google Calendar | Export as .ics | Schedule patterns, priorities |
| OBD logs | From existing OBD tool | Car history |
| Any existing PDFs | Jacob drops them in a folder | Manuals, medical records, anything useful |

### Phase 3 — Honcho Seeding

After phases 1 and 2, Honcho's extraction layer replays the historical data. It builds Jacob's psychological profile before a single live conversation happens. His patterns (execution gap, research avoidance, planning marathons, emotional compression) are already known — not discovered slowly.

---

## Daily Experience

**Morning (7am, automatic)**
Kitty sends a brief. One casual opener. What's relevant today. One thing from the news digest she thinks he'll care about. If Honcho flagged something, one gentle observation. Never more than a short read.

**Day-to-day**
Jacob opens Open WebUI on phone or Mac. Talks or types. Kitty knows his context. When he asks about his car, she has his vehicle history and service manuals. When he asks about a symptom, she has his blood results and medical history. When he wants to build something, she architects it before writing a line of code. When she notices a pattern, she names it — once, gently, without lecture.

**Voice**
Full voice conversation. Jacob speaks, faster-whisper transcribes, Kitty responds in text (or voice via Kokoro TTS if he wants). Same context, same memory, works the same as text.

**Documents / PDFs / Schematics**
Jacob drops a file into Open WebUI or the ingestion folder. LlamaIndex reads it. For complex technical docs (circuit boards, schematics), a vision pipeline runs: Claude Sonnet describes every component in detail, OCR extracts all text and labels, an image search finds related schematics online to augment. All of it goes into ChromaDB tagged to that document. Jacob can ask anything about it later.

**Vibe Coding**
Jacob describes what he wants to build. Kitty (acting as architect) designs it, checks it against his skill level, and produces a clear plan before any code gets written. Claude Code executes the plan. Kitty reviews what was built.

**Weekly (automatic)**
Honcho surfaces one pattern observation. Direct, kind, non-judgmental. Not a report — just one thing she noticed that she wanted to say out loud.

---

## News Aggregation

n8n pulls headlines daily from multiple sources (RSS feeds, no scraping needed):
- Tech / AI developments
- Canadian news
- Topics matching Jacob's domains (automotive, health, finance, whatever he specifies in onboarding)

Kitty reads the raw headlines and produces a short digest — 5-8 items, one sentence each, with source. Appears in morning brief. No ads, no clickbait, just the actual news.

---

## Specialist Contexts (the 5 domain modes)

Instead of 12 complex specialists, Kitty has 5 clean context modes that activate based on what Jacob is asking about:

| Mode | Activates when | What changes |
|---|---|---|
| Soul / default | General conversation, personal, life stuff | Core Kitty personality, full psychological context |
| Repair & Technical | Car, electronics, schematics, "how do I fix" | Pulls vehicle history, service manuals, schematic database, step-by-step repair mode |
| Health & Medical | Symptoms, blood results, medications, fitness | Pulls medical profile, frames everything as "here's what research says / questions for your doctor" |
| Research | "Look this up," "find out about," deep dives | Activates Firecrawl pipeline, cites all sources, never synthesizes without grounding |
| Code & Build | "I want to build," "how do I make," vibe coding | Architect mode — plan before code, check complexity against skill level |

---

## What Gets Kept From Existing Kitty

| Component | Location | Why keep it |
|---|---|---|
| Honcho | `src/space_kitty/honcho.py` | Core psychological layer — unique, already wired |
| faster-whisper voice input | `src/api/transcription_service.py` | Already works, wire into Open WebUI |
| Morning brief | `src/core/morning_brief.py` | Already built, just needs n8n to fire it |
| Firecrawl research pipeline | `src/tools/research_pipeline.py` | Good, working, keep as research specialist tool |
| ChromaDB | `src/memory/chroma_manager.py` | Keep as knowledge base, reduce to single interface |
| OBD parser | `src/tools/obd_parser.py` | Real utility for repair domain |
| Domain routing logic | `src/core/query_router.py` (simplified) | Keep the domain classification, replace model routing with LiteLLM |
| Token cache | `scripts/kitty_builder.py` (extract) | Extract semantic cache and token tracking, keep those |
| Skill engine | `src/core/skill_engine.py` | Keep — drives command behavior |
| Command engine | `src/core/command_engine.py` | Keep — handles slash commands |

---

## What Gets Cut

| Component | Why |
|---|---|
| Custom model routing (4+ files) | Replaced by LiteLLM — one library does all of it |
| 6 of 8 memory files | Replaced by Zep + single ChromaDB interface |
| Eval infrastructure | Overkill for one user. Archive, don't delete. |
| Swarm executor | Premature. Archive. |
| Observability/metrics dashboard | Not needed for personal use. Archive. |
| Duplicate orchestrators | Keep one (CoreOrchestrator), archive the rest |
| garage-ui | Replaced by Open WebUI. Keep code, just stop maintaining. |
| KittyBuilder (most of it) | Claude Code replaces it. Extract: token cache, semantic cache, security enforcement. |

---

## Build Order (what ships first)

Each phase is one focused session. Each phase delivers something Jacob can actually use.

**Phase 1 — Open WebUI + Kitty soul**
Install Open WebUI. Configure Kitty's name, personality, system prompt. Point at Claude via LiteLLM. Jacob can talk to Kitty on day 1.

**Phase 2 — LiteLLM model routing**
Wire LiteLLM to replace all custom routing. Hermes 3 via Ollama for free local tasks. DeepSeek Flash for cheap calls. Claude for complex. Cost tracking on by default.

**Phase 3 — Zep memory**
Install Zep self-hosted. Wire into Open WebUI pipeline. Every conversation starts feeding Jacob's long-term memory. Kitty starts remembering things between sessions.

**Phase 4 — Onboarding: guided interview**
Build the 8-domain interview flow inside Kitty. Jacob does one domain per sitting. All answers go into Zep + ChromaDB. Honcho gets seeded from interview answers.

**Phase 5 — Onboarding: file ingestion**
Build ingestion pipeline (LlamaIndex). Process session logs, chat exports, Apple Health, calendar, OBD logs, existing docs. Everything lands in ChromaDB. Honcho replays history.

**Phase 6 — Morning brief + news via n8n**
Install n8n. Configure 7am brief. Wire news RSS sources. Brief fires automatically every morning.

**Phase 7 — Voice (input + output)**
Wire faster-whisper into Open WebUI voice input. Add Kokoro TTS for voice output. Full voice conversations working.

**Phase 8 — Document + schematic pipeline**
LlamaIndex PDF ingestion working. LlamaParse for complex docs. Vision pipeline for schematics/circuit boards (Claude Sonnet describes, OCR extracts, image search augments).

**Phase 9 — Honcho weekly mirror**
Wire n8n to trigger Honcho pattern report weekly. Kitty surfaces one observation. Gentle, direct.

**Phase 10 — Domain specialist contexts**
Build the 5 context modes. Test each domain. Medical mode with health profile. Repair mode with vehicle history. Research mode with citation grounding.

---

## Tools Reference (plain English)

- **Open WebUI** — the chat interface. Free, self-hosted, runs on your Mac.
- **Hermes 3** — a free AI model that runs locally, great at agent/tool tasks.
- **Ollama** — the app that runs Hermes 3 (and other models) on your Mac.
- **LiteLLM** — one Python library that talks to all AI companies so you don't have to write separate code for each.
- **Zep** — self-hosted memory system. Remembers facts about Jacob across all conversations. All data stays local.
- **ChromaDB** — a database that understands meaning (not just keywords). Already in Kitty. Stores everything Kitty knows.
- **LlamaIndex** — a library that reads files (PDFs, docs, images) and puts them into ChromaDB. The "ingestion pipeline."
- **LlamaParse** — LlamaIndex's premium document parser. $0.003/page. Used for schematics, medical records, complex layouts.
- **Honcho** — psychological pattern extraction. Watches every conversation. Already built.
- **n8n** — visual automation tool. Runs tasks on a schedule without Jacob needing to do anything.
- **faster-whisper** — speech-to-text. Already built. Jacob talks, it transcribes.
- **Kokoro TTS** — text-to-speech. Free, runs locally. Kitty talks back.
- **Firecrawl** — web scraper for research. Already built. Pulls and reads full web pages.

---

## What This Is Not

- Not a commercial product. Personal use only.
- Not a replacement for doctors or lawyers. Medical/legal output is always framed as research and questions to ask, never diagnosis or advice.
- Not finished on day one. It ships something useful in Phase 1 and gets better with every phase.
