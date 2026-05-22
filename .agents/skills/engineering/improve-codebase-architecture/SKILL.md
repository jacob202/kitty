---
name: improve-codebase-architecture
description: Find deepening opportunities in a codebase, informed by Kitty's domain language in docs/ARCHITECTURE.md and CLAUDE.md. Use when the user wants to improve architecture, find refactoring opportunities, consolidate tightly-coupled modules, or make a codebase more testable and AI-navigable.
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities** — refactors that turn shallow modules into deep ones. The aim is testability and AI-navigability.

## Glossary

Use these terms exactly in every suggestion. Consistent language is the point — don't drift into "component," "service," "API," or "boundary." Full definitions in [LANGUAGE.md](LANGUAGE.md).

- **Module** — anything with an interface and an implementation (function, class, package, slice).
- **Interface** — everything a caller must know to use the module: types, invariants, error modes, ordering, config. Not just the type signature.
- **Implementation** — the code inside.
- **Depth** — leverage at the interface: a lot of behaviour behind a small interface. **Deep** = high leverage. **Shallow** = interface nearly as complex as the implementation.
- **Seam** — where an interface lives; a place behaviour can be altered without editing in place. (Use this, not "boundary.")
- **Adapter** — a concrete thing satisfying an interface at a seam.
- **Leverage** — what callers get from depth.
- **Locality** — what maintainers get from depth: change, bugs, knowledge concentrated in one place.

Key principles (see [LANGUAGE.md](LANGUAGE.md) for the full list):

- **Deletion test**: imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.**
- **One adapter = hypothetical seam. Two adapters = real seam.**

This skill is _informed_ by the project's domain model. Kitty's architecture docs and module names give names to good seams; existing docs record decisions the skill should not re-litigate.

## Kitty grounding (read first)

Before exploring, read:

| Doc | Purpose |
|-----|---------|
| `docs/ARCHITECTURE.md` | Live stack, ports, package layout |
| `CLAUDE.md` | Module map, routing rules, test commands |
| `gateway/paths.py` | Path constants — all storage paths flow from here |
| `docs/CONTEXT_ENGINEERING.md` | How context is assembled and injected |

**Domain vocabulary:** use names from `gateway/` — e.g. `context_builder`, `memory_graph`, `StorageRouter`, `buddy`, `skill_registry` — not generic handler names.

**Recorded decisions:** Kitty has no formal ADR directory yet. Treat existing docs under `docs/` as load-bearing unless the user says otherwise. When a rejection deserves permanence, offer to add `docs/adr/NNNN-title.md` using [ADR-FORMAT.md](ADR-FORMAT.md).

## Process

### 1. Explore

Read the Kitty grounding docs above, then walk the codebase. Use the Task tool (`subagent_type=generalPurpose` or `ce-repo-research-analyst`) for broad exploration. Note where you experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow** — interface nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called (no **locality**)?
- Where do tightly-coupled modules leak across their seams? (e.g. direct backend imports instead of `StorageRouter`)
- Which parts of the codebase are untested, or hard to test through their current interface?

Apply the **deletion test** to anything you suspect is shallow: would deleting it concentrate complexity, or just move it? A "yes, concentrates" is the signal you want.

### 2. Present candidates

Present a numbered list of deepening opportunities. For each candidate:

- **Files** — which files/modules are involved
- **Problem** — why the current architecture is causing friction
- **Solution** — plain English description of what would change
- **Benefits** — explained in terms of locality and leverage, and also in how tests would improve

**Use Kitty domain vocabulary** (from `docs/ARCHITECTURE.md` and `CLAUDE.md`) **and [LANGUAGE.md](LANGUAGE.md) vocabulary for the architecture.** Talk about "the memory_graph unified query module" — not "the FooBarHandler," and not "the Memory service."

**Doc conflicts**: if a candidate contradicts an existing doc, only surface it when the friction is real enough to warrant revisiting. Mark it clearly (e.g. _"contradicts docs/ARCHITECTURE.md — but worth reopening because…"_). Don't list every theoretical refactor existing docs forbid.

Do NOT propose interfaces yet. Ask the user: "Which of these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, drop into a grilling conversation. Walk the design tree with them — constraints, dependencies, the shape of the deepened module, what sits behind the seam, what tests survive.

Side effects happen inline as decisions crystallize:

- **Naming a deepened module after a concept not yet in docs?** Add a short definition to `docs/ARCHITECTURE.md` or a new `docs/CONTEXT.md` using [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md). Create `docs/CONTEXT.md` lazily if it doesn't exist.
- **Sharpening a fuzzy term during the conversation?** Update the relevant doc right there.
- **User rejects the candidate with a load-bearing reason?** Offer an ADR at `docs/adr/NNNN-title.md`, framed as: _"Want me to record this as an ADR so future architecture reviews don't re-suggest it?"_ Only offer when the reason would actually be needed by a future explorer — skip ephemeral reasons ("not worth it right now") and self-evident ones. See [ADR-FORMAT.md](ADR-FORMAT.md).
- **Want to explore alternative interfaces for the deepened module?** See [INTERFACE-DESIGN.md](INTERFACE-DESIGN.md).
