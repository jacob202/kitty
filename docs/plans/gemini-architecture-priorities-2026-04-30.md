# Gemini audit — three deep tracks (priorities index)

**Tag:** `GEMINI-ARCH-PRIORITIES` (grep-friendly)  
**Sources:** `docs/AGENT_COORDINATION.md` active lanes (`arch-001`, `arch-002`, `kb-002`) + execution artifacts below.  
**Purpose:** Single place to **extract and sequence** Gemini’s architecture recommendations against your control docs (`CURRENT_FOCUS.md`, `TASKS.md`, `docs/DECISIONS.md`).

---

## Track 1 — Unified Tool Runtime (Candidate A)

| Field | Value |
|-------|--------|
| Lane | `arch-001` (planned) |
| Execution depth | Stepwise plan with files, validation, acceptance criteria |
| Plan | `docs/plans/2026-04-30-unified-tool-runtime.md` |
| Intent | One `ToolRuntime` over `ToolManager` / `ToolRegistry`; permissions; batch execution; specialist executor seam |

**Why first (suggested):** Candidate A explicitly **sits under** future specialist execution (`SpecialistToolExecutor` stub in plan). Shipping typed `ToolDefinition` / `ToolContext` first reduces duplicate safety logic before large specialist refactors.

---

## Track 2 — Specialist Runtime (Candidate B)

| Field | Value |
|-------|--------|
| Lane | `arch-002` (planned) |
| Execution depth | Described on coordination board; **no long-form plan file yet** |
| Concept anchor | `KITTY_CONTEXT.md` — **SpecialistDefinition** (data-driven identity + toolset) |
| Intent | Move specialist **execution** into a runtime; specialists become definitions + thin hooks |

**Dependency:** Overlaps Track 1 at the `SpecialistToolExecutor` / recursion boundary — spec-first before editing `src/core/specialists/` broadly (per `CURRENT_FOCUS` / D-0007).

**Next artifact (recommended):** `specs/specialist-runtime.spec.md` (intake → approve → implement), or extend superpowers plan if that is your chosen intake path.

---

## Track 3 — Builder automation (intake → spec)

| Field | Value |
|-------|--------|
| Lane | `kb-002` (**complete** on coordination board) |
| Execution depth | `scripts/automate_builder.py` + `specs/builder-automation.spec.md` |
| Intent | Classified intake Markdown → compliant spec skeletons; faster spec-first cycles for Tracks 1–2 |

**Use ongoing:** Run when new ideas arrive so **arch** work always enters through an approved spec (D-0003, D-0007).

---

## Suggested sequencing (“your priorities”)

1. **Keep regression bars green** — merge gate + copy-first sync after risky merges (`TASKS.md`, D-0010, D-0011).  
2. **Track 3 on demand** — spin specs for any new arch work before code (`automate_builder.py` / builder intake).  
3. **Track 1 then Track 2** — matches the seam ordering in the Unified Tool Runtime plan; avoids two large refactors fighting the same import graph.  
4. **Reconcile `CURRENT_FOCUS`** — when starting `arch-001` / `arch-002`, update forbidden/allowed work or open a waivered spec so coordination stays truthful.

---

## Cross-links

- Learnings / process: `docs/audits/LEARNINGS_72H_2026-04-30.md`, `docs/DECISIONS.md` (D-0011, D-0012).  
- Operational milestones: `docs/audits/operational-plan-20260430.md`.

---

*Indexed by cursor from coordination + repo artifacts; amend when Gemini adds a dedicated Candidate B plan file.*
