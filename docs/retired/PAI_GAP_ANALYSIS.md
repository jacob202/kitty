# Kitty vs. PAI — Gap Analysis

**Date:** 2026-06-08
**Subject:** Daniel Miessler's [Personal AI Infrastructure (PAI)](https://github.com/danielmiessler/Personal_AI_Infrastructure) compared against Kitty
**Purpose:** Identify concrete ideas worth stealing from PAI, ranked by value.

---

## Update (2026-06-08): decision & what shipped

**Strategic decision: lift PAI's patterns, do NOT fork it.** PAI is a TypeScript/Bun layer that runs *inside* Claude Code and is Anthropic-model-centric; Kitty is a standalone, model-agnostic, local-first Python app. Forking would inherit Anthropic lock-in and discard Kitty's working voice/telegram/integration code + tests. So we lift PAI's *portable markdown assets* and adapt them to Kitty's conventions (stripping PAI cruft: `~/.claude/PAI` paths, `localhost:31337` voice hooks, `{PRINCIPAL.NAME}` vars).

**Shipped in this PR:**
- **TELOS user-identity** (`config/USER/*.md` templates + `gateway/user_context.py`), injected into every system prompt via `context_builder.get_system_prompt()`. Closes the #1 gap (Kitty had no model of *who Jacob is*).
- **8 reasoning/spec skills lifted verbatim** (cruft-stripped) into `.agents/skills/`: `first-principles`, `systems-thinking`, `red-team`, `iterative-depth`, `root-cause-analysis`, `extract-wisdom`, `science-method`, and `isa` (the Ideal State Artifact spec + examples). Auto-discovered by `skill_registry`.

**Deferred to follow-up PRs (touch working code — need sign-off):** typed knowledge graph, ISA→verifier wiring, explicit Algorithm phases.

### Adjacent tools evaluated
- **TurboVec** (compressed ANN index): **DEFER.** Its win is RAM/latency at millions of docs; Kitty is personal-scale and ChromaDB already gives documents+metadata+persistence. Revisit behind `memory_graph`'s `StoreAdapter` only if the KB grows huge.
- **MemPalace** (local-first semantic memory + typed knowledge graph w/ temporal validity): **strong candidate, Phase 4.** Recommended as the *vehicle* for the typed-knowledge-graph gap — embedded behind `memory_graph`'s `StoreAdapter`, not run as a separate sidecar service.

---

## TL;DR

Kitty and PAI are close cousins. Both are local-first, filesystem-as-database, persona-driven personal AI systems built on Claude Code. Kitty is **ahead** on voice, model-agnostic routing, mood/companion state, and external-world context (calendar, weather, iMessage, health). PAI is **ahead** on three things Kitty largely lacks:

1. **A user-identity layer** (TELOS) — Kitty knows *who Kitty is* but not *who Jacob is*.
2. **Explicit success criteria** (ISA/ISC) — Kitty defines "done" implicitly ("tests pass"); PAI codifies it per task.
3. **A typed knowledge graph** — Kitty has 5 memory stores but only counts cross-store correlations; PAI links typed entities.

The single highest-leverage borrow is **TELOS**, because it's cheap, missing entirely, and multiplies the value of everything Kitty already built.

---

## Methodology

We mapped Kitty's actual implementation (verified against `gateway/`, `config/`, `.agents/`) onto PAI's 10 core concepts. Status is one of **HAS IT** / **PARTIAL** / **MISSING**.

| # | Concept | Kitty status | Key Kitty file(s) |
|---|---------|:---:|---|
| 1 | User Identity / TELOS | **MISSING** | — (only hard-coded `USER_ID="jacob"` in `memory.py:11`) |
| 2 | Ideal State / Success Criteria | **PARTIAL** | `verifier.py`, `builder.py`, `task_runner.py` |
| 3 | Structured Problem-Solving Loop | **PARTIAL** | `builder.py`, `agent_runner.py`, `council_graph.py` |
| 4 | Memory Tiers / Typed Graph | **PARTIAL** | `memory_graph.py`, `memory.py`, `knowledge.py`, `journal.py` |
| 5 | Skills as Code-at-Center | **PARTIAL** | `skill_registry.py`, `plugin_registry.py`, `.agents/skills/` |
| 6 | Self-Improvement from Signals | **PARTIAL** | `self_review.py`, `learning.py`, `buddy.py` |
| 7 | Hooks / Event-Driven Integrations | **MISSING** | `plugin_registry.py` (field defined, no dispatcher) |
| 8 | Life Dashboard ("Pulse") | **PARTIAL** | `DashboardHome.tsx`, `brief.py`, `buddy.py` |
| 9 | Voice / DA Persona | **HAS IT** | `voice_pipeline.py`, `buddy.py`, `SOUL.md` |
| 10 | Model-Agnostic Routing | **HAS IT** | `llm_client.py`, `domain_router.py` |

---

## Ideas worth stealing — ranked by value

Ranked by **(impact × fit) ÷ cost**. Each item notes the PAI source concept, the Kitty gap, and a concrete first step.

### 🥇 1. TELOS — a user-identity store (HIGH impact, LOW cost)

**PAI source:** Paired `PRINCIPAL_IDENTITY` + `DA_IDENTITY` files in `PAI/USER/`, populated by an `/interview` wizard. TELOS sections: *Mission, Goals, Beliefs, Wisdom, Challenges, Books, Mental models, Narratives.* Identity is articulated **first**, then everything else optimizes against it.

**Kitty gap:** `config/SOUL.md` is Kitty's identity. There is **no equivalent file for Jacob**. The system knows the user by the constant `USER_ID="jacob"` and whatever episodic facts mem0 has absorbed — but no stated mission, goals, values, current problems, or life-context. Every prompt is built without a north star for *the human*.

**Why it's #1:** It's the cheapest high-impact change. A single markdown file (`config/USER.md` or `config/TELOS.md`) injected as a new step in `context_builder.py` would let *every* surface — brief, chat, voice, nudges, agent tasks — reason against Jacob's actual goals instead of inferring them. It also multiplies the value of features Kitty already shipped (nudge engine, brief, patterns) by giving them a reference frame.

**First step:** Create `config/USER.md` with TELOS sections; add a context-builder step that injects it (mirror how `SOUL.md` is loaded). Optionally a `/interview` flow later (Kitty already has a journal interview pattern in `journal.py`).

---

### 🥈 2. Ideal State Criteria (ISC) for agent tasks (HIGH impact, MEDIUM cost)

**PAI source:** The **ISA (Ideal State Artifact)** — a 12-section PRD-like format (Problem → Vision → Out of Scope → Principles → Constraints → Goal → Criteria → Test Strategy → Features → Decisions → Changelog → Verification). The **Criteria** section holds ISCs that *double as verification items* — the system "hill-climbs toward ideal state" by decomposing into discrete, checkable criteria.

**Kitty gap:** `task_runner.py` tasks carry a free-text `goal` but no structured success criteria. `verifier.py` defines success implicitly as "pytest passes" and "a reviewer approves." There is no stored, per-task definition of *what done looks like* that verification checks against.

**Why it matters:** This closes Kitty's biggest agent-loop weakness — tasks succeed/fail on a proxy (tests green) rather than on whether they actually achieved the goal. Even a lightweight version (3–5 explicit success criteria attached to each task, checked at the verify stage) would make `builder.py` and `agent_runner.py` meaningfully more reliable.

**First step:** Add an optional `success_criteria: list[str]` to the task schema in `task_runner.py`; have the PLAN stage of `builder.py` propose them and the VERIFY stage in `verifier.py` check each one. Skip the full 12-section ISA — adopt only the Criteria-as-verification idea.

---

### 🥉 3. Typed knowledge graph (MEDIUM-HIGH impact, HIGH cost)

**PAI source:** The **KNOWLEDGE** memory tier is a *typed graph* of `People, Companies, Ideas, Research, Blogs` — entities with relationships, not flat notes. Routing decisions use the graph.

**Kitty gap:** `memory_graph.py` is a strong facade over 5 stores (memory, knowledge, journal, traces, todos), but `correlate()` only returns **counts** ("3 related journal entries"). There are no typed entities and no edges linking them ("task X relates to person Y via project Z"). `KnowledgeMetadata` is flat.

**Why it's lower:** High value long-term, but expensive and partially redundant with Kitty's existing vector search + correlation. The deep-module pattern in `memory_graph.py` is the right place to grow this incrementally rather than rebuild.

**First step:** Don't boil the ocean. Add one entity type (e.g. `Person`) with typed edges to existing store items, surfaced through a new `memory_graph` adapter. Measure whether it improves context before expanding to 5 entity types.

---

### 4. Self-improvement that closes the loop (MEDIUM impact, MEDIUM cost)

**PAI source:** Signals (explicit ratings, sentiment, **verification outcomes**, satisfaction) flow back and *auto-tune the system*. "The system that runs the work is also the system that gets better at running it."

**Kitty gap:** Kitty already *captures* rich signals — `self_review.py` logs drift, reactions, and session arc; `buddy.py` tracks mood. But the loop is **open**: signals land in `SOUL_SCRATCHPAD.md` for **manual** review before anything changes. Nothing auto-tunes.

**Why it matters:** Kitty has done the hard 80% (signal capture). The missing 20% is a safe automated feedback path. Tie verification outcomes from idea #2 into `learning.py` so the system tracks which task patterns succeed.

**First step:** Once ISCs (#2) exist, log ISC hit-rate per task type and surface it; defer any automatic prompt mutation until trust is established.

---

### 5. A real hooks/event system (MEDIUM impact, MEDIUM cost)

**PAI source:** 37 event-driven hooks; "OBSERVABILITY" memory logs every tool call + hook firing + satisfaction signal.

**Kitty gap:** `plugin_registry.py` *defines* a `hooks` field (line 37, 52) but no dispatcher exists. Kitty has FastAPI middleware and OpenWebUI `__event_emitter__` streaming, but no general domain-event bus.

**Why it's mid-pack:** Enabling tech, not user-facing value on its own. Worth it only once there are multiple subscribers (it would cleanly power #4's signal capture and the nudge engine).

**First step:** Implement a minimal in-process event bus that `plugin_registry.py` hooks subscribe to; emit a few core events (task_completed, drift_detected, brief_generated).

---

### 6. Skills as code-at-center (LOW-MEDIUM impact, MEDIUM cost) — *evaluate, don't rush*

**PAI source:** Hierarchy is `code → CLI → workflows → SKILL.md`. "Prompts wrap code; code doesn't wrap prompts." Determinism first.

**Kitty gap:** `skill_registry.py` loads `SKILL.md` instruction cards (frontmatter: name, description, when_to_use, allowed_tools) that the LLM reads and executes manually — prompts wrap *nothing*. No deterministic execution engine.

**Verdict:** Philosophically appealing but a large refactor with unclear ROI for Kitty's current scope. Kitty's modules (`weather.py`, `calendar_integration.py`, etc.) are *already* code-at-center — they just aren't exposed through the skill abstraction. Consider unifying these later; not a near-term win.

---

## What Kitty already does better than PAI

Worth stating, so we don't regress chasing parity:

- **Voice pipeline** — `voice_pipeline.py` is a complete deep-module STT→LLM→TTS→gate loop with companion mood (`buddy.py`). PAI has voice *announcements*; Kitty has a voice *conversation channel*.
- **Model-agnostic routing with fallback** — `llm_client.py`'s LiteLLM→OpenRouter→Gemini→NVIDIA chain is more robust than a single classifier.
- **External-world context** — calendar, weather, iMessage, ambient app detection, health (Phase 3). PAI has less ambient integration.
- **Companion/mood state** — `buddy.py` persistent mood + drift is distinctive and not a PAI focus.

---

## Recommended sequence

1. **TELOS** (`config/USER.md` + context-builder injection) — do this first; days of work, multiplies everything.
2. **ISCs on tasks** — biggest reliability win for the agent loop.
3. **Close the self-improvement loop** using ISC outcomes — builds directly on #2.
4. **Event bus**, then **typed graph** — enabling infrastructure, only once #1–#3 prove their value.
5. Leave **skills-as-code** as a deliberate non-goal for now.

---

*Source for PAI details: project README and repo structure (v5.0.0 / Algorithm v6.3.0). Kitty status verified against the current `claude/personal-ai-infrastructure-w0b17o` branch.*
