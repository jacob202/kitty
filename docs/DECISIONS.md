# Decisions

Last updated: 2026-05-09

This file records durable project decisions. New work should follow these rules unless a later dated decision explicitly supersedes them.

## D-0001: Current App Stays Put (Phase 0)

Status: superseded by D-0014

`/Users/jacobbrizinski/Projects/kitty` is the current runnable app. Do not move it, rename it, split it, or physically migrate files during Phase 0.

Rationale: the app is actively changing, and uncontrolled moves would make it hard to distinguish real regressions from path and import breakage.

## D-0002: `kitty-system` Separation Is Planned, Not Started (Phase 0)

Status: superseded by D-0014

The future architecture may separate stable system/control material from the runnable app, using a future `kitty-system` boundary. That separation is pending controlled migration.

Required before migration:

- Approved migration spec.
- Full file inventory.
- Explicit move map.
- Rollback plan.
- Verification commands.
- Completion report.

## D-0003: Intake Before Builder Work

Status: accepted

Builder tasks must enter through `docs/BUILDER_INTAKE.md` and `intake/`. A task is not ready for implementation until it has:

All build work passes through kittyintake.

- A named owner or worker lane.
- Scope summary.
- Allowed files.
- Forbidden files.
- Acceptance tests.
- Smoke test.
- Rollback plan.

## D-0004: Separate Control Docs From Product Code

Status: accepted

Control documents describe how work is allowed to proceed. They do not authorize product behavior changes by themselves.

Control-doc changes may update:

- `CURRENT_FOCUS.md`
- `docs/DECISIONS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/FILE_MANIFEST.md`
- `docs/BUILDER_INTAKE.md`
- `specs/_template.md`
- `intake/`

Product changes require a separate spec.

## D-0005: Park, Do Not Opportunistically Build

Status: accepted

Interesting ideas discovered during focused work must go to `docs/PARKED_FEATURES.md` or an intake note. They must not be implemented inside an unrelated task.

## D-0006: Protected Files Require Explicit Permission

Status: accepted

Protected files and directories are listed in `docs/FILE_GOVERNANCE.md`. Workers must check that file before editing and must not touch protected runtime paths unless their assigned spec explicitly allows it.

## D-0007: Builder Requires Explicit Project And Spec

Status: accepted

`kittybuilder` must not start an open-ended interactive builder by default. It requires:

- `--project`
- `--spec`
- dry-run by default
- `--execute` before any future write-capable builder path

The spec must live inside the project, and every run must end with a completion-report checklist.

Rationale:
Raw builder launch is too easy to confuse with runtime Kitty startup and can lead to uncontrolled edits.

## D-0008: Canadian-First Assistant Persona Candidate

Status: needs_user_confirmation (confidence: low)

Do not treat the Canadian-first assistant persona as accepted canon yet.

Rationale:
The evidence in `docs/imports/gemini_intake_20260428.md` comes primarily from assistant-authored session text. It is useful as a candidate preference, but not strong enough to become a durable project decision without Jacob confirming it.

Consequences:
Kitty should keep the accepted direct/practical/no-fluff style, but Canadian sourcing and budget-first behavior should be used only when the user asks for it or confirms this as a permanent preference.

Review trigger:
Jacob confirms whether Canadian-first sourcing/budget behavior is a permanent assistant preference.

## D-0009: Preserve Raw Logs

Status: accepted (confidence: high)

Preserve raw logs until reviewed extraction exists.

Rationale:
This is already a project safety rule and matches the master plan. It prevents accidental deletion of unmodified data and forces humans/agents to perform an explicit review.

## D-0010: Migration Runtime Path Is Active With Rollback Preserved

Status: superseded by D-0014 (2026-05-02)

Daily work previously followed a copy-first second checkout at `kitty-system/kitty-app` with `/Users/jacobbrizinski/Projects/kitty` as git rollback. That two-checkout workflow is **retired**; see D-0014.

## D-0014: Single Canonical Checkout After Copy-First Consolidation

Status: accepted

The only authoritative runnable app and git history is:

`/Users/jacobbrizinski/Projects/kitty`

The temporary migrated tree at `kitty-system/kitty-app` was reconciled into this repository and removed (2026-05-01; see `docs/audits/CONSOLIDATION_REPORT_2026-05-01.md`).

Consequences:
- New implementation, testing, and documentation work run **only** from the canonical path above unless Jacob explicitly approves a new migration spec.
- Older docs, coordination-board rows, and merge-gate reports that mention `kitty-system/kitty-app` are **historical chronology**, not current routing.

Review trigger:
Opening a new physical split or second runnable checkout requires a dated decision here plus `docs/FILE_MANIFEST.md` and `docs/LAYER0_CONTROL_PLANE.md` updates.

## D-0011: Phase 4 Merge Gate Report Path Is Project-Anchored

Status: accepted

`scripts/run_phase4_merge_gate.sh` resolves a **relative** `--report` path against the directory passed to **`--project`** (after `pwd` resolution), not against the shell’s current working directory.

Rationale:
A relative report path combined with a mismatched cwd produced incomplete markdown (missing header and Full Suite section) while steps still ran against `--project`.

Consequences:
- Default and relative reports (for example `docs/PHASE4_MERGE_GATE_RUN_<date>.md`) are created under the **validated project tree**.
- Use an absolute `--report` only when the report must live outside `--project`.

Review trigger:
Change to merge gate contract or CI layout that requires cwd-relative reports.

## D-0012: Commit Message Must Match Staged Content

Status: accepted

Before finalizing a commit message, authors run **`git diff --cached --stat`** (or equivalent) and ensure the **title and body describe only what is staged**.

Rationale:
Mismatched narratives (message references files not in the commit, or omits staged files) confuse bisect, audits, and coordination handoffs.

Consequences:
- Agents treat the staged diff as the source of truth for the commit message.
- Unrelated staged changes are split into a separate commit or unstaged.

Review trigger:
Repeated coordination confusion from commit metadata; optional automation (prepare-commit-msg hook) if desired.

## D-0013: KittyBuilder Is The Project Manager Workbench

Status: accepted

KittyBuilder owns the start-of-work project-manager surface. It loads the Layer 0 control plane, dirty-tree state, task state, and recent commits before work starts. It prepares CTO handoffs and next gated actions.

KittyBuilder does not replace the CTO role. Sonnet/Opus still own architecture, code review, technical coherence, and merge judgment.

KittyBuilder does not replace Dorothy. Dorothy remains the board, vault, and Telegram notification layer.

Safety boundary:
Write-capable builder execution still requires an approved spec and explicit `--project` / `--spec` arguments. Read-only PM briefing can run with `python3 scripts/kitty_builder.py --brief`.

Review trigger:
If `kittybuilder --brief` becomes misleading, slow, or noisy, tighten its context pack rather than bypassing the PM surface.

## D-0015: Run-End Continuity Checkpoint Is Mandatory

Status: accepted

After any meaningful run, update the canonical continuity surfaces so another model can resume without replaying the whole session.

Required files:
- `TASKS.md`
- `docs/TASKS.md`
- `SESSION_SUMMARY.md`
- `docs/OPEN_LOOPS.md`
- `docs/handoffs/HANDOFF-YYYY-MM-DD.md` (dated handoff for the run)

Durable policy changes also require:
- `docs/DECISIONS.md`

Delegated runs must include actual token telemetry:
- per-lane `delta total_tokens`
- estimated uncached prompt (`input_tokens - cached_input_tokens`)
- parent-orchestrator delta for the same window

Rationale:
Takeover speed and quality degraded when status lived only in chat text. The checkpoint contract reduces restart cost and makes delegated usage auditable.

Reference:
`docs/CONTINUITY_STANDARD.md`

Review trigger:
If this protocol creates excessive overhead, adjust template strictness, not evidence requirements.

## D-0016: Optimize KittyBuilder For Effectiveness Per Token

Status: accepted

KittyBuilder routing must optimize for lowest expected verified cost, not cheapest-first output. Verified cost includes model tokens, retries, failed tests, human re-explanation, cleanup from low-quality code, and misalignment with the approved request.

Consequences:
- Do not default to multi-agent swarms for coding tasks.
- Use parallel agents only for independent lanes with explicit ownership, output format, validation command, and stop conditions.
- Add an Intent Compiler before execution so messy brain dumps become scoped, testable Builder Briefs.
- Add a Context Compiler so workers receive the smallest high-signal context pack that can satisfy the task.
- Add a Worker Health Preflight before routing to external CLIs/providers.
- Add an append-only Evidence Ledger for run outcomes, verification, tokens, risks, and next action.

Reference:
- `docs/plans/kittybuilder-effectiveness-meta-analysis-2026-05-06.md`
- `docs/plans/kittybuilder-effectiveness-research-sources-2026-05-06.md`
- `docs/superpowers/plans/2026-05-06-kittybuilder-intent-compiler.md`

Review trigger:
If future run evidence shows this control layer adds more overhead than quality gain, revise the routing policy and compiler schema rather than returning to blanket cheap-first delegation.

## D-0017: Cost Discipline — Cheap-First Routing

Status: accepted

Jacob has explicitly said "always conserve your usage" multiple times. Model routing follows a strict tier order:

- **Default (cheap-and-reliable):** DeepSeek V4 Flash, Gemini 2.5 Flash, Groq paid tier — under $0.01/1K. Use for execution work, code generation, file edits, test writing.
- **Backup (free):** OpenRouter free models (`qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`), Groq free tier. Use when daily budget is hit or task is genuinely simple. Accept rate-limit risk.
- **Premium (reserved):** Claude Sonnet for architecture, code review, multi-file synthesis, Jacob-facing summaries. Claude Opus only for highest-leverage strategic decisions.
- **Local (offline/private):** MLX Qwen3.5-4B-4bit, Ollama qwen2.5-coder:7b. Free, private, no cloud dependency.

Rationale: free-first sounds cheapest but has rate limits, queues, quality variance, and outage risk. Cheap-and-reliable models are deterministic. Free is the safety net, not the default.

Source: CLAUDE.md

Review trigger: Jacob explicitly changes cost posture or a new default-tier model becomes available at comparable price.

## D-0018: Named-Tool Fidelity

Status: accepted

When Jacob explicitly names a tool (`coderabbit review`, `aider`, `crush run`), use that exact tool. Do not silently substitute with a generic equivalent even if the substitute seems capable.

Source: CLAUDE.md

Review trigger: Jacob explicitly delegates a substitution policy.

## D-0019: Cut Parallel Agents When Not Producing Evidence

Status: accepted

Parallel agents must be terminated the moment they stop producing evidence. Do not keep agents alive "just in case." Token cost scales linearly with idle agents.

Source: CLAUDE.md

Review trigger: evidence that early cutoff causes more harm than cost savings.

## D-0020: Approved MCP Server Launch Set

Status: accepted

The active MCP server set is exactly: **kanban, telegram, vault, drawthings** (all Dorothy.app except drawthings which is npx-based on port 7859). All other MCP servers must be cut or parked.

Consequences:
- Dorothy.app also ships mcp-orchestrator, mcp-socialdata, mcp-world, mcp-x — these must remain un-wired until MCP expansion is explicitly approved (see D-0029).

Source: LAYER0_CONTROL_PLANE.md (2026-05-02), ~/.claude/mcp.json audit (2026-05-09)

Review trigger: Jacob explicitly expands or contracts the MCP launch set.

## D-0021: Instruction Authority Order

Status: accepted

When agent instructions conflict, apply this priority (highest to lowest):

1. Jacob's live instruction in the current session
2. AGENTS.md
3. CLAUDE.md
4. LAYER0_CONTROL_PLANE.md
5. CURRENT_FOCUS.md
6. TASKS.md
7. docs/DECISIONS.md
8. Approved active spec
9. docs/AGENT_COORDINATION.md (lane coordination only)
10. Older files, stale handoffs, archived docs

Source: LAYER0_CONTROL_PLANE.md

Review trigger: new persistent-instruction surface is added to the project.

## D-0022: Storage Routing Is Strict

Status: accepted

Wrong routing is explicitly cited as the #1 source of data-loss bugs in this project. The canonical routing is:

- **Knowledge base ingestion** → LightRAG ONLY (never JournalDB)
- **Journal entries** → JournalDB ONLY (never LightRAG)
- **Semantic search** → ChromaDB
- **MCP entities/relations** → `@modelcontextprotocol/server-memory`
- **Corrections and other structured data** → SQLite

Never cross-route these stores.

Source: AGENTS.md

Review trigger: storage backend replacement or new data type introduced.

## D-0023: Validation Loop Is Mandatory After Code Changes

Status: accepted

After every code change, the following must pass before claiming work is done:

1. `pytest tests/ -q --tb=short` — fix failures, rerun until passing, then rerun once more clean.
2. For control-layer work: `bash scripts/run_gates.sh`
3. For runtime/API work: verify `/status` and `/health` curl checks
4. For eval-gated changes: verify `POST /api/eval/run`

Never skip this loop. The reasoning-route bug and ChromaDB regression both slipped through because code was marked done before the loop ran.

Source: AGENTS.md

Review trigger: test infrastructure is reorganized or gates are renamed.

## D-0024: Test Evidence Required Before Claiming Work Complete

Status: accepted

Any claim that something is "done," "fixed," or "passing" requires fresh test output as evidence pasted inline. Status optimism without verification is rejected. Jacob reacts strongly to claims without proof.

Source: AGENTS.md

Review trigger: Jacob explicitly changes verification expectations.

## D-0025: No Source Files In Project Root

Status: accepted

New files must go to their canonical location:

- Source code → `src/`
- Tests → `tests/`
- Documentation and plans → `docs/`
- Config → `config/`
- Scripts → `scripts/`

Never create source files directly in the project root (`/Users/jacobbrizinski/Projects/kitty/`).

Source: AGENTS.md

Review trigger: new top-level directory is formally established.

## D-0026: Firecrawl Query Limits Per Run

Status: accepted

- Max 1–2 Firecrawl queries per run.
- Use `scrape()` not `crawl()` for single pages.
- For multi-page web research, use `src/tools/research_pipeline.py` (map + batch_scrape) — not deep crawl.

Rationale: uncapped Firecrawl usage burns budget and creates noisy context.

Source: AGENTS.md

Review trigger: research pipeline is redesigned or Firecrawl pricing changes.

## D-0027: Learned Rules Require Explicit Review Before Adoption

Status: accepted

User corrections may surface candidate learned rules. No automated process may blindly append them to SOUL files or agent instruction sources. All candidates must pass explicit human review before becoming canon.

Source: SOUL_LEARNED_RULES.md

Review trigger: a formal review workflow for learned rules is implemented.

## D-0028: Parked Features Require Template Format

Status: accepted

Every entry in `docs/PARKED_FEATURES.md` must use the standard template with all required sections: Status, Source, Owner, Priority, Problem, Proposed Shape, Why Parked, Dependencies, Risks, Acceptance Sketch, Revival Trigger, Minimum Safe Version, Allowed Future Files, Forbidden During Unrelated Work.

Rationale: parking preserves ideas without hijacking focused work; incomplete entries defeat the purpose.

Source: PARKED_FEATURES.md

Review trigger: template sections are formally revised.

## D-0029: MCP Expansion Is Forbidden In Current Phase

Status: accepted

No new MCP servers may be registered, no un-wired Dorothy.app servers may be activated, and no MCP agent bundle work (KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, Overnighter) may proceed.

This extends D-0020: the approved set is fixed at four servers.

Revival trigger: Jacob explicitly approves MCP expansion after workspace separation preflight is clean.

Source: PARKED_FEATURES.md, CURRENT_FOCUS.md (2026-05-09)

## D-0030: All Agents Must Start With MASTER_INDEX.md

Status: accepted

All agent sessions must begin by reading `MASTER_INDEX.md` for fast-parse orientation — project structure, key commands, and current-phase boundaries. It is the canonical starting point and supersedes ad-hoc codebase exploration as a first step.

Source: HANDOFF-2026-05-09.md (2026-05-09)

Review trigger: MASTER_INDEX.md is renamed or replaced by a different orientation document.

## D-0031: web_llm Uses OpenRouter Exclusively As Provider Fallback

Status: accepted

`src/api/web_llm.py` uses OpenRouter free tier as its only fallback provider. Anthropic, Gemini, and all other direct-provider cascading has been removed. No provider waterfalling outside the OpenRouter ecosystem.

Source: SESSION_SUMMARY.md (2026-05-07)

Review trigger: a new provider tier is deliberately added with Jacob's approval.
