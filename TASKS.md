# Tasks

Last updated: **2026-05-13**

## Authority

Feature roadmap and phased work live in **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`**. Jacob’s latest message overrides everything; next **`docs/DECISIONS.md`**, then **`AGENTS.md`**, **`docs/STANDUP.md`**.

This file is a **thin checklist**. For file lists, rationale, and “what done looks like”, always open the Unified Plan—not a summary here.

---

## Active focus (Unified Plan Phase 1)

Companion architecture foundation (**Phase 1** in `docs/UNIFIED_IMPLEMENTATION_PLAN.md`). Track progress there; indicative checkboxes:

- [x] **1.1 Collapse context layers** — `memory_graph.unified_context()` queries all 4 stores concurrently; wired into every LLM call via `context_builder.py`.
- [x] **1.2 Companion voice wired** — `voice_gate.py` filters banned phrases; `self_review.py` drift injected into system prompt when threshold exceeded.
- [x] **1.3 Persistent voice channel** — `voice_session.py` WebSocket handler with 20-turn history; route `/voice` live in `app.py`.
- [ ] **1.4 Buddy / mascot** — `gateway/buddy.py` exists with persistent mood state + `/mood` endpoint; UI polls gateway instead of inferring from text.

---

## Next horizons (see Unified Plan)

Work is **ordered** after Phase 1 in the same doc: **Phase 2** agents & background tasks, **Phase 3** external-world connection, **Phases 4–10**, then **Excluded (Parked)**. Do not start downstream phases unless Jacob or the Plan explicitly expands scope.

---

## Historical archive (pre-gateway prune — not the live layout)

Earlier **Phase 2 memory / KittyBuilder / `src/`** checkpoints (2026-05 and earlier) referred to paths that **no longer exist** in this checkout (legacy **`src/`** tree removed **2026-05-13**). Those tasks are **completed or obsolete** relative to stack structure; preserved only for audit trail:

- `docs/plans/phase2-orchestration-workflow-2026-05-06.md`
- `docs/plans/` and `docs/superpowers/plans/` (memory architecture, KittyBuilder-era plans)

For **current runtime**, code lives under **`gateway/`**; verification:  
`/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short`

---

## Quick verify

Before claiming done on Python/config/hooks:

`/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short`
