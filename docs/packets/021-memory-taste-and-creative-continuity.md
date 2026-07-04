# 021 — Memory Taste + Creative Continuity

**Status:** 📋 spec authored, not built
**Best executor:** Claude Code / Codex with Jacob review
**Intent:** make Kitty feel like a continuity assistant, not a recovery surveillance mirror.

## Why this exists

Jacob named the real product connection: Kitty, the daily brief, creative work, image prompts, writing, and project navigation are all variations of the same thing:

> help Jacob not lose the thread.

The current repo already has the technical spine for this: the gateway is the product, clients are thin views, context reads go through `memory_graph`, and the state/action spine is the near-term build path. But the memory/persona layer needs taste controls so Kitty does not over-index on the most emotionally intense facts forever.

This packet adds that missing layer: **memory should be consentful, scoped, decayed, and useful. Creativity should be an active relationship, not a separate hobby panel.**

## Product principle

Kitty should remember what helps Jacob continue:

- what he was building
- what was already decided
- what is unfinished
- what constraints matter
- what tone or approach has landed
- what he wants more of
- what he explicitly wants deprioritized

Kitty should not repeatedly foreground painful, medical, recovery, grief, or spiral context unless it is directly relevant, recently requested, safety-relevant, or explicitly pinned by Jacob.

The goal is not amnesia. The goal is **tasteful continuity**.

## Core thesis to encode

> Kitty is an attention-repair and continuity assistant for rebuilding days.

A more user-facing phrase:

> Kitty holds the thread: where you were, what matters, and the next small move.

This should inform memory, brief, project resume, creative mode, and the home surface.

## Files likely touched

- `config/SOUL.md`
- `soul/kitty.md`
- `soul/specialists/creative.md`
- `gateway/memory_graph.py`
- `gateway/context_assembler.py`
- `gateway/memory_consolidation.py`
- new: `gateway/memory_policy.py`
- tests around context assembly / memory graph / consolidation

## Files not to touch

- provider routing, LiteLLM, or `gateway/llm_client.py` except if tests need a harmless import
- action queue execution logic
- mail connector OAuth or Gmail fetch logic
- UI redesign work unrelated to displaying memory controls
- packet registry/order unless Jacob explicitly activates this packet

## Design rules

### 1. Memory has modes, not one personality soup

Add a small memory policy layer that classifies memory items into display/use modes:

- `pinned` — Jacob explicitly wants this remembered and surfaced when relevant
- `working_context` — active projects, current decisions, next steps, task state
- `preference` — tone, design, workflow, communication preferences
- `creative_thread` — recurring creative interests, motifs, project directions, aesthetic decisions
- `sensitive_support` — recovery, grief, health, benefits, shame, crisis, addiction, family/relationship pain
- `archived` — true but should rarely surface
- `blocked` — do not surface unless Jacob explicitly asks

No item should become a permanent identity lens just because it was emotionally intense.

### 2. Sensitive support context is opt-in at surfacing time

Sensitive material can exist in local storage, but context assembly should suppress it by default unless:

- the current user message directly asks about it
- Jacob has pinned it as active support context
- there is a safety-critical reason to include it
- the route is local-only and the response genuinely needs it

Even then, Kitty should use the smallest useful amount of context.

### 3. Memory needs decay and “not today”

Add support for soft suppression:

- `snooze_until`
- `last_surfaced_at`
- `surface_count`
- `decay_after_days`
- `user_verdict`: `helpful`, `too_much`, `wrong_focus`, `keep_quiet`, `pin`

This prevents one old theme from becoming the permanent center of future-Jacob.

### 4. Consolidation must not turn repeated spirals into identity

`gateway/memory_consolidation.py` currently summarizes clusters into durable “Jacob has been...” memories. That is useful for projects, preferences, and decisions, but risky for emotionally repetitive sessions.

Change consolidation prompts so they prefer:

- decisions made
- active projects
- constraints and preferences
- next steps
- what helped
- what Jacob wants less/more of

Avoid durable summaries like:

- “Jacob has been spiraling about...”
- “Jacob has been focused on recovery...”
- “Jacob keeps struggling with...”

Unless Jacob explicitly asks to store a recovery-related pattern, recovery details should be summarized as **support preferences**, not identity labels.

Better pattern:

> Jacob prefers future support to stay practical and positive around recovery unless he explicitly asks for a deeper recovery frame.

### 5. Creativity is not a separate compartment

Creative mode should not only generate drafts or brainstorms. It should help Jacob keep creative threads alive across time.

Add the concept of a `creative_thread` memory:

- project: Kitty / poem / painting / image workflow / mascot / music
- motif: attention repair, continuity, not losing the light, imperfect warmth, badly drawn cat, recovery without branding everything as recovery
- current edge: what is being explored now
- next tiny move: the smallest continuation
- aesthetic constraints: what to preserve / avoid

Creative relationship model:

- Jacob supplies emotional truth, taste, contradiction, and sparks.
- Kitty reflects patterns, preserves decisions, offers directions, and brings back unfinished threads at the right moment.
- Kitty does not turn creativity into productivity sludge.
- Kitty does not over-polish away weirdness, vulnerability, humor, or edge.

### 6. Home surface should show “the thread,” not “the psyche”

When this reaches UI, memory should appear as continuity cards, not psych labels.

Possible cards:

- **Continue** — the project/thread Jacob was last working on
- **Decision kept** — a recent settled choice worth preserving
- **Creative spark** — one unfinished creative thread worth returning to
- **Useful constraint** — something that protects the work
- **Quiet memory** — something Kitty knows but is intentionally not foregrounding

Do not show a dashboard of diagnoses, spirals, relapse risk, or emotional analytics unless Jacob explicitly opts into a support mode.

## Implementation sketch

### Step 1 — Add `gateway/memory_policy.py`

Functions:

- `classify_memory_item(item: Item, query: str) -> MemoryClass`
- `should_surface(item: Item, query: str, mode: str = "default") -> bool`
- `rewrite_sensitive_summary(text: str) -> str`
- `memory_display_reason(item: Item, query: str) -> str`

Keep it simple and rule-based first. No new memory substrate.

### Step 2 — Filter in `context_assembler`

Before `_format_memory_block`, run graph results through `memory_policy.should_surface(...)`.

Preserve raw `memory_items` in `ContextBundle` for debugging/tests, but only filtered items enter the system prompt.

### Step 3 — Update consolidation prompt

Revise `_summarize_cluster` so it asks for durable continuity facts, not psych summaries.

Prompt should say:

- capture decisions, preferences, active threads, constraints, next steps
- avoid turning distress/recovery repetition into identity
- if the cluster is sensitive, summarize only the support preference or concrete next step
- return `NO_DURABLE_MEMORY` if there is nothing useful to remember

### Step 4 — Update SOUL wording

Patch `config/SOUL.md` and/or `soul/kitty.md` so Kitty explicitly understands:

- memory is for continuity, not surveillance
- use remembered sensitive context sparingly
- do not make recovery the default lens
- creativity is a living thread Kitty helps preserve
- Jacob remains the director of what matters

Suggested replacement for the current memory spirit:

> Remember like a good collaborator, not like a case file. Keep the thread: decisions, projects, preferences, constraints, and unfinished sparks. Sensitive history is not the center of Jacob unless he makes it the center today. When in doubt, surface the next useful move, not the deepest backstory.

### Step 5 — Update creative specialist

Add a section: “Creative continuity.”

It should say creative mode should:

- preserve Jacob’s taste and constraints
- return to unfinished motifs without forcing them
- help convert sparks into small finished artifacts
- keep weirdness and emotional truth intact
- avoid treating creativity as mere productivity

## Acceptance criteria

1. Sensitive/recovery memories do not appear in assembled context for unrelated queries.
2. Active project, preference, and creative-thread memories still appear when relevant.
3. A memory item marked/patterned as `blocked` or `keep_quiet` is suppressed unless directly requested.
4. Consolidation can return `NO_DURABLE_MEMORY` and does not store a memory in that case.
5. Consolidation tests prove emotionally repetitive traces become support preferences or no memory, not identity summaries.
6. SOUL docs encode “continuity, not surveillance.”
7. Creative specialist docs encode creativity as thread-preservation + co-creation, not just generation.
8. No new database, vector store, event bus, agent framework, or UI rebuild is introduced.

## Suggested tests

- `tests/test_memory_policy.py`
  - project memory surfaces for project query
  - creative memory surfaces for creative query
  - recovery memory suppressed for unrelated project query
  - recovery memory surfaces for direct recovery query
  - blocked memory suppressed even when weakly related

- `tests/test_context_assembler_memory_policy.py`
  - assembled `system` excludes sensitive support item for neutral query
  - `ContextBundle.memory_items` still includes raw items for audit/debug if current design wants that

- `tests/test_memory_consolidation_policy.py`
  - `NO_DURABLE_MEMORY` skips `_store_memory`
  - repeated distress snippets become a support-preference summary, not “Jacob is/keeps...”

## Non-goals

- Building a therapist mode
- Building a recovery expert pack
- Adding user-facing analytics about Jacob’s mental state
- Reworking the whole memory system
- New model routing
- New UI beyond optional tiny display labels
- Making creativity into gamification

## Jacob review questions before build

1. What memory categories should be visible in the UI?
2. What should be completely quiet unless asked?
3. Does “creative thread” feel right, or should it be called something else?
4. Should “quiet memory” be visible as a concept, or only used internally?
5. What is the default setting for recovery/support context: `quiet`, `only when asked`, or `support mode only`?

## One-line build instruction

Implement a tiny memory policy layer that makes Kitty remember for continuity, suppress sensitive context by default, and preserve creative threads as living project context without adding new architecture.
