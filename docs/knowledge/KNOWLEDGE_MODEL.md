---
type: model
title: "Kitty Knowledge Model"
status: draft
owner: jacob
primary_purpose: Canonical semantic model for organizational knowledge — every subsystem must use this vocabulary consistently
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
  - docs/architecture/REFERENCE_ARCHITECTURE.md
implements:
  - docs/adr/0019-knowledge-model-prerequisite.md
review_cycle: quarterly
---

# Kitty Knowledge Model

## 1. Purpose

Everything in Kitty ultimately exists to improve decisions. The Knowledge Model defines the language the repository uses to describe reality. It is not a database schema. It is not a graph implementation. It is not a vector index. This document defines the meaning of information regardless of how it is stored. If two subsystems disagree about what "Knowledge" means, the architecture has already failed.

## 2. Core Philosophy

Kitty does not store information. Kitty transforms experience into increasingly reliable judgment. Every object in the system exists somewhere on that journey:

Reality → Evidence → Observations → Findings → Knowledge → Patterns → Judgment → Decisions → Outcomes → Reflection → Improved Judgment

Nothing skips layers without justification.

## 3. First-Class Knowledge Objects

### Reality
Exists independently of Kitty. Never modified by the Knowledge System. Only observed.

### Evidence
An observable, immutable fact. Answers "What happened?" Immutable, attributable, timestamped, traceable. Knowledge without evidence becomes opinion.

### Observation
Describes evidence without interpretation. Intentionally neutral. "Packet 027 required three implementation retries" — not "Builder struggles with retries."

### Finding
A supported interpretation. Unlike observations, findings introduce explanation. Every finding must reference supporting observations.

### Knowledge
A finding that has survived review. Answers "What do we currently believe?" Reviewable, versioned, supersedable, confidence-scored. Not permanent — evolves as new evidence arrives.

### Pattern
Knowledge observed repeatedly. Patterns predict future behavior. Stronger than individual knowledge because they generalize across instances.

### Doctrine
Organizational policy derived from validated patterns. Normative. Answers "How should we behave?" Changes rarely. Requires deliberate governance.

### Judgment
The application of doctrine and knowledge to a specific context. Dynamic — cannot simply be stored. Kitty does not store judgment. Kitty stores the inputs that make good judgment more likely.

### Decision
A specific choice made within a context. The recorded artifact of judgment. Should reference evidence, doctrine, and reasoning.

### Outcome
The measurable result of a decision. Validates or invalidates prior judgment.

### Reflection
Compares expectations with outcomes. Without reflection there is no organizational learning. Reflection turns failure into knowledge.

## 4. Engineering Objects

**Mission** — Permanent organizational objective. Current: Reduce Uncertainty, Reduce Activation Energy, Compound Organizational Judgment.
**Capability** — Something Kitty can reliably accomplish. Backed by evidence.
**Initiative** — A coordinated effort to improve capabilities. Spans multiple packets.
**Packet** — The smallest independently reviewable engineering unit. One branch, one PR.
**Receipt** — A machine-readable record describing what occurred. Evidence, not knowledge.

## 5. Confidence Model

| Level | Meaning |
|---|---|
| Experimental | Single source, unvalidated |
| Candidate | Multiple supporting observations, requires review |
| Accepted | Reviewed, actively used |
| Established | Validated repeatedly over time |
| Superseded | Historically valuable, no longer authoritative |

## 6. Lifecycle

Evidence → Observation → Finding → Knowledge → Pattern → Doctrine (optional; most knowledge should not become doctrine) → Superseded

Each stage is a gate. Nothing skips stages without explicit justification.

## 7. The Learning Loop

Evidence feeds knowledge. Knowledge and doctrine inform decisions. Decisions produce outcomes. Outcomes trigger reflection. Reflection updates knowledge and, when warranted, doctrine. Every completed initiative should feed this loop.

## 8. Repository Rules

Never confuse: Evidence with knowledge. Knowledge with doctrine. Doctrine with implementation. Implementation with outcomes.

## 9. Anti-Patterns

Calling everything Knowledge. Skipping validation. Storing knowledge without provenance. Confusing product entities with knowledge entities. Codifying judgment without repetition. Treating superseded knowledge as waste.

## 10. Semantic Alignment (Existing Codebase)

The Knowledge Model is a semantic specification. The runtime codebase evolved independently. The following clarifies how existing code concepts map to Knowledge Model terms:

| Code Concept | Code Location | Knowledge Model Equivalent | Notes |
|---|---|---|---|
| `KNOWLEDGE_DIR` | `gateway/paths.py` | Evidence (storage path) | Name retained for compatibility; see docstring |
| `Source.KNOWLEDGE` | `gateway/memory_graph.py` | Evidence (ChromaDB index) | Search category, not semantic level; see docstring |
| `"knowledge"` search key | `gateway/search.py` | Evidence (retrieval) | ChromaDB-stored documents as search results |
| `knowledge routes` | `gateway/routes/knowledge.py` | Evidence ingestion | API surface for document pipeline |
| `journal "reflection"` theme | `gateway/journal.py` | Personal journaling | User-facing, not architectural Reflection |

No runtime abstractions exist for: Doctrine, Pattern, Judgment, Receipt, Outcome, Finding, Observation. These are defined in this model as semantic targets for future implementation. Do not implement them prematurely.
