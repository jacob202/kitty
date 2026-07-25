# Mature AI Product Research

**Written:** 2026-07-25 · **Written against:** `gateway-packages` @ `ac898f9`, a commit that
has since been rewound out of that branch; its history is preserved at
`backup/gateway-packages-2026-07-25`.

**Status: reference, not authority.** This document records what other projects learned. It
does not set priorities, sequencing, or effort for Kitty. Everything under a "What this means
for Kitty" heading is a proposal, and none of it binds anything until it is decided
separately and recorded in the roadmap authority named by `docs/AUTHORITY_MAP.md`.

What mature open-source AI assistants learned the hard way, organized by theme rather than
by project. Every claim below is either linked to a primary source I fetched, or explicitly
labelled as inference. Where a theme is thin, it says so — a gap named is worth more than a
gap papered over.

Written as a companion to the competitive comparison that was in `docs/PLANS.md` at the time.
That section has since been removed as stale; the pointer in `docs/PLANS.md` supersedes it.
That comparison asked "what do they have that we don't." This one asks "what did it cost them
to learn it."

Projects surveyed: Open WebUI (146k★), Goose (51k★), LibreChat (41k★), Khoj (36k★),
Chatbot UI (33k★), AionUi (31k★).

---

## Theme 1 — The first run is where you lose people

### The evidence

Open WebUI's most common first-run failure is a blank screen, and it has at least four
distinct causes that all present identically to the user:

- The container serves the page before the database finishes initializing. Documented fix
  is "wait 60 seconds and refresh" — the app has no way to say this itself.
- A hanging LAN connection to the model backend leaves the UI blank except for the
  keybinding help button in the corner ([#2337](https://github.com/open-webui/open-webui/issues/2337)).
- `/app/models` takes 20–35 seconds to return, so login appears to fail before it succeeds.
- Misconfigured service URLs, which one report describes as a mix of user error and
  application error.

Four different root causes, one symptom, zero diagnostic surface. See
[#12396](https://github.com/open-webui/open-webui/issues/12396) and discussions
[#12316](https://github.com/open-webui/open-webui/discussions/12316),
[#9963](https://github.com/open-webui/open-webui/discussions/9963).

Goose went the other direction. Its `download_cli.sh` is roughly 1,500 lines — OS
detection, architecture detection, error handling, PATH management. That is a very large
amount of code whose entire job is making one command work on a stranger's machine.

### Why it happened

The blank screen is not a bug, it's an architectural consequence. When the frontend is a
separate SvelteKit app that boots and *then* asks the backend for state, every backend
problem becomes the same frontend symptom: nothing rendered. The UI has no vocabulary for
"the backend is slow" versus "the backend is misconfigured" versus "the backend is fine but
the DB isn't ready," because at render time it hasn't heard from the backend at all.

Goose's 1,500-line installer is the same lesson learned in the opposite direction: the
install path is where the most environmental variance meets the least user patience, so it
gets a disproportionate share of the defensive code.

### What this means for Kitty

Kitty is local-first single-user, so it has the same shape of exposure: a Next.js UI in
`gateway/kitty-chat/` that boots and then asks the FastAPI gateway for state. The failure
mode is available to us.

The lesson is not "build an onboarding wizard" — Kitty already has a multi-step
`OnboardingModal`. The lesson is that **the loading state needs to distinguish causes**.
A spinner that can say "gateway not responding" vs "gateway up, models loading" vs "no
models configured" is worth more than a slideshow, and it's less code.

---

## Theme 2 — Streaming is a rendering problem, not a networking problem

### The evidence

This is the strongest cross-project pattern in the research, and it shows up as three
apparently unrelated bugs that share one root cause.

**Open WebUI [#21348](https://github.com/open-webui/open-webui/issues/21348)** — 50 comments,
12 reactions. In v0.8.0, reasoning traces rendered as many separate visual fragments and
slowed the browser "to a halt." The reporter's own diagnosis: rendering "possibly split at
each token output." Closed Feb 13 2026.

**Open WebUI [#23990](https://github.com/open-webui/open-webui/issues/23990)** — 27 comments,
39 reactions. Scrolling up through a conversation jumps erratically. Firefox only, not
Chromium. The console says scroll-anchoring was disabled due to excessive adjustments, and
warns about scroll-linked positioning effects conflicting with async panning.

**The general case**, from outside these repos: when a response has grown to 2,000 words
across 200 renders, re-parsing the whole markdown body and diffing hundreds of DOM nodes on
every token produces jitter, scroll stutter, and visible jank. Sources:
[tigerabrodi](https://tigerabrodi.blog/how-to-build-a-performant-ai-markdown-renderer),
[The Prompt Bench](https://thepromptbench.com/ai-product-ux/streaming-ui-patterns-that-dont-break/).

### Why it happened

These are the same bug wearing different hats. Per-token DOM mutation causes layout thrash;
layout thrash defeats the browser's scroll anchoring; defeated scroll anchoring is what the
user experiences as "scrolling jumps around." Open WebUI's #23990 is Firefox-only not
because Firefox is broken but because Firefox's scroll anchoring gives up loudly where
Chromium's degrades quietly.

The deeper reason is that markdown is a *whole-document* format being fed a *stream*. Tokens
arrive slicing markdown mid-syntax — unclosed code fences, half-written bold markers,
partial list items. The naive renderer re-parses everything on every chunk, which is both
slow and visually wrong (formatting flickers as the parser changes its mind).

Worth noting the counter-evidence: for chat-length content, markdown parsing is genuinely
fast — under 5ms for a 5KB message. So the naive approach survives a long time in
development and only collapses under long reasoning traces. **That's why this ships broken
so often.** It works on every message you test with.

### What this means for Kitty

Three concrete rules, in cost order:

1. Memoize the message body so streaming one message doesn't recompute the conversation list.
2. Buffer incomplete markdown structures — defer a code block until its closing fence
   arrives, showing a streaming indicator inside it instead of re-parsing a broken fence
   200 times.
3. Reasoning traces are the stress case, not the normal case. If Kitty renders them, they
   need to be append-only or virtualized. Open WebUI shipped this broken to 146k stars'
   worth of users.

If we test streaming with short answers only, we will ship #21348.

---

## Theme 3 — Configuration is a product surface, and YAML is not a UI

### The evidence

LibreChat configures through `librechat.yaml`, and the recurring complaints are not about
what it can express but about how it fails:

- The `version` field is required by the schema but was omitted from the docs.
- Arbitrary keys aren't allowed under `endpoints` — you must use `custom` — which the docs
  didn't make clear ([#10514](https://github.com/danny-avila/LibreChat/discussions/10514)).
- The `models` field is structured inconsistently across examples.
- The file frequently doesn't mount correctly under Docker despite users following the
  startup guide ([#3755](https://github.com/danny-avila/LibreChat/discussions/3755),
  [#5162](https://github.com/danny-avila/LibreChat/discussions/5162)).
- A discussion titled, plainly, "Fix the librechat.yaml file in the main repository"
  ([#2487](https://github.com/danny-avila/LibreChat/discussions/2487)).

### Why it happened

Every one of these is a *validation and error-message* failure, not a design failure. The
schema knows `version` is required; the user finds out from a stack trace. The schema knows
`endpoints` needs `custom`; the user finds out from a forum. The config system has all the
information needed to produce a good error and produces a bad one instead.

The Docker mount failures are worse, because a config that silently isn't loaded is
indistinguishable from a config that's loaded and ignored. The user debugs the wrong layer.

### What this means for Kitty

Kitty has config in several places. The transferable rule is: **a config system's error
messages are its actual user interface**, and they're usually written last by whoever is
most tired. Concretely — validate on load, name the file path in the error, say what was
expected and what was found, and fail loud when a config file that was expected isn't
found. That last one is already Kitty's non-negotiable #1; LibreChat is the case study for
why.

---

## Theme 4 — Extension ecosystems: the friction is the roadmap

### The evidence

This is the best-documented "why" in the entire survey, because Block wrote it down.

Before MCP, Goose's extension system required Python expertise and custom integration work
for every new tool. During a company restructuring, when Goose was actively helping teams
move faster, that inflexibility became the bottleneck to spreading it across Block.

Block reached out to Anthropic about the friction and found Anthropic was already building
the Model Context Protocol. Rather than keep patching custom Python integrations, Block
became a contributor to the spec before it shipped, and Goose became the first publicly
available MCP client. Goose now reaches 3,000+ tools through MCP. In November 2025 Block
donated Goose to the Agentic AI Foundation alongside Anthropic's donation of MCP.

Source: [Arcade.dev](https://www.arcade.dev/blog/goose-the-open-source-agent-that-shaped-mcp/).
One quote worth keeping: *"When new MCP features need a reference implementation, Goose is
often where they land first."*

### Why it matters

The sequence is the lesson. Block did not decide to adopt a standard because standards are
good. They hit a specific, dated, organizational bottleneck — extensions cost too much
engineering per tool — and went looking. The protocol adoption was downstream of a felt
cost.

The counterweight: MCP is not free. Open WebUI
[#20629](https://github.com/open-webui/open-webui/issues/20629) (23 comments, 23 reactions)
is an MCP server response failure, and MCP has its own security surface serious enough that
Goose's own docs published a piece on
[securing MCP](https://goose-docs.ai/blog/2025/03/31/securing-mcp/).

### What this means for Kitty

Kitty already runs MCP servers. The applicable lesson is the *ordering* one: don't add
extension infrastructure ahead of a felt cost. Block's payoff came from having a real
bottleneck to relieve. Adding integration surface before there's a specific thing being
integrated is how you get maintenance without leverage.

---

## Theme 5 — Regressions in the invisible path

### The evidence

Open WebUI [#25585](https://github.com/open-webui/open-webui/issues/25585) — 54 comments,
16 reactions — is the single most instructive bug in this research.

After upgrading v0.9.5 → v0.9.6, web search broke. But not visibly. The search *ran*. The
logs confirmed success: "added 9 items to collection web-search-...". The results were
retrieved and stored. They were simply never handed to the model. Every observable signal
said the feature worked. The answers were just quietly ungrounded.

The maintainer's pinned diagnosis: the legacy tool-calling path became incompatible with
v0.9.6, likely around collection scoping. Workaround was an env var
(`ENABLE_RETRIEVAL_UNSCOPED_COLLECTIONS=true`); the real fix was "~2 lines of code"; the
recommendation was to abandon the legacy path entirely.

Compare Open WebUI [#21564](https://github.com/open-webui/open-webui/issues/21564) — 42
comments, 38 reactions — where "Continue Response" generates a whole new response instead of
extending the existing one, and Edit doesn't modify the message. Same family: the feature
appears to do something, so the user can't tell it's wrong without checking the output
carefully.

### Why it happened

Two lines of code, 54 comments. That ratio is the story. The bug was cheap to fix and
expensive to *find*, because the failure had no symptom on the path anyone was watching. A
success log fired. A collection was populated. The only evidence of failure was the model's
answer being subtly worse, which is the least reliable signal in the entire system.

The legacy-path detail matters too: this broke in the code path that was still supported but
no longer exercised. Dual paths rot asymmetrically — the one you use gets tested by usage,
the one you keep for compatibility gets tested by nobody.

### What this means for Kitty

This is the theme most directly aimed at us, because Kitty's storage layer is mid-migration
and has exactly this shape: reads are supposed to go through `gateway/memory_graph.py`,
writes still go direct to stores until Phase B's write-side router lands. That's a dual
path.

(This paragraph originally added that a refactor on `gateway-packages` had just moved those
modules into subpackages. That refactor was abandoned and the branch rewound the same day,
so the observation no longer describes the tree. The dual-path point stands on its own.)

Two rules fall out:

1. **A success log is not evidence the data arrived.** "Stored 9 items" and "the model saw 9
   items" are different assertions. If only the first is logged, the second can fail
   silently for a release cycle. Assert on the consuming end.
2. **Retrieval needs an end-to-end check, not a unit test per stage.** Every stage of
   #25585 passed its own test. The handoff between stages is where it broke.

---

## Theme 6 — What users ask for, ranked

Feature requests sorted by reactions are a decent proxy for felt pain. The top of the
LibreChat list is not what a feature roadmap usually prioritizes:

| Request | Reactions | Comments |
|---|---|---|
| [Chat folders / projects](https://github.com/danny-avila/LibreChat/issues/4848) | 176 | 58 |
| [Admin user management](https://github.com/danny-avila/LibreChat/issues/3137) | 113 | 56 |
| [Agent skills support](https://github.com/danny-avila/LibreChat/issues/11106) | 72 | 27 |
| [Show conversation cost](https://github.com/danny-avila/LibreChat/issues/1215) | 69 | 36 |

The #1 request by a wide margin is *organizing conversations you already have* — folders,
plus projects carrying shared files and system prompts, with the requester citing Claude's
projects as the model. Not a new capability. Filing.

Cost visibility at #4 is the other notable one: people want to know what a conversation cost
them, and 69 people cared enough to react.

**Honest limit:** I verified the numbers and the request content for all four, but I did not
read the full comment threads, so I can't report maintainer reasoning on why these took as
long as they did. The GitHub API summary for #1215 showed no maintainer explanation of
difficulty. Treat this table as demand signal, not as design rationale.

### What this means for Kitty

Kitty is single-user, so admin user management is irrelevant and folders matter less than
they do at LibreChat's scale. Cost visibility does transfer directly — Kitty routes through
LiteLLM and already tracks spend, so surfacing per-conversation cost is mostly a display
problem. Given it's a top-5 ask across a 41k-star project, that's cheap signal to act on.

---

## Theme 7 — Architecture convergence

Not a pain point, just an observation worth recording.

- **Open WebUI**: SvelteKit (Svelte 5, TypeScript) frontend, FastAPI backend, backend serves
  the compiled frontend from the same host to simplify deployment.
- **Khoj**: monolithic Django + FastAPI backend on a shared database, with search, sandbox,
  and automation decoupled as HTTP services. Notable pattern: an LLM adapter layer for
  provider portability.
- **Kitty**: FastAPI gateway, Next.js UI, LiteLLM for routing.

Everyone landed on Python/FastAPI for the backend and a JS framework for the UI, with a
provider-abstraction layer in between. Kitty's LiteLLM proxy is the same idea as Khoj's
adapter pattern, bought instead of built.

The deployment detail is the interesting one: Open WebUI serves the built frontend from the
backend host specifically to cut infrastructure complexity. That's a deliberate trade of
dev-time convenience for install-time simplicity — and given Theme 1, they still didn't buy
enough of it.

Sources: [DeepWiki architecture overview](https://deepwiki.com/open-webui/open-webui/2-architecture),
[Khoj](https://github.com/khoj-ai/khoj).

---

## What I did not cover

Named so the next pass knows where to start:

- **Mobile UX.** No primary sources gathered. LibreChat reportedly has a dedicated mobile
  stylesheet (per the competitive notes that were in PLANS.md, since removed as stale) but I
  did not verify it or find reasoning.
- **Agent visibility / task management.** Theme identified in the handoff, no evidence
  collected. LibreChat [#11106](https://github.com/danny-avila/LibreChat/issues/11106) is
  the thread to start from.
- **Community sources.** Reddit, HN, and dev.to were in scope per the reframe. I used one
  independent technical blog (the markdown renderer piece) and otherwise stayed on primary
  GitHub sources and vendor blogs. HN threads on Open WebUI and Goose launches are unread.
- **Commit history and controversial PRs.** Also in scope, not done. Issue threads were the
  higher-yield source per unit of effort; commit archaeology is the deeper and slower dig.
- **Chatbot UI and AionUi** contributed nothing to this document. Both were in the survey
  set; neither surfaced material on these themes.

## The one-line version

Four of the seven themes are the same failure: **the system knew something the user didn't,
and didn't say it.** The blank screen knew the DB wasn't ready. The config loader knew
`version` was required. The web-search path knew it had 9 items. The "Continue Response"
button knew it was starting fresh. In every case the information existed one layer away from
the person who needed it.

That's the design handbook entry. Everything else here is detail.
