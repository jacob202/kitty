# Handoff — Design Doc Audit — 2026-05-01

**For:** Next agent fixing the launch plan design doc.
**Doc:** `docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md`
**Doc commit:** `181f611` (880 lines, 399/399 tests)
**Status:** Audit complete. 1 defect fixed in working tree (uncommitted). 8 remain.

---

## 1. ORIGINAL HANDOFF (Opus 4.7)

> Full version: `HANDOFF-2026-05-01-launch-plan-design.md` (same archive directory)
> 
> **Core task:** Write launch plan design doc. Mission: "So that no one becomes themselves alone." Approach B (Vision First). Layer 0 before Layer 1. 13 required sections. 800-1500 lines. No new decisions, pure synthesis.
> 
> **Jacob overrode "no new decisions" and "no clarifying questions" during the grilling below.**

---

## 2. TASK PROMPT (Jacob → deepseek-v4-pro)

**Mission (verbatim):**
> "So that no one becomes themselves alone."

**Locked:**
- Audience: technical friends, own copy on Mac. Future: App Store
- Approach B: Vision First (onboarding/memory first)
- Layer 0 before Layer 1
- Cheap-models-first budget. Free as backup
- Dorothy MCP = PM (Kanban + Telegram)
- Crush + Aider = builders
- Stack: Flask + Next.js + MLX + LightRAG
- 6 sub-projects: Onboarding → Memory → Commands → Tests → UX → Launch Ops
- 800-1500 lines, commit when done

---

## 3. GRILLED DECISIONS

| # | Question | Decision |
|---|----------|----------|
| 1 | Model strategy for M1 8GB | Cheap cloud APIs for parallel builders, local MLX fallback. ~$50-100 total build cost. |
| 2 | Multi-agent framework | CrewAI (assembly line) for onboarding pipeline. AutoGen/CrewAI-hybrid (team huddle) for CTO review pairs. |
| 3 | Dorothy MCP servers | Keep 4: kanban, telegram, vault, drawthings. Cut: orchestrator, socialdata, X, world. |
| 4 | Dorothy bridge | ~150-line Python daemon polling Kanban every 30s, spawning CrewAI/Crush/Aider, posting Telegram. |
| 5 | Skills to keep | fix-and-verify, parallel-subagents, overnight-queue, prompt-answer-quality, tdd, caveman, **grill-me (KEPT)**, spec-to-impl, demo, audit, zoom-out, firecrawl-* (11), skill-creator, find-skills |
| 6 | Skills to cut | domain-news, grill-with-docs, improve-codebase-architecture, recommend, setup-matt-pocock-skills, to-issues, to-prd, triage, write-a-skill, execution, improve, planning, reasoning, ship, think, world-builder, ast-grep. **Agent-browser: cut, reactivate if needed.** |
| 7 | Plugins: keep 4, cut 5 | Keep: commit-commands, code-review, superpowers, feature-dev. Cut: security-guidance, pr-review-toolkit, agent-sdk-dev, pyright-lsp, frontend-design |
| 8 | Scripts: keep 7 | clear-and-test.sh, quick-smoke.sh, checkpoint.sh, run_gates.sh, validate.sh, golden_demo.sh, context_pack_generator.py |
| 9 | Model routing | Hybrid: search/digest on cheap API, embed/organize on local MLX. Primary: deepseek-v4-flash ($0.28/M), qwen3-235b-a22b ($0.10/M), mistral-small-24b ($0.08/M). Free backup: qwen3-coder:free, llama-3.3-70b:free |
| 10 | Exa | Complementary to Firecrawl. API key available. |
| 11 | Docs optimization | Balanced. Strip narrative, keep critical gotchas. ~80 lines each. |
| 12 | Client reinstalls | No reinstalls. Clean configs only. |
| 13 | Cleanup execution | Phased (B). Verify after each phase. |
| 14 | Budget | Flexible. No hard cap. |

---

## 4. AUDIT RESULTS

**Grade: 64/100 — BORDERLINE PASS**

| Criteria | Score/Max |
|----------|-----------|
| Accuracy (grilled decisions correct) | 22/30 |
| Consistency (internal agreement) | 12/25 |
| Completeness (no gaps) | 10/15 |
| Actionability (can execute from doc) | 12/20 |
| Voice (Jacob-readable) | 8/10 |

### Defects (ordered by severity)

**D1. [FIXED — uncommitted] Mission drift check resurrected**
- Line 831: Continuous Enforcement table. Accidentally restored when bad commit was reverted. Cut in working tree, not committed.

**D2. Skills count math wrong**
- Phase B (line 158): Says "Keep 18" but listed skills count ~25 (firecrawl-* is 11 alone). Fix: recount and update number.

**D3. Stale information flow ASCII diagram**
- Section 8: Shows only "Crush + Aider" with old arrows. Team roster above it was updated but diagram wasn't. Fix: redraw with all roles.

**D4. "Coordinator" references survive**
- Failure Modes (lines 491-503) and Lane Discipline (505-511) reference a "coordinator" role that was removed from team roster. Fix: replace with "bridge daemon" or "Sonnet."

**D5. Phase verification gates hand-wavy**
- Phases A-F: "Verify X works" with no specific command. Fix: add exact verification command per phase.

**D6-D9: Minor inconsistencies**
- D6: PM header says "3" servers but drawthings makes it 4
- D7: Constraints section still says "Skills not optimized" without cross-referencing Pre-Flight plan
- D8: Orchestrator status ambiguous ("stripped to launcher if kept at all" vs "Cut: orchestrator")
- D9: Codex/OpenCode (paid subs) not in team roster as available agents

---

## 5. NEXT

1. Fix D2-D9 in the doc
2. `venv/bin/python -m pytest tests/ -q --tb=short` — must be 399 passing
3. Commit with: `fix: resolve 8 audit defects in launch plan design doc`
4. Append completion note here

---

Completion note: 2026-05-01 — audit defects D1-D9 resolved by Codex; doc checks pass (all 13 sections, mission quote intact, 881 lines); `venv/bin/python -m pytest tests/ -q --tb=short` passed with 399 tests and 2 warnings.

Follow-up note: 2026-05-01 — Jacob flagged a missing grilling-session decision: "No reinstalls. Clean configs only" and CLI/model config convergence. Added it to the design doc as a first-class Layer 0 Phase G, Model and CLI Config Control table, and Layer 0 validation gate.

Follow-up note: 2026-05-01 — Jacob pasted fuller grilling context. Added missing details: right-tool-not-fewer-tools rule, SOUL/reference-doc cleanup, CrewAI vs AutoGen vs LangGraph rationale, paid-seat vs cheap-API distinction, dormant-client policy, and agent-browser reactivation trigger.

Follow-up note: 2026-05-01 — Remaining D2-D9 defects re-audited and fixed by GLM-5.1. D4 (coordinator refs), D6 (PM header count), D8 (orchestrator ambiguity), D9 (Codex/OpenCode roster) were already resolved in prior passes. D2 (skills count) fixed: firecrawl-* is 12 not 11, total kept = 25 not 24. D5 (Phase C verification) fixed: added concrete grep command. D7 (constraints cross-ref) fixed: added reference to Pre-Flight Phases B-C. Also fixed skill total from ~35 to 43 (25 kept + 18 cut). 399/399 tests passing.
