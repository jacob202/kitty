---
type: principles
title: "System Design Principles"
status: draft
owner: jacob
primary_purpose: Engineering principles that guide subsystem design — stable semantics, replaceable implementations, low coupling, explicit ownership
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
  - docs/architecture/REFERENCE_ARCHITECTURE.md
review_cycle: annual
---

# System Design Principles

Very small. Engineering principles.

1. **Stable semantics.** What a subsystem means should outlive how it is implemented. Semantics are the contract. Implementation is the delivery mechanism.

2. **Replaceable implementations.** Every subsystem should be replaceable without architectural change. Builder may move from one executor to another. Knowledge retrieval may move from one database to another. The architecture remains intact.

3. **Canonical knowledge.** Every concept has exactly one home. Every other document references it. None duplicate it. Duplicate definitions are a CI failure.

4. **Low coupling.** Subsystems communicate through explicit contracts. No hidden state. No implicit dependencies. No direct architectural mutation. Replace one subsystem — nothing else should break.

5. **Explicit ownership.** Every capability has exactly one owning Office. Capabilities may collaborate. Ownership is never shared. Shared ownership becomes missing ownership.

6. **Progressive context.** Agents and humans should receive only the context they need. Full architectural context should be discoverable, not forced. Point, don't explain. Reference, don't duplicate.

7. **Simplicity.** If understanding increases while complexity decreases, the architecture is moving in the correct direction. Every architectural decision should remove future ambiguity.

8. **Continuous learning.** Every completed initiative produces evidence. Evidence produces observations. Observations become knowledge. Knowledge compounds. The organization gets smarter — not just larger.
