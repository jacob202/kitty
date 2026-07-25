# Kitty Initiatives — Reorganized from Session Meta-Analysis

**Roadmap authority** per `docs/AUTHORITY_MAP.md` — this file owns feature
sequencing and priority. `docs/PLANS.md` is a session status tracker that
defers to this file; `docs/SESSION_META_2026-07-24.md` is the analysis this
plan was built from.

**Principle:** Depth first, then breadth. Every initiative must answer:
"Does this make Kitty better at the thing it already does, or does it add
something new?" New features only after existing features actually work.

## Layer 0 — Foundation (4 initiatives, prerequisites)

### F0: Context Compaction
**Why:** The 1M context window WILL fill. A single thread running for weeks
becomes unusable without compaction.
**What:**
- After N messages, auto-summarize conversation into memory checkpoint
- Active window keeps last 10 messages + checkpoint
- At context limit: archive thread, new thread, inject "previously..." summary
- User never sees a context-full error
**Depends on:** Memory system (already exists)
**Effort:** Medium (backend only, no UI changes needed to start)

### F1: Privacy Boundaries
**Why:** Before adding email, health, money features, define what data goes
where and who can access it.
**What:**
- Document PII tiers: local-only, cloud-ok, never-store
- Enforce at the LLM boundary (extend existing `privacy_tier` system)  
- Health data, financial data, email content → never leaves local gateway
  unless explicitly tagged cloud-ok
- User-visible privacy labels on features
**Depends on:** Existing D10 privacy system in `call_llm`
**Effort:** Small (mostly doc + boundary enforcement in routes)

### F2: Latency Budget
**Why:** "Chat is too slow" is a feeling. "TTFT > 2s on wifi" is a bug.
**What:**
- Define TTFT targets: <1.5s on wifi, <3s on cellular
- Add timing headers to all gateway responses
- Display TTFT in UI (status bar or tooltip)
- Alert when targets are exceeded
**Depends on:** TTFT logging (already added this session)
**Effort:** Small (logging exists, add UI display + alert threshold)

### F3: Dogfood Script
**Why:** Catch real bugs before human users do. Swarm-review is static
analysis; dogfood script drives actual user flows.
**What:**
- Script that: starts dev server, runs Playwright through key flows
  (home loads → send chat message → check response → navigate to tutor →
  quiz a question → check builder → check settings)
- Reports: failures, latency per step, visual regressions
- Can run headless in CI
- Exits non-zero on failures
**Depends on:** Visual-diff (already exists), Playwright (already installed)
**Effort:** Medium (one new script, ~200 lines)

## Layer 1 — Deepen Existing (4 initiatives, highest user impact)

### D1: Chat Depth
**Why:** Chat is the core loop. Right now it works but is shallow — no context
management, no thread organization, no continuity across sessions.
**What:**
- Context compaction (F0) integrated into chat experience
- Thread persistence with proper session restore
- Message attachments that actually work (file upload → gateway → context)
- Chat search across all threads
- Per-thread memory and context indicators
**Depends on:** F0 (context compaction)
**Effort:** Large (backend + frontend changes)

### D2: Home Depth
**Why:** Home should deliver on the North Star: "one concrete, doable next
move." Right now it's a dashboard of tiles.
**What:**
- Time-aware home: different content for morning/afternoon/evening
- "One next move" hero that's actually useful (not generic)
- Personalization from memory + journal + chat patterns
- Remove tiles that aren't earning their space
- Quick actions that complete in one tap
**Depends on:** Memory system, journal
**Effort:** Medium (mainly frontend, uses existing data)

### D3: Tutor Depth
**Why:** Tutor has a working quiz loop but can't learn from documents. The
UI we built (TutorShell) is a shell — it needs the backend to actually work.
**What:**
- Fix document ingestion pipeline (tutor/learn route + ChromaDB)
- Working progress tracking: what have I learned, what am I weak on?
- Spaced repetition that actually schedules reviews
- Quiz quality: generated questions should be smart, not templated
- Integration with knowledge system (reuse what's already indexed)
**Depends on:** Knowledge system (exists), tutor.py (exists)
**Effort:** Medium (mostly backend fixes + polish)

### D4: Builder Depth
**Why:** Builder's quality is "questionable" and it "takes just as long to
launch, fix the runs, and merge the work as it does to get another model to
just do it." The value proposition is broken.
**What:**
- Chat interface for Builder (talk to it directly about tasks)
- Failure transparency: "this is why this one failed, this is how to fix it"
- Quality metrics on submitted work (did it compile? did tests pass?)
- Initiative creation from chat ("build me a dogfood script")
- Faster worker dispatch (parallelize where possible)
**Depends on:** Builder CLI (exists)
**Effort:** Large (new UI + Builder backend changes)

## Layer 2 — One New Lane at a Time (3 initiatives)

### N1: Specialists v1 (1 specialist)
**Why:** Prove the specialists concept with one working example before
building infrastructure for many.
**What:**
- Pick one specialist (recommendation: health/therapist — highest personal
  value to Jacob)
- System prompt with personality, knowledge domain, and conversation style
- Persistent context store (last N messages injected on session start)
- Simple UI: a specialist appears in the expert strip, clicking opens a
  dedicated chat with their persona
- One specialist working end-to-end before adding more
**Depends on:** Chat infrastructure
**Effort:** Medium (one specialist is a prompt + context store)

### N2: Documents v1
**Why:** Documents are flat and undifferentiated. Specialists need organized
context.
**What:**
- Groups/folders for documents
- Specialist-linked folders (health docs → health specialist context)
- Simple search across documents
- Document ingestion from file upload + URL
**Depends on:** N1 (specialists should own their document context)
**Effort:** Medium (frontend restructuring + backend folder support)

### N3: Proactive Insights v1
**Why:** "Did you know?" — Kitty should surface patterns it notices, not just
respond to questions.
**What:**
- Passive pattern detection: recurring topics, emotional trends in journal,
  habits from chat
- Simple cards on home: "you've mentioned X 4 times this week — want to
  explore it?"
- Dismissible, never intrusive
- One new card per session max (don't spam)
**Depends on:** Journal, memory system
**Effort:** Small (memory query + card component)

## Layer 3 — Validate Before Building (4 items, research only)

### V1: Email Integration Research
**Scope:** Research only. Can we reliably pull emails? What's the privacy
model? What's the latency? Build a prototype that reads 1 email account
and summarizes the inbox.

### V2: Journal Prompt Engine Research
**Scope:** Research only. What makes a good journal prompt? Can we generate
personalized prompts from memory + chat patterns? Build a prototype prompt
generator and test with 5 prompts.

### V3: Computer Control Research
**Scope:** Research only. Orca already has computer-use. Can we wire it
into Kitty's tool system? What's the security model? Build a prototype
that opens an app via Orca from a Kitty chat command.

### V4: Local Model Feasibility
**Scope:** Research only. Can ollama run on Jacob's MacBook Air with
acceptable performance? What models fit in 8GB? Build a prototype that
swaps between cloud (OpenRouter) and local (ollama) for the same query
and measures latency + quality.

## What Not to Build (Explicitly Rejected)

- **News tab** → A specialist, not a tab. "Hey kitty, what's new in AI?"
  - Rejected because: content aggregation is a solved problem, Kitty should
    be the interface, not the aggregator
- **Marketplace page** → A specialist with periodic search, not a UI page
  - Rejected because: premature until research specialist works
- **Character system beyond basic** → Photo→description pipeline only
  - Rejected because: Guava Pro-level quality requires custom training
    infrastructure we don't have
- **Customer swarm** → Dogfood script first (F3), swarm later
  - Rejected because: premature until basic reliability is established
- **iMessage reading** → Email first, iMessage when/if stable
  - Rejected because: Apple's security model makes this fragile

## Sequencing

```
F0 (context) ──┐
F1 (privacy) ──┤
F2 (latency) ──┤── All can start in parallel
F3 (dogfood) ──┘
       │
       ▼
D1 (chat depth) ── depends on F0
D2 (home depth) ── can start immediately
D3 (tutor depth) ── can start immediately
D4 (builder depth) ── can start immediately
       │
       ▼
N1 (specialists) ── depends on D1 (chat)
       │
       ▼
N2 (documents) ── depends on N1
N3 (insights) ── can start after D2 (home) + journal exists
       │
       ▼
V1-V4 (research) ── can run in parallel with everything above
```

## Immediate Next Actions

1. Commit + push this session's changes (43 files)
2. Restart LiteLLM with `OPENROUTER_API_KEY` for DeepSeek models
3. Dogfood: send a real chat message, check TTFT in logs
4. Start F3 (dogfood script) — highest-leverage single task
5. Start F0 (context compaction) — design before chat fills up
6. Other Orca instance continues: repo research, architecture audit,
   Builder redesign, image studio research
