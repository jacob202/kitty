# Superseded — Image-job runner and recipe registry cleanup

**Status:** Superseded and partially landed  
**Reviewed:** 2026-07-28  
**Replacement:** `docs/plans/image-studio-character-first-architecture-2026-07-28.md`

This plan is no longer ready to implement as written.

The repository now contains the durable `image_jobs` store and a centralized
`image_runner`, and several request-contract cleanups described here have
landed. The remaining problem is not another extraction of the same runner. It
is that recipe capability rows still overstate what the runtime can execute:
current character generation resolves one primary reference, recipe metadata
does not select a real versioned workflow, and multi-character/localized edit
support is not operational.

Carry forward only these requirements:

- `image_runner` remains the single provider-dispatch boundary;
- every return or exception leaves the provider job in a truthful terminal or
  recoverable durable state;
- recipe availability must be derived from executable adapter health, required
  models/nodes, and validated workflow hashes;
- unsupported recipes must be unavailable rather than displayed optimistically;
- routes remain thin and must not duplicate provider lifecycle handling.

Do not execute the old candidate order. The replacement plan extends the
existing job system with image sessions, attempts, model adapters, Character
Packs, Qwen open-worker generation/editing, premium-final promotion, bounded
critique/repair, multi-character support, honest ETA, and cost governance.

The original plan remains available in Git history as implementation evidence.
