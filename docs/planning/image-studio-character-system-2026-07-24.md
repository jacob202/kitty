# Superseded — Image Studio and character system redesign (2026-07-24)

**Status:** Superseded on 2026-07-28  
**Replacement:** `docs/plans/image-studio-character-first-architecture-2026-07-28.md`  
**Roadmap authority:** `docs/ROADMAP.md`

This document described an earlier repository state and must not be used as an
implementation plan.

Its useful ideas—character references, versioned identity, gallery lineage,
backend abstraction, workflow validation, privacy, and durable jobs—were
re-audited against current code and carried forward where still valid.

Its implementation claims and sequencing are stale because:

- the character store now has reference images, embeddings, versioning, tags,
  and gallery records;
- a durable provider-neutral `image_jobs` store and `image_runner` now exist;
- recipe rows still do not prove executable workflow support;
- current generation uses one primary reference and does not provide a real
  multi-character or localized-repair workflow;
- PR #289 introduces an ImagePlan boundary that the replacement plan deepens;
- the earlier ComfyUI/Stability/DALL-E fallback recommendation predates the
  current model market and the corrected fictional-adult James use case;
- `docs/ROADMAP.md` now gates broad Image Studio implementation until Phase 1
  exits.

The original document remains available in Git history as research evidence.
Do not execute its ten-week sequence or provider recommendations.
