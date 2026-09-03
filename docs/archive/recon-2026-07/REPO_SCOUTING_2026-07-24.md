# Repo Scouting — What Already Exists That Kitty Can Use

**Correction from first pass:** These aren't features to build from scratch. They're
existing repos to borrow, wrap, or integrate. The question isn't "should we build X"
— it's "what's already out there that does X and how do we use it?"

---

## News Tab (Jacob's favorite — NOT killed, just repurposed)

**What already exists:**
- **[FreshRSS](https://github.com/FreshRSS/FreshRSS)** — 15.6k stars, self-hosted RSS aggregator with a proper API. Supports categories, search, mobile-friendly. Runs in Docker. Has Fever API compatibility so any RSS client can talk to it.
- **[RSSHub](https://github.com/DIYgod/RSSHub)** — 45k stars, "everything is RSSible." Generates RSS feeds from services that don't have them: Twitter/X, Reddit, YouTube, Substack, GitHub, NYT, etc. This is how you get Reddit, Substack, and NYT into an RSS reader.

**How Kitty would use it:**
1. Deploy FreshRSS (docker container) as Kitty's feed backend
2. Use RSSHub to generate feeds for Reddit, Substack, GitHub, etc.
3. Kitty reads FreshRSS's API, curates a "best of" for the home page
4. Jacob configures his feeds once in FreshRSS's UI (or Kitty does it via API)

**Cost:** Free. Both are open source. Docker container for FreshRSS is ~100MB.
**Integration difficulty:** Low. Both have REST APIs. Zero build — just deploy and read.

---

## Marketplace / Local Listings Monitoring

**What already exists:**
- **[changedetection.io](https://github.com/dgtlmoon/changedetection.io)** — 32.7k stars, "the best and simplest tool for website change detection." Monitors any web page for changes. Tracks price drops, restock alerts, new listings on classifieds. Has a REST API, webhooks, and can send notifications (email, Slack, Discord, etc.). Self-hostable, free.

**How Kitty would use it:**
1. Deploy changedetection.io (docker container)
2. Jacob tells Kitty: "watch for Sansui AU-717 on Kijiji and FB Marketplace"
3. Kitty adds those URLs to changedetection's watch list via API
4. When listings appear, changedetection triggers a webhook → Kitty receives it
5. Kitty surfaces the listing as a card on home: "new Sansui AU-717 listing — $450"

**Cost:** Free. Open source. Docker container.
**Integration difficulty:** Low. REST API + webhook model. Kitty just reads the results.

**For market research (not monitoring):**
- Use Kitty's existing LLM + search capabilities. "Research speakers under $500" → Kitty generates search queries, reads results, synthesizes. No separate tool needed beyond what we already have (OpenRouter models with search capability).

---

## Customer Swarm / AI-Driven UI Testing

**What already exists:**
- **[browser-use](https://github.com/browser-use/browser-use)** — 106k stars, MIT license. Python library that lets AI agents control a browser. Used for: QA automation (QA test my local website and report bugs), form filling, data extraction. Has a CLI mode that Claude Code/Codex/Cursor can control directly.

**How Kitty would use it for testing:**
1. Kitty's dogfood script calls browser-use with a test prompt: "open localhost:4000, check that home page loads with greeting, navigate to tutor, attempt a quiz question, report any errors or broken UI"
2. browser-use drives Chromium, takes screenshots, reports findings
3. Multiple runs with different models = "expert swarm" testing (different models catch different issues)
4. For "customer swarm": same approach but with prompts simulating different user personas: "you're a first-time user opening Kitty for the first time — report what's confusing"

**Cost:** Free (open source). LLM calls per test run (tiny, ~$0.01 per run with DeepSeek Flash).
**Integration difficulty:** Medium. Requires Playwright + browser-use Python package. Already have Playwright for visual-diff.

**This also solves computer control (#4 in brainstorm):** browser-use IS computer control for the browser. For desktop app control, Orca's computer-use skill already covers that. So the "computer control" feature = browser-use (browser) + Orca skill (desktop apps).

---

## iMessage Integration

**What already exists:**
- **[imessage-exporter](https://github.com/ReagentX/imessage-exporter)** — 5.4k stars, GPL-3.0. Rust library + CLI that exports iMessage data to txt/html/json. Supports every iMessage feature: group chats, attachments, edited messages, tapbacks, stickers, RCS, SMS, MMS. Works on macOS Sequoia/Tahoe.

**How Kitty would use it:**
1. Install imessage-exporter CLI (cargo install or brew)
2. Kitty runs `imessage-exporter` periodically (cron job or manual trigger) to export the iMessage database to JSON
3. Kitty reads the JSON export, indexes it into its memory/knowledge system
4. Messages become searchable: "what did Mom say about dinner on Tuesday?"
5. Auto-summarize recent conversations for the home page

**Limitations:** macOS only (where Kitty already runs). Requires Full Disk Access permission (user grants once). Export is read-only — Kitty can read messages but can't send them. Export takes 30-60 seconds for large databases, so it's a batch operation, not real-time.

**Cost:** Free. Open source.
**Integration difficulty:** Medium. CLI wrapper + JSON parsing + memory indexing.

---

## Email Integration

**What already exists:**
- Python's `imaplib` (stdlib) — talk to any IMAP server (Gmail, iCloud, etc.)
- **[mail-parser](https://pypi.org/project/mail-parser/)** — Python library, parses email into structured data
- No external repo needed — this is 50 lines of Python to connect to IMAP, fetch recent emails, and feed them into Kitty's context

**How Kitty would use it:**
1. Connect to Jacob's email via IMAP (env var: EMAIL + app password)
2. Fetch unread emails from last 24 hours (not entire inbox)
3. Classify: government/requires-action, personal, newsletters, spam
4. Surface action-required emails as cards on home: "DMV renewal due — respond?"
5. "Remove friction completing the task" = Kitty can draft replies, fill forms

**Privacy:** Email stays local. LLM only sees the subject + first 200 chars unless Jacob explicitly says "read this email fully."
**Integration difficulty:** Low. Stdlib IMAP + existing LLM pipeline.

---

## Context/Thread Management

**Trade-off analysis (per Jacob's request):**

| Model | Pros | Cons |
|---|---|---|
| **Single eternal thread** | Always in context, never loses continuity, feels like one conversation | Fills up (1M context = ~250K words), can't separate topics, becomes unwieldy, counter to how everyone uses chat |
| **Multiple threads (per topic)** | Clean separation, can archive/delete, proven UX pattern (every chat app), context per topic stays fresh | Need to manage threads, easy to lose track, less "always there" feeling |
| **Hybrid: home = most recent thread, chat = thread list** | Best of both. Quick access from home, organization from chat tab. Threads auto-summarize into memory so old context persists even in new threads | More complex to implement, need good thread naming/organization |

**Recommended: Hybrid with auto-organization.**

Kitty should manage threads like a good PA manages files:
1. **Home shows most recent active thread** — start typing immediately
2. **Chat tab shows all threads** with auto-generated names based on first message
3. **Kitty auto-detects topic shifts** — "this seems like a new topic, want me to: [continue here] [start new thread]"
4. **Threads auto-summarize into memory** — when a thread is idle for 24h, Kitty writes a summary checkpoint to memory. When you return to the topic, the memory checkpoint is injected as context.
5. **Old threads become read-only archives** — never deleted, always searchable

**What already exists for context/memory management:**
- **[mem0](https://github.com/mem0ai/mem0)** — already used by Kitty for memory. Handles adding/searching memories with embeddings.
- **[LangChain memory](https://python.langchain.com/docs/modules/memory/)** — various memory strategies: buffer, summary, window, token-buffer. Good reference implementations.
- **[only-my-mem0ry](https://github.com/ost527/only-my-mem0ry)** — fully local mem0 without cloud. Runs on-device embeddings with Chroma. Could replace cloud mem0 for privacy-sensitive data.

**Kitty already has the building blocks:** `memory_graph.py`, `memory_weave.py`, `context_assembler.py`. The thread management is a UI layer on top of what already exists.

---

## Repos for Jacob & The Agent Team (not just Kitty)

### Personal productivity + life OS
- **[n8n](https://github.com/n8n-io/n8n)** — 60k+ stars, fair-code. Workflow automation with AI nodes. Connect email, calendar, tasks, notifications. "If this email is from the government and requires action, create a todo and notify me."
- **[Activepieces](https://github.com/activepieces/activepieces)** — 14k+ stars, MIT. No-code automation builder. Alternative to n8n with cleaner UX.

### Agent team tooling (for the OpenCode/Claude Code workflow)
- **[browser-use](https://github.com/browser-use/browser-use)** — 106k stars. Already covered above — useful for agents controlling browsers during development.
- **[Continue](https://github.com/continuedev/continue)** — 22k+ stars, Apache 2.0. Open-source AI code assistant. Could be a reference for how Kitty's coding features work.
- **[Aider](https://github.com/Aider-AI/aider)** — 30k+ stars, Apache 2.0. AI pair programming in terminal. Reference for Kitty's code-editing capabilities.

### Self-improvement / learning from past insights
- **[Obsidian](https://obsidian.md)** + plugins — not open source but has a massive plugin ecosystem for knowledge management. Reference for how to structure personal knowledge.
- **[Logseq](https://github.com/logseq/logseq)** — 36k+ stars, AGPL. Open-source knowledge base. Good reference for graph-based note-taking that Kitty's memory system could learn from.
- The "review every insight I've ever had" idea → could be done with Kitty's existing memory system + a scheduled LLM call that reads memory and identifies patterns. No new repo needed.

---

## Summary: What's Free to Steal

| Feature | Repo | Stars | License | Integration |
|---|---|---|---|---|
| News tab | FreshRSS + RSSHub | 15k + 45k | AGPL / MIT | Deploy Docker, read API |
| Marketplace monitoring | changedetection.io | 32k | Apache 2.0 | Deploy Docker, webhook → Kitty |
| Computer control + swarm testing | browser-use | 106k | MIT | pip install, Python wrapper |
| iMessage reading | imessage-exporter | 5.4k | GPL-3.0 | CLI wrapper → JSON → memory |
| Email reading | imaplib (stdlib) | — | — | 50 lines of Python |
| Context/memory mgmt | mem0 (already used) | — | — | Already integrated |
| Context — local privacy | only-my-mem0ry | small | — | Reference only |
| Workflow automation | n8n or Activepieces | 60k / 14k | fair-code / MIT | Deploy Docker, connect APIs |
| Knowledge base | Logseq | 36k | AGPL | Reference design only |

**Total cost to integrate all of these:** $0. Every single one is free and open source.
**Total effort:** Docker deploys + API wrappers. No feature built from scratch.
