---
type: governance
title: "Documentation Governance"
status: canonical
owner: jacob
primary_purpose: Rules for documentation ownership, review, deprecation, supersession, and amendment
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
implements:
  - docs/CONSTITUTION.md
referenced_by:
  - docs/README.md
review_cycle: quarterly
---

# Documentation Governance

## Ownership

Every foundational document has an `owner` in its YAML frontmatter. The owner is responsible for keeping the document current and consistent, reviewing proposed changes, and ensuring traceability links remain accurate. The default owner is `jacob` unless explicitly delegated.

## Review Cadence

| Document Type | Review Cycle |
|---|---|
| Vision | Annual |
| Constitution | Annual (changes require ADR) |
| Roadmap | Monthly |
| Architecture | Quarterly |
| ADRs | At creation; superseded when replaced |
| Operations (status, learnings) | Continuous |
| Research / design specs | Per initiative |

## Adding a New Foundational Document

1. Create the document with required YAML frontmatter.
2. Declare `derives_from` (what it builds on) and `implements` (what it fulfills).
3. Add it to `docs/README.md` in the appropriate section.
4. Run `kitty docs lint` to verify traceability and metadata.
5. If the document introduces an architectural decision, create an ADR.

## Deprecation Process

1. Add `status: deprecated` to the document's frontmatter.
2. Add a deprecation notice at the top of the document body explaining what replaces it.
3. Move the file to `docs/archive/` if it is no longer referenced by any active document.
4. Update `docs/README.md` to remove it from the active index.
5. Run `kitty docs lint` to confirm no broken references.

## Supersession Process

1. The superseding document declares `supersedes: [old-doc-path]` in its frontmatter.
2. The superseded document gets `status: superseded` and a notice pointing to the replacement.
3. If the superseded document is an ADR, the new ADR references it.
4. Move the superseded file to `docs/archive/` after confirming no active references remain.

## ADR Requirements

An ADR is required for: changes to the Constitution, new databases/queues/cloud services/frameworks, gateway API surface changes, approval tier changes, storage model changes, and any decision that affects multiple subsystems. ADRs follow the template in `docs/adr/0000-template.md`: Context, Decision, Consequences.

## Automated Enforcement

- `kitty docs lint` validates frontmatter, traceability, and references.
- `SYSTEM_MAP.md` is auto-generated from frontmatter and checked for staleness in CI.
- CI fails if generated artifacts are stale or if traceability links are broken.

## Anti-Patterns

- **Orphan documents** — foundational documents with no `derives_from` and no `referenced_by`.
- **Duplicate philosophy** — the same principle stated in multiple documents. Reference, don't copy.
- **Stale handoffs** — status documents that haven't been updated in the current context.
- **Implementation in vision** — Vision and Constitution contain no implementation details.
- **Missing ADR** — architectural changes without a corresponding ADR.
