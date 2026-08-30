# CONTEXT.md format (optional domain glossary)

Create or extend `docs/CONTEXT.md` when the grilling loop introduces a domain term that deserves a stable name across architecture reviews.

## Template

```markdown
# Kitty domain glossary

## <Term>

**Meaning:** One sentence definition.

**Modules:** Which gateway modules own this concept (e.g. `memory_graph`, `context_builder`).

**Not:** Common confusions to avoid.
```

## Rules

- One term per `##` heading.
- Prefer names already used in `gateway/` and `docs/ARCHITECTURE.md`.
- Keep entries short — this is a glossary, not a design doc.
- Link to tests or routes when they clarify behaviour.
