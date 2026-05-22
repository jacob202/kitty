# ADR format

Use when a rejected architecture candidate has a load-bearing reason worth preserving. Store at `docs/adr/NNNN-short-title.md` (create the directory if needed).

## Template

```markdown
# ADR-NNNN: <Title>

**Status:** Accepted | Superseded by ADR-XXXX

## Context

What problem or candidate prompted this decision.

## Decision

What we chose and why.

## Consequences

What gets easier, harder, or off-limits for future refactors.
```

## Rules

- Number sequentially (`0001`, `0002`, …).
- Record the rejection reason, not the full alternative design.
- Link to the modules and docs involved.
