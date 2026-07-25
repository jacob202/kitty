# Kitty Evolution Brainstorm — 2026-07-24

Raw distillation of Jacob's stream-of-consciousness session. Each section is a
thread. Decisions made here should feed the next ACTIVE_MISSION or KX initiative
set. Nothing here is committed; everything needs prioritization.

---

## 1. Mobile UX — Immediate Fixes

**Problem:** Chat bar in the Chat tab is unusable on mobile. Can't chat with
Kitty on phone at all right now.

**Direction:**
- Home page should have chat. The primary chat surface lives on Home, not in a
  separate tab. Home IS the chat.
- Chat tab repurposed into something else — "Projects Den"? A workspace view
  where chats have become projects with context, files, artifacts.
- Open question: is Home chat a single continuous thread that carries context?
  What happens when context runs out? Need a context-window-aware UX pattern.

**Related existing work:** Slice 5 (mobile/PWA polish) in the fable-ux-phase
working notes — but that's cosmetic (bottom tabs, safe-area). This is structural
(reorganizing what lives where).

---

## 2. Image Studio Overhaul

**Problems:**
- Need a way to add/import images into the image studio
- Current setup is too slow — needs cloud compute
- Have $10 credit on airforce.ai (subscription-based, limited models)

**Character likeness research:**
- Impressed with Guava Pro 1.5 on mage.space — one photo of questionable quality
  produces some of the best character-likeness generations seen
- How to achieve similar experience in Kitty?

**Character system design:**
- What is a character? A character card containing:
  - Photos/reference images
  - Description/prompt
  - Name
  - Maybe more (voice, personality, backstory)?
- How does Kitty reliably recreate characters across generations?
- Need a harness/skill that:
  1. Reverse-engineers a photo into a language the model understands
  2. From that recreation, iterates with its own language
  3. Makes character creation easy and repeatable
- Where does the character card live? File system? Database? UI panel?

**Image gen brain:** Keep Mistral Small 4 — has vision, European leanings,
$0.15/$0.60 per 1M tokens, 256K context.

---

## 3. Models — Kitty's Brain (Resolved)

**Source:** DeepSeek, Qwen, Mistral, GLM, Kimi researched live in this session.

**Decision:** DeepSeek V4 Pro as primary brain.
- $0.44/M input, $0.87/M output, 1M context
- 1.6T params / 49B active (MoE)
- AI intelligence 44.3, coding 59.4, agentic 36.4
- Best balance of smarts, price, and context window

**Fallback:** DeepSeek V4 Flash
- $0.10/M input, $0.20/M output, 1M context
- 284B/13B active
- For routine chat, summarization, tasks that don't need peak reasoning

**Heavy coding/agentic tasks:** GLM 5.2
- $0.82/M input, $2.58/M output, 1M context
- AI intelligence 51.1, coding 68.8, agentic 43.1
- Strongest per-dollar coding/agentic performance

**Image gen:** Mistral Small 4 ($0.15/$0.60, 256K ctx, vision)

**Model price reference (per 1M tokens via OpenRouter):**

| Model | Input | Output | Intel | Coding | Agentic | Context |
|---|---|---|---|---|---|---|
| DeepSeek V4 Flash | $0.10 | $0.20 | 40.3 | 56.2 | 31.1 | 1M |
| DeepSeek V4 Pro | $0.44 | $0.87 | 44.3 | 59.4 | 36.4 | 1M |
| GLM 5.2 | $0.82 | $2.58 | 51.1 | 68.8 | 43.1 | 1M |
| GLM 4.7 Flash | $0.06 | $0.40 | — | — | — | 200K |
| Mistral Small 4 | $0.15 | $0.60 | — | — | — | 256K |
| Qwen3.7 Plus | $0.32 | $1.28 | 39.0 | 55.9 | 20.8 | 1M |
| Kimi K2.6 | $0.68 | $3.42 | 44.2 | 61.8 | 30.3 | 256K |
| Kimi K3 | $3.00 | $15.00 | 57.1 | 76.2 | 50.1 | 1M |

---

## 4. Kitty Computer Control

Kitty needs to run things from the computer — Claude coworker / dispatch type
situation. Ideally control apps, browsers, and system state.

**Relevant repos/tech to investigate:**
- Computer-use tools (Orca already has this)
- Claude computer use / Anthropic computer-use API
- Browser automation via Playwright/Puppeteer
- macOS accessibility APIs / AppleScript / Shortcuts
- Could leverage the existing Orca computer-use skill

---

## 5. KittyBuilder — Next Evolution

**Builder needs its own:**
- Brain (its own system prompt — separate from Kitty's personality)
- Chat interface (talk to Builder directly)
- More information transparency:
  - "You have these tasks"
  - "This is why this one failed"
  - "This is how you would fix it"
  - "This is the quality level of the work submitted by the model"
- Clear initiative and task creation flow
- Graphical representation of build process:
  - Where am I going?
  - What's been built?
  - How and with what?
  - Could be a card, but a UI chatbot is preferable

**Key question:** Where do Kitty and KittyBuilder's capabilities overlap and
separate? Need a clear boundary.

---

## 6. Documents Rework

- Documents absolutely need groups and folders
- Cannot all be flat/undifferentiated
- Specialists (not "agents" — decision made) are domain experts:
  - Health guy for physical health
  - Therapist for mental health
  - Audio electronics nerd for Sansui stuff
  - Etc.
- Each specialist has personality, system prompt, specific context
- Specialists need to persist context across sessions
- Some roles are special and require dedicated UI, files, and context

---

## 7. Chat Intelligence & Personality

**Kitty should:**
- Guide and give insights, not just respond
- Creative use cases — "did you know?"
- Apply learnings from past conversations
- Be naturally curious about who Jacob is — what he likes, how he reacts, how
  he thinks
- Have its own personality (already started at the very beginning — revisit
  those files, session logs, personality backup)
- Naturally create projects from chat conversations, emails, etc.
- Have a very good sense of:
  - Where Jacob is in life
  - How much money (eventually)
  - Benefits, when he's been to the doctor and for what
  - When to go back to the dentist
- Messages (iMessages, emails, chat) should all be helpful inputs

---

## 8. Home Page — What Lives Here

**Right now:** Nothing. All work. Not useful as a daily driver.

**Should have:**
- Chat (primary surface — see #1)
- "Best of" feed:
  - Important emails — especially government/requires-action emails
  - Remove friction completing tasks from email
  - Life-relevant notifications
- Quick journal prompt
- Next actions / what needs attention

---

## 9. News Tab (Future)

Aggregate from:
- AI news
- GitHub/repo news and highlights
- Reddit (subscribed subreddits)
- Substack
- New York Times
- Biohacking
- Electronic music
- Audiophile
- General "best of" across interests

---

## 10. Journaling

- Dedicated journaling section
- Pre-built prompts personalized to Jacob
- Optional — choose prompts or free-write
- Auto-journal at end of every day:
  - What did we talk about?
  - What was Jacob curious about?
  - What patterns emerged?
- Natural/journal-like — Kitty gets curious about specific topics and dives in

---

## 11. Marketplace / Research

- Periodic searches for local items Jacob is looking for
- Notifications when something comes up
- Market researcher mode — researching speakers, gear, etc.
- Hold onto all research so it can be reused

---

## 12. UI/UX — How to Smoke This Out Faster

**Concern:** Still at a basic level of user experience and functionality for
how simple this should be to understand.

**Ideas:**
- UI swarm with experts (already exists as concept)
- Customer swarm — fake beta release
- Could be extremely powerful if prompted and set up correctly
- Needs tasks to figure out the fake beta / customer swarm approach

---

## 13. Recurring Planning Routine

Need a regular brainstorming and planning rhythm:
- Figure out exactly how Kitty becomes a real full-fledged app
- Big difference between prototype and product — many moving parts and decisions
- Dedicated future-thinker/planning persona:
  - On the cutting edge
  - Forward-thinking
  - Creative
  - Outside-the-box
  - Free spirit

---

## 14. Small Local Model

- Idea: something like "Sloth" — find a small model, have it know just Jacob's
  data. Could be really small but would know him very well.
- Sounds like Kitty though — may overlap with core Kitty concept
- Also: something that's more like a "republic" agent (goes out into the world,
  agent-like)
- Related: LlamaIndex for turning documents into agents/specialists

---

## 15. Repos to Investigate

| Repo/Tech | Purpose |
|---|---|
| Fabric | CLI commands, pattern library |
| DSPy | Programming foundation models |
| Microsoft skill stuff | Self-evolving AI skills, files-to-prompts |
| System prompts repos | Inspiration for Kitty's prompts |
| PR agent repo | Code review automation |
| GPT Researcher | Deep research feature |
| Onlook | Kitty design/UI feature |
| Mastra | Agent framework |
| 12 factor agents | Agent design principles |
| CC plugins | Plugin architecture |
| Sloth | Small local model approach |
| LlamaIndex | Documents → agents |

**Also:** Use AI to review every insight Jacob has ever had and find:
- All the things he should be doing
- Consistent mistakes / patterns
- After every Q&A about a topic/idea/event, ask a question that furthers
  understanding

---

## 16. Open Questions (Unresolved)

1. **Home chat context model:** Continuous thread? When does context run out?
   What happens then?
2. **Chat tab becomes what?** "Projects Den"? Workspace view?
3. **Character card storage:** Database table? File system? Format?
4. **Character recreation reliability:** Can a harness/skill reverse-engineer
   a photo into model-readable language reliably?
5. **Kitty vs KittyBuilder boundary:** Where do they overlap/separate?
6. **Airforce.ai vs other image cloud compute:** Worth the $10 credit or find
   alternatives?
7. **"Did you know?" / proactive insights:** How aggressive should Kitty be?
8. **All of this is slow right now** — chat speed is unacceptable. Perf is
   priority zero.
9. **Specialist context persistence:** How do specialists carry context across
   sessions?

---

## 17. Priority Signals (Jacob's Emphasis)

- Home page sucks — no chat, nothing for daily driver → **highest UX priority**
- Mobile chat is broken → **blocker**
- Chat is too slow → **blocker**
- Image studio needs cloud compute and character system → **high**
- KittyBuilder needs its own brain and chat → **high**
- Documents need structure → **medium**
- Everything else (news, marketplace, journaling, etc.) → **future**

---

## 18. Cross-Reference with Existing Work

- **ACTIVE_MISSION.md (KFX-001):** Frontend + product-experience harvest.
  This brainstorm provides raw input for the KX initiative manifests.
- **fable-ux-phase:** Slices 1-2 done (design alignment, chat deepening).
  Slice 3 (home click-throughs) is next. Slices 4 (perf) and 5 (mobile PWA)
  should be elevated given the mobile chat blocker.
- **KittyBuilder:** `docs/KITTYBUILDER_QUICKSTART.md`, existing CLI surface.
  Needs the UI/chat layer described here.

---

*Next: prioritize into a bounded initiative list, feed into KX manifests or
next ACTIVE_MISSION.*
