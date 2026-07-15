---
type: architecture
title: "Kitty Capability Model"
status: draft
owner: jacob
primary_purpose: Define every permanent capability Kitty may possess, independent of implementation — the bridge between architecture and implementation
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
  - docs/architecture/REFERENCE_ARCHITECTURE.md
  - docs/architecture/ORGANIZATIONAL_MODEL.md
review_cycle: quarterly
---

# Kitty Capability Model

## Purpose

Capabilities describe what Kitty is able to accomplish. They do not describe implementations, user interfaces, technologies, models, or providers. Capabilities are stable. Implementations are replaceable.

A capability is a repeatable organizational ability that produces measurable value. "Execute Builder Packets" is a capability. "Use OpenCode" is not.

## Capability Lifecycle

Proposed → Designed → Experimental → Operational → Optimized → Core → Deprecated → Retired. Capabilities mature. They are never "finished."

## Capability Maturity Levels

| Level | Name | Description |
|---|---|---|
| 0 | Concept | Defined but not yet implemented |
| 1 | Manual | Human performs almost everything |
| 2 | Assisted | Kitty assists; human remains primary |
| 3 | Semi-Autonomous | Kitty performs bounded work; human supervises |
| 4 | Operational | Kitty performs reliably; human intervenes only when needed |
| 5 | Organizational | Capability continuously improves itself through evidence and reflection |

## Capability Domains

### Executive
Strategic Planning (L1), Prioritization (L1), Delegation (L2), Goal Management (L1), Roadmapping (L2)

### Knowledge
Evidence Collection (L2), Knowledge Retrieval (L1), Pattern Detection (L0), Doctrine Management (L2), Historical Recovery (L0), Knowledge Validation (L1), Terminology Management (L2)

### Builder
Packet Planning (L2), Bounded Execution (L3), Recovery (L2), Independent Verification (L2), Research (L2), Review Coordination (L2), Receipt Generation (L2), Self-Building (L2)

### Personal
Email Management (L2), Daily Planning (L2), Task Management (L2), Reminder System (L2), Opportunity Discovery (L1), Context Preparation (L2)

### Operations
Scheduling (L2), Background Jobs (L2), Monitoring (L2), Notifications (L2), Maintenance (L1), Governance Automation (L1)

### Creative
Writing Assistance (L2), Image Generation (L3), Design Support (L1), Brainstorming (L2), Communication Drafting (L2)

## Dependencies

Capabilities depend on capabilities. Never implementations. Removing or degrading a capability should make downstream impacts immediately obvious.

## How This Replaces Feature-Based Roadmapping

Instead of "let's build email," say "let's mature the Email Management capability from Assisted (L2) to Semi-Autonomous (L3)." Features are what you ship. Capabilities are what you can do. Features accumulate. Capabilities compound.

## Anti-Patterns

Capabilities should never be: model-specific, provider-specific, framework-specific, UI-specific, or temporary. Capabilities should outlive implementations.

## Success Criteria

Every subsystem knows what it owns. Roadmaps become capability maturation plans instead of feature lists. Implementations become replaceable without architectural changes. Organizational maturity becomes measurable.
