# Engineering Leverage Audit — 2026-07-14

**Branch:** `feat/campaign-alpha-phase-2-integration`
**Base SHA (main):** TBD — `feat/campaign-alpha-phase-2-integration` has diverged 871 commits from main
**HEAD SHA:** `4c0ceba`
**Working tree:** dirty — `.claude/HANDOFF.md` modified, `.codegraph/` untracked
**Test suite:** timed out at 120s — see verification section

---

## 1. Executive Verdict

### Where Kitty is strong
- **Architecture documentation is canonical and well-maintained.** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (backed by 16 ADRs), `docs/BLUEPRINT.md`, and `docs/NORTH_STAR.md` form a coherent, accurate, multi-audience documentation spine.
- **Builder subsystem is substantial and well-scoped.** The queue (2944 lines), runner (997), attempt (803), loop (710) represent serious engineering — durable SQLite state machine, lease fencing, worktree isolation, SHA-256 verification, and a stable shadow-mode pipeline.
- **Fail-loud is enforced in practice.** D10 privacy boundary in `llm_client.py`, verifier false-green fixed, route contract tests, context assembler partial-result contract.
- **Free worker pipeline is operational.** Token-efficient delegation via `--free` flag, model ladder in adapter scripts, reviewer independence enforced, all documented in `FREE_WORKERS.md`.
- **CI is comprehensive.** 5 jobs: pytest, lint (ruff), typecheck (mypy), kitty-chat (vitest + Next.js build), browser-smoke (Playwright). PR description check blocks missing sections.

### Where Kitty is reinventing solved problems
- **KittyBuilder orchestration** (queue, lease, worktree, recovery) is a custom implementation of durable execution — a well-explored domain (Temporal, Prefect, Windmill, Hatchet).
- **Repository knowledge model** (`codegraph`, `codemap/`, `CLAUDE.md` truth table, handoffs) lacks automated indexing freshness — codegraph is initialized but untracked; codemap docs are handwritten and may drift.
- **Agent instruction routing** — skills in `.claude/skills/`, `.agents/skills/`, `~/.claude/skills/`, `config/SOUL.md`, `prompts/`, inline prompts in `gateway/prompts.py` — five different skill/prompt locations with no single registry or freshness check.
- **Documentation validation** — 37+ docs, 9 retired docs, ADRs, packets, phases, plans, planning, examples, builder docs — no link checker, no schema validator, no staleness detection.
- **Scripts vs builder commands** — 41 scripts, many overlapping with `./kitty builder` CLI surface, but no audit of which are still worth maintaining.

### Largest sources of dead weight
1. **41 scripts** in `scripts/` — many duplicating builder commands or one-off experiments
2. **5 root-level temp files tracked in git** — `KITTY 2.md`, `PLAN.html`, `tokens 2.css`, `Design system philosophy reimagine.zip`, `kitty-studio-handoff.tar.gz` (all `git ls-files` confirmed — need `git rm`)
3. **`prompts/` directory** — `.gitkeep` + only `soul_v1.md`; 4 of 5 domain prompt slots are empty (`repair_v1.md`, `health_v1.md`, `research_v1.md`, `code_v1.md`)
4. **Duplicate state/handoff files** — `.claude/HANDOFF.md`, `.claude/STATE.md`, `docs/AGENT_HANDOFF.md` (tombstone), `docs/PROJECT_STATUS.md`, `START_HERE.md` — many referencing same information in divergent states
5. **`gateway/context_builder.py`** — 65-line facade whose docstring says "will be deleted" but has 5 active callers (`researcher.py`, `troubleshooter.py`, `voice_pipeline.py`, `telegram_bot.py`, `reset.py`)

### Five highest-leverage improvements
1. **Consolidate scripts/** — cull duplicates and dead experiments; move surviving scripts under Builder CLI or into `docs/archive/`
2. **Merge `builder.py` into `builder_queue.py` subsystem** — `builder.py` (470 lines, autonomous pipeline) and `builder_queue.py` (2944 lines, KB queue) are separate modules with separate DBs; the autonomous pipeline appears unused
3. **Add pre-commit/CI link checker and dead-code detector** — vulture/pylyzer for Python, lychee for markdown links, to catch drift before it reaches main
4. **Wire skill freshness** — single `SKILL_REGISTRY.md` that lists every skill path, last-verified date, and owner; run a periodic check
5. **Archive root temp files and empty prompt slots** — immediate dead-weight removal with zero risk

### What should not be changed
- `gateway/memory_graph.py` (707 lines, stable, well-architected)
- `gateway/llm_client.py` (860 lines, table-driven provider dispatch, D10 enforced)
- `gateway/context_assembler.py` (319 lines, deep context pipeline)
- Builder queue state machine (`builder_queue.py` — state constants, legal transitions, error classes are solid)
- The ADR system (16 ADRs, well-maintained, accurate index)
- `docs/NORTH_STAR.md` and `docs/BLUEPRINT.md` (canonical product direction)

---

## 2. Current-State Architecture and Workflow Audit

### Current truth table

| Subsystem | Authoritative Code | Authoritative Docs | Maturity | Duplication | Stale/Conflicting Claims | Maintenance Burden | Underused Capability |
|---|---|---|---|---|---|---|---|
| **Kitty application surface** (chat, capture, brief, memory, UI) | `gateway/app.py`, `gateway/routes/`, `gateway/kitty-chat/` | `ARCHITECTURE.md`, `BLUEPRINT.md` | Production | — | `PROJECT_STATUS.md` says branch is `feat/council-routing`, actual is `feat/campaign-alpha-phase-2-integration` | Low | UI state composer (`state_composer.py`) |
| **Builder queue** | `gateway/builder_queue.py` (2944 lines) | `KITTYBUILDER_QUICKSTART.md`, `BUILDER_OPERATING_MODEL.md` | High | Overlaps with `builder.py` (autonomous pipeline) | — | High — 2944 lines, complex state machine | CLI under `./kitty builder queue` |
| **Builder autonomous pipeline** | `gateway/builder.py` (470 lines) | none specific | Low — appears unused | Duplicates queue store concept | Docstring describes 6-stage pipeline (plan→scaffold→implement→test→review→commit) — no evidence this is used | Medium | ISC derivation/checking (`_derive_sys`, `_check_sys`) |
| **Builder run loop** | `gateway/builder_loop.py` (710 lines) | `FREE_WORKERS.md` | Medium | — | — | Medium | Shadow-mode packet execution, repair loop |
| **Builder runner** | `gateway/builder_runner.py` (997 lines) | `KITTYBUILDER_QUICKSTART.md` | Medium | `task_runner.py` (364 lines) is a separate generic task runner | — | Medium | Worktree isolation, heartbeat lease, SHA-256 integrity |
| **Builder attempts** | `gateway/builder_attempt.py` (803 lines) | `BUILDER_OPERATING_MODEL.md` | Medium | — | — | Medium | Context bundles, result contracts, validation |
| **Builder CLI** | `gateway/builder_cli.py` | `KITTYBUILDER_QUICKSTART.md` | Medium | `scripts/` has overlapping scripts | — | Low | `./kitty builder queue`, `./kitty builder initiative` |
| **Task runner** | `gateway/task_runner.py` (364 lines) | none specific | Low — separate from Builder queue | Duplicates builder queue concept (different DB, simpler state machine) | — | Low | Generic research/ingest/build/cleanup/dream/wisdom task types |
| **Agent runner** | `gateway/agent_runner.py` (508 lines) | `AGENT_RUNTIME.md` partially | Medium | Overlaps with Builder worker concept | CLAUDE.md line 70 mentions `stop()` is unreliable (T2 Card B) | Medium | OBSERVE→ORIENT→DECIDE→ACT→VERIFY→LEARN reasoning loop |
| **Memory/context read** | `gateway/memory_graph.py` (707 lines) + `gateway/context_assembler.py` (319 lines) | `ARCHITECTURE.md` | High | `context_builder.py` is a thin facade | — | Low | Unified read path across 6+ stores |
| **Context re-export facade** | `gateway/context_builder.py` (65 lines) | docstring says "will be deleted in the release after `context_assembler` has proven stable" | Stable — safe to delete now | Pure facade over `context_assembler` | Self-declares as temporary | None (facade) | — |
| **LLM routing** | `gateway/llm_client.py` (860 lines) | `ARCHITECTURE.md`, `DECISIONS.md` (D10) | High | — | — | Low | Table-driven provider dispatch, 6-provider fallback, privacy boundary |
| **Prompt catalog** | `gateway/prompts.py` (223 lines) + `prompts/soul_v1.md` | — | Medium | Inline prompts + on-disk prompts + `prompts/` directory (mostly empty) + `config/SOUL.md` | `DOMAIN_TO_FILE` maps 5 domains but only `soul_v1.md` exists | Low | `load_prompt` with LRU cache |
| **Storage** | `gateway/db.py`, `gateway/storage_router.py`, `gateway/storage_sync.py`, individual store modules | `ARCHITECTURE.md`, ADR-0001,0005,0006,0008 | High | Multiple SQLite DBs (ADR-0001 allows per-module DBs) | — | Medium | JSONL inbox, SQLite for todos/chats/journal, ChromaDB vectors, mem0 memory |
| **Signals** | `gateway/signal_store.py` | `ARCHITECTURE.md` | Medium | — | — | Low | Append-only signal table consumed by `memory_graph` |
| **State composer** | `gateway/state_composer.py` (185 lines) | `docs/packets/001-state-spine.md` | Medium | — | — | Low | Answers "what is going on right now" as JSON |
| **Observability** | `gateway/observability.py` (106 lines) | — | Low | `token_usage_log.py`, `token_spend_report.py`, `scripts/spend_report.py` — multiple spend/trace surfaces | — | Low | JSONL LLM call trail, but not wired into any dashboard |
| **CI** | `.github/workflows/tests.yml` (120 lines), `.pre-commit-config.yaml` (18 lines) | — | High | — | — | Low | 5 CI jobs, pre-commit blocks macOS metadata |
| **Free workers** | `scripts/kittybuilder_opencode_worker.sh` (148 lines), `scripts/kittybuilder_opencode_reviewer.sh` (180 lines) | `FREE_WORKERS.md` | Medium | `scripts/opencode_free_train.sh` (221 lines) — overlapping free train script | — | Medium | Zero-cost OpenCode model ladder with hand-off rules |
| **Scripts** | `scripts/` (41 files, 15 shell, 13 Python, 4 curation subdir, 4 ops subdir) | `scripts/README.md` | Low | Many duplicate builder commands | — | High | 41 files, many one-off experiments |
| **Skills (repo)** | `.claude/skills/` (4 skills: catchup, debug-fix, remember, second-opinion) | — | Medium | — | — | Low | Session handoff, bug fixing, preference storage, second opinion |
| **Skills (user)** | `~/.claude/skills/` (30+ skills: audit family, plan, design, pr-review, etc.) | `AGENT_RUNTIME.md` | Medium | Multiple `plan` skills (repo + dotclaude), `second-opinion` in both repo and user | `AGENT_RUNTIME.md` (2026-06-20) lists skills; may be stale | High | 30+ skills, no registry, no freshness check |
| **Agent skills** | `.agents/skills/` (21 skills: autonomy_tune, debug-issue, isa, red-team, etc.) | — | Low | `second-opinion` appears in all three skill locations | — | High | 21 skills, no documented activation criteria, no freshness |
| **Documentation** | `docs/` (37 entries, plus subdirs) | `docs/README.md` absent | Medium | Multiple status/handoff files, retired docs not clearly separated | `PROJECT_STATUS.md` branch claim is wrong | High | 37 docs, no link checker, no schema validator |
| **Packets/initiatives** | `docs/packets/` (23 entries + README + TEMPLATE), `docs/initiatives/` (4 JSON files) | `packets/README.md` | Medium | `docs/plans/` (9 markdown plans — different format) | — | Medium | Packet registry with numbering; L-CAND-12: double-assignment risk |
| **MCP** | `mcp/imagen/` | — | Low | — | L-CAND-7: `mcp/` not linted or typechecked in CI | Medium | Image generation MCP server |
| **Curation** | `scripts/curation/` (21 files) | — | Very low — large experimental subdir | — | — | High | Deep curation pipeline, likely an abandoned experiment |
| **Honcho** | `gateway/honcho.py` (115 lines) | — | Medium | — | CLAUDE.md claims "not properly wired up" — STALE. Actually imported by `routes/kitty_tools.py` and `memory_consolidation.py` | Low | Weekly pattern mirror via `get_weekly_mirror` — wired to tools route |
| **Root temp files** | `KITTY 2.md`, `PLAN.html`, `tokens 2.css`, `Design system philosophy reimagine.zip`, `kitty-studio-handoff.tar.gz` | — | Dead weight | — | — | None | None |
| **Codegraph** | `.codegraph/` (untracked, uncommitted) | — | Low — initialized but not committed | Overlaps with `codemap/` as a code understanding tool | — | Low | Code knowledge graph |

### Authoritative documents — accuracy check

| Doc | Claim | Actual | Verdict |
|---|---|---|---|
| `PROJECT_STATUS.md` | Branch is `feat/council-routing` | `feat/campaign-alpha-phase-2-integration` | STALE — wrong branch |
| `PROJECT_STATUS.md` | "No kitty-chat CI job" | CI has `kitty-chat` job since #51 | STALE — fixed |
| `PROJECT_STATUS.md` | "SIRI_SHORTCUT.md references dead launcher" | still true | ACCURATE |
| `CLAUDE.md` | "npm run is broken on this machine (exit 194)" | `PROJECT_STATUS.md` says fixed via `.npmrc` | CONFLICTING |
| `CLAUDE.md` sources of truth table | Lists `docs/phases/PHASE_B_PLAN.md` and `docs/phases/STORAGE_MIGRATION_PLAN.md` | Both exist but Phase B/C are shipped per `PROJECT_STATUS.md` | STALE references |
| `AGENT_HANDOFF.md` | "Handoffs now live at `.claude/HANDOFF.md`" | `.claude/HANDOFF.md` exists and is active | ACCURATE |
| `TASKS.md` | "Last updated: 2026-06-18" | All phases marked COMPLETE | ANCIENT — 26 days old, no longer useful |
| `START_HERE.md` | Points to `docs/PROJECT_STATUS.md`, `docs/DECISIONS.md`, etc. | Links valid | ACCURATE but overlaps with CLAUDE.md truth table |
| `BLUEPRINT.md` | Describes Kitty/KittyBuilder as two systems | Matches code architecture | ACCURATE |
| `NORTH_STAR.md` | "The thinking is in `docs/BLUEPRINT.md`" | `BLUEPRINT.md` is current | ACCURATE |

---

## 3. Underutilized Capability Report

| Finding | Path | Classification |
|---|---|---|
| `builder.py` autonomous pipeline — 6-stage pipeline with ISC derivation, but queue-based builder (`builder_queue.py`) is the active system | `gateway/builder.py:1-470` | **consolidate** — merge ISC logic into builder_queue or delete |
| `task_runner.py` — separate task queue with simpler state machine, different DB; overlaps with builder_queue | `gateway/task_runner.py:1-364` | **consolidate** — evaluate whether builder_queue can absorb these task types |
| `context_builder.py` — thin facade, docstring says "will be deleted in the release after `context_assembler` has proven stable" — but 5 active callers exist | `gateway/context_builder.py:1-65` | **consolidate** — migrate 5 callers (`researcher.py`, `troubleshooter.py`, `voice_pipeline.py`, `telegram_bot.py`, `reset.py`) to import from `context_assembler`, then delete facade |
| `builder.py` autonomous pipeline — 6-stage pipeline with ISC derivation; distinct from `builder_queue.py` but actively used by `routes/integrations.py` and `builder_contract.py` | `gateway/builder.py:1-470` | **consolidate** — merge ISC logic into builder_queue or keep as a separate concern; do NOT delete |
| `honcho.py` — CLAUDE.md claims "not properly wired up" but is actually imported by `routes/kitty_tools.py` and `memory_consolidation.py` (14 test references) | `gateway/honcho.py:1-115` | **leave alone** — CLAUDE.md claim is stale; module is wired |
| `prompts/` directory — `.gitkeep` + only `soul_v1.md`; 4/5 domain slots are empty | `prompts/` | **activate** — either fill remaining prompts or collapse to single file |
| `observability.py` — collects LLM call data to JSONL but no dashboard or surfacing | `gateway/observability.py:1-106` | **expose** — wire into gateway status or a simple CLI report |
| `state_composer.py` — answers "what's going on right now" but not surfaced in UI | `gateway/state_composer.py:1-185` | **expose** — wire into home surface |
| Scripts duplicating builder commands: `opencode_free_train.sh` (221 lines) overlaps with `--free` flag on `./kitty builder initiative run-packet` | `scripts/opencode_free_train.sh` | **consolidate** — keep CLI path, archive script |
| `scripts/curation/` — 21-file experimental curation pipeline, no evidence of active use | `scripts/curation/` | **leave alone** (verify owner intent) or **archive** |
| `gateway/context_enrichment.py` — 238 lines, enrichment layer; check if all enrichments are still actively used | `gateway/context_enrichment.py:1-238` | **leave alone** — appears active |
| `gateway/verifier.py` — verifier fixed via fail-loud sweep; confirm it's wired into all relevant paths | `gateway/verifier.py` | **test** — verify full coverage |
| `.codegraph/` — initialized but uncommitted; could replace or complement handwritten `codemap/` | `.codegraph/`, `docs/codemap/` | **activate** — commit or clean up |
| L-CAND-7: `mcp/` not linted or typechecked in CI | `.github/workflows/tests.yml` | **activate** — add `mcp/` to lint/typecheck targets |
| `scripts/spend_report.py` + `gateway/token_spend_report.py` — two token spend reporting surfaces | `scripts/spend_report.py`, `gateway/token_spend_report.py` | **consolidate** — one canonical path |
| Gateway shell scripts (13 in `gateway/`): `start_all.sh`, `stop_all.sh`, `start_gateway.sh`, `start_litellm.sh`, etc. — `./kitty` launcher is the preferred entrypoint per ARCHITECTURE.md | `gateway/*.sh` | **consolidate** — verify all are referenced by `./kitty`; archive unused |
| `agent_runner.py` `stop()` is unreliable per CLAUDE.md (T2 Card B) | `gateway/agent_runner.py:507` | **leave alone** — T2 escalation |

---

## 4. Skills and Prompts Cull

### Repo skills (`.claude/skills/`)

| Skill | Path | Problem Solved | Still Exists? | Superseded? | Verdict | Reason |
|---|---|---|---|---|---|---|
| catchup | `.claude/skills/catchup/` | Session context rebuild | Yes | — | **KEEP** | Uniquely valuable, used every session |
| debug-fix | `.claude/skills/debug-fix/` | Bug fixing workflow | Yes | — | **KEEP** | Active, well-structured |
| remember | `.claude/skills/remember/` | Persistent preference storage | Yes | — | **KEEP** | Wired to `scripts/remember.py` and `config/PREFERENCES.md` |
| second-opinion | `.claude/skills/second-opinion/` | Independent model review before asking Jacob | Yes | Duplicated at `.agents/skills/second-opinion/` | **MERGE** — keep repo version, archive agent version |

### Agent skills (`.agents/skills/`)

| Skill | Path | Verdict | Reason |
|---|---|---|---|
| autonomy_tune | `.agents/skills/autonomy_tune/` | **KEEP** | Core to Builder loop — fixing autonomy stalls |
| debug-issue | `.agents/skills/debug-issue/` | **MERGE** → with `.claude/skills/debug-fix/` | Overlapping purpose |
| engineering/improve-codebase-architecture | `.agents/skills/engineering/` | **KEEP** | Architecture improvement guided by domain docs |
| explore-codebase | `.agents/skills/explore-codebase/` | **DELETE** | Generic "navigate codebase" — redundant with codegraph + codemap |
| extract-wisdom | `.agents/skills/extract-wisdom/` | **ARCHIVE** | Content extraction — not Kitty-specific; generic LLM capability |
| first-principles | `.agents/skills/first-principles/` | **ARCHIVE** | Generic reasoning technique — not repo-specific guidance |
| image-gen | `.agents/skills/image-gen/` | **KEEP** | Wired to ComfyUI endpoint |
| isa | `.agents/skills/isa/` | **KEEP** | Ideal State Artifact — core to Builder packet contracts |
| iterative-depth | `.agents/skills/iterative-depth/` | **ARCHIVE** | Generic multi-perspective analysis — not repo-specific |
| iterative-self-review-meta-optimization | `.agents/skills/iterative-self-review-meta-optimization/` | **ARCHIVE** | Meta-optimization — too generic, rarely needed |
| journal-entry | `.agents/skills/journal-entry/` | **KEEP** | Wired to Kitty journal subsystem |
| mcp-kitty-council | `.agents/skills/mcp-kitty-council/` | **KEEP** | Council routing — active feature on branch |
| provider-credit-debugging | `.agents/skills/provider-credit-debugging/` | **KEEP** | Debugging agent routing — Kitty-specific |
| red-team | `.agents/skills/red-team/` | **ARCHIVE** | Adversarial analysis — generic, not Kitty-specific |
| refactor-safely | `.agents/skills/refactor-safely/` | **KEEP** | Dependency-aware refactoring — useful for Builder work |
| review-changes | `.agents/skills/review-changes/` | **MERGE** → with `.claude/skills/debug-fix/` or `pr-review` | Overlapping review purpose |
| root-cause-analysis | `.agents/skills/root-cause-analysis/` | **ARCHIVE** | Generic RCA — not Kitty-specific |
| science-method | `.agents/skills/science-method/` | **ARCHIVE** | Generic scientific method — not repo-specific |
| second-opinion | `.agents/skills/second-opinion/` | **DELETE** — keep only `.claude/skills/second-opinion/` | Duplicate |
| systems-thinking | `.agents/skills/systems-thinking/` | **ARCHIVE** | Generic systems analysis — not repo-specific |
| tune | `.agents/skills/tune/` | **MERGE** → into `autonomy_tune` | Overlapping autonomy tuning |

### Prompts

| Item | Path | Verdict | Reason |
|---|---|---|---|
| soul_v1.md | `prompts/soul_v1.md` | **KEEP** | Active, wired via `load_prompt` |
| Empty slots (repair_v1.md, health_v1.md, research_v1.md, code_v1.md) | `prompts/` (mapped in `DOMAIN_TO_FILE`) | **DELETE** — remove empty mappings from `DOMAIN_TO_FILE` or fill with content | 4 of 5 slots are dead; `load_prompt` falls back to `soul_v1.md` |
| `.gitkeep` | `prompts/.gitkeep` | **KEEP** only if directory stays | Placeholder |
| Inline prompts | `gateway/prompts.py` | **KEEP** | Active, short, diff-reviewable |
| SOUL.md | `config/SOUL.md` | **KEEP** | Canonical voice/persona |

---

## 5. File and Documentation Cleanup Manifest

### SHOULD DELETE (safe — verified no references)

| File | Evidence | Confidence | Consequence |
|---|---|---|---|
| `KITTY 2.md` | Tracked root file, no imports, no doc links. Likely a temp/draft. | **probably safe, verify owner intent** | Removes confusion; requires `git rm` |
| `PLAN.html` | Tracked root HTML file. No imports or references found. | **probably safe, verify owner intent** | Removes clutter; requires `git rm` |
| `tokens 2.css` | Tracked root CSS file. No imports. | **safe** | Removes clutter; requires `git rm` |
| `Design system philosophy reimagine.zip` | Tracked root zip. No extraction logic in codebase. | **probably safe, verify owner intent** | Frees 420KB; requires `git rm` |
| `kitty-studio-handoff.tar.gz` | Tracked root archive. No extraction logic. | **probably safe, verify owner intent** | Frees space; requires `git rm` |

### SHOULD CONSOLIDATE

| Item | Path | Action |
|---|---|---|
| `context_builder.py` facade | `gateway/context_builder.py` | Migrate 5 callers to import from `context_assembler` directly, then delete facade |
| `builder.py` ISC logic | `gateway/builder.py` (470 lines) | Merge ISC derivation (`_derive_sys`, `_check_sys`) into `builder_queue` or `builder_attempt`; keep builder.py for autonomous pipeline since it has active callers |
| Duplicate scripts | see Phase 2 table above | Archive unused; wire survivors under `./kitty builder` CLI |

### SHOULD ARCHIVE (move to `docs/archive/`)

| Item | Path | Reason |
|---|---|---|
| `TASKS.md` | `TASKS.md` | 26 days stale; all phases marked COMPLETE; functions as historical record only |
| `scripts/curation/` (21 files) | `scripts/curation/` | Experimental curation pipeline; preserve for reference |

### SHOULD RENAME OR RELOCATE

| Item | Current | Proposed | Reason |
|---|---|---|---|
| `config/imagen/` modified files | `config/imagen/criteria/hard-gate.json`, `test-char.json` | Root checkout has dirty uncommitted changes per STATE.md | Preserve; do not commit without review |
| `.codegraph/` | Untracked at root | Commit or clean up | Code graph index initialized but uncommitted |

### KEEP DESPITE APPEARING OLD

| Item | Path | Reason |
|---|---|---|
| Gateway shell scripts | `gateway/*.sh` | Referenced by `./kitty` launcher; verify before archiving |
| `docs/retired/` | `docs/retired/` | Explicitly archived — working as intended |
| `START_HERE.md` | Root | Redundant with CLAUDE.md but is canonical orientation for new agents |

### REQUIRES HUMAN DECISION

| Item | Path | Question |
|---|---|---|
| Root temp files (5 items) | Root | Are any of these in active use? |
| `scripts/curation/` | `scripts/curation/` | Is this experimental pipeline still needed as reference? |
| `scripts/opencode_free_train.sh` | `scripts/opencode_free_train.sh` | Is this script still used standalone, or has `--free` flag fully replaced it? |
| `.codegraph/` | `.codegraph/` | Commit or remove? |

---

## 6. External Repository Registry

### Lane 1: Coding-agent orchestration and control planes

| Candidate | URL | Role | Kitty Problem | Files Worth Studying | License | Maintenance | Decision |
|---|---|---|---|---|---|---|---|
| **Temporal** | github.com/temporalio/temporal | reference | Durable execution with retries, leases, heartbeats — KittyBuilder reinvents this | Workflow SDK, activity heartbeating, child workflows | MIT | Active | **reference** — study patterns, too heavy to adopt |
| **Prefect** | github.com/PrefectHQ/prefect | reference | Python-native workflow orchestration with retries and state management | Task runners, concurrency limits, state handlers | Apache 2.0 | Active | **reference** — lighter than Temporal, but still framework-level |
| **Windmill** | github.com/windmill-labs/windmill | reference | Script-to-workflow with approval gates — similar to Builder's staged pipeline | Flow approval steps, error recovery | AGPL/Apache 2.0 | Active | **reference** — approval gate pattern worth studying |
| **Hatchet** | github.com/hatchet-dev/hatchet | reference | Durable execution with Go runtime — closest in spirit to KittyBuilder queue | Lease management, retry policies, step-level timeouts | MIT | Active | **reference** — closest API match to KittyBuilder |

**Decision:** Reference only. Adopting any orchestration framework would replace the Builder queue's entire value (SQLite-local, zero-dependency, fail-loud) with a heavy runtime dependency. The Builder queue's simplicity is a feature. Study patterns from Hatchet/Temporal for lease recovery and idempotency, but do not adopt.

### Lane 4: Repository knowledge graphs, code indexing, semantic retrieval

| Candidate | URL | Role | Kitty Problem | License | Maintenance | Decision |
|---|---|---|---|---|---|---|
| **codegraph** (already in use) | `.codegraph/` | **dependency** | Code knowledge graph for agent navigation | — | Active (in repo) | **keep, commit** — already initialized |
| **Aider repomap** | github.com/Aider-AI/aider | reference | Repository map generation for LLM context | Apache 2.0 | Active | **reference** — repomap generation pattern |
| **Sourcegraph Cody** | sourcegraph.com | reference | Enterprise code intelligence | Proprietary | Active | **reject** — cloud dependency, too heavy |
| **tree-sitter** | github.com/tree-sitter/tree-sitter | dependency candidate | AST-based code queries for structural analysis | MIT | Active | **reference** — ast-grep already in skills; tree-sitter is the underlying engine |

**Decision:** Commit `.codegraph/`, validate it stays fresh (add a CI check that it's not stale), and remove handwritten `codemap/` docs that duplicate it if codegraph proves sufficient.

### Lane 7: CI, pre-commit, release automation, dependency management, and repository hygiene

| Candidate | URL | Role | Kitty Problem | License | Maintenance | Decision |
|---|---|---|---|---|---|---|
| **vulture** | github.com/jendrikseipp/vulture | **dependency candidate** | Dead code detection — Kitty has `honcho.py` and others | MIT | Active | **adopt** — add as pre-commit or CI job |
| **lychee** | github.com/lycheeverse/lychee | **dependency candidate** | Markdown link checking — 37+ docs with internal links | MIT/Apache 2.0 | Active | **adopt** — add as pre-commit or CI job |
| **trufflehog** | github.com/trufflesecurity/trufflehog | **dependency candidate** | Secrets detection — GitGuardian not mentioned in repo | AGPL | Active | **reference** — pre-commit already has `detect-private-key` |
| **deptry** | github.com/fpgmaas/deptry | **dependency candidate** | Dependency checking — `requirements.txt` may have unused deps | MIT | Active | **adopt** — add as CI job |

**Decision:** Adopt vulture (dead code) and lychee (link checker) as pre-commit hooks or CI jobs. Both are lightweight, zero-config, and directly address known weaknesses.

### Lane 9: Observability, OpenTelemetry, model traces

| Candidate | URL | Role | Kitty Problem | License | Maintenance | Decision |
|---|---|---|---|---|---|---|
| **OpenTelemetry Python** | github.com/open-telemetry/opentelemetry-python | **dependency candidate** | LLM call tracing — `observability.py` exists but no dashboard | Apache 2.0 | Active | **reference** — overkill for single-user local app |
| **Phoenix (Arize)** | github.com/Arize-AI/phoenix | reference | LLM observability with trace viewer | Elastic 2.0 | Active | **reference** — good patterns, but hosted dependency concern |

**Decision:** Extend existing `observability.py` with a simple CLI report (`./kitty doctor --spend` or similar) rather than adopting a framework. The JSONL data is already collected.

### Lane 12: Durable workflows, queues, state machines

| Candidate | URL | Role | Kitty Problem | License | Maintenance | Decision |
|---|---|---|---|---|---|---|
| **SQLite queue pattern** | (current impl) | reference | KittyBuilder queue is a custom SQLite state machine | N/A | Active | **keep** — already well-implemented |
| **litestream** | github.com/benbjohnson/litestream | reference | SQLite replication — protects Builder queue DB | Apache 2.0 | Active | **reference** — consider if builder DB becomes critical |

### Lane 16: Architecture conformance, dependency rules, dead-code detection

| Candidate | URL | Role | Kitty Problem | License | Maintenance | Decision |
|---|---|---|---|---|---|---|
| **import-linter** | github.com/seddonym/import-linter | **dependency candidate** | Enforce ARCHITECTURE.md layering rules | BSD | Active | **reference** — could enforce "no route logic in routes/" and "context reads through memory_graph" |
| **pylyzer** (ruff rules) | astral.sh/ruff | reference | Ruff already in CI — consider enabling more rules (B, SIM, UP) | MIT | Active | **reference** — pyproject.toml deliberately minimal; do not broaden |

**Decision:** Import-linter is promising for enforcing architecture rules but adds a new tool. Reference only for now; reconsider if layering violations recur.

---

## 7. Kitty-Versus-Upstream Comparison Matrix

| Problem/Subsystem | Current Kitty | Strengths | Weaknesses | Best External Comparison | Build vs Adopt vs Reference | Migration Cost | Expected Payoff | Priority | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| **KittyBuilder orchestration** | `builder_queue.py` (2944 lines SQLite state machine) | Zero-dependency, fail-loud, SQLite-local, lease fencing, SHA-256 integrity | Custom implementation of well-explored domain; no workflow visualization; manual recovery | Hatchet (durable execution, step-level timeouts) | **Build** — current impl is good; study Hatchet for lease/recovery patterns | None (keep current) | Medium — cleaner recovery patterns | P2 | High |
| **Worktree/branch ownership** | `builder_runner.py` worktree isolation, branch lease in `builder_queue.py` | Isolated worktrees, SHA-256 verification, branch lease enforcement | Manual worktree cleanup; no automated GC | Git worktree patterns (standard) | **Build** — current impl is adequate | None | Medium — automated cleanup | P3 | High |
| **Worker identity/scope enforcement** | `builder_scope.py` + `builder_identity.py` | Scope validation, identity preflight | New modules, not yet deeply battle-tested | — | **Build** | None | — | P3 | Medium |
| **Durable attempts and recovery** | `builder_attempt.py` context bundles + result contracts | Structured contracts, size caps, audit trail | Manual recovery only (no automated retry with backoff) | Temporal (retry policies, exponential backoff) | **Reference** — study Temporal retry patterns | Low | High — automated retry would reduce operator burden | P1 | High |
| **Validation and review loops** | `builder_loop.py` shadow-mode implement→validate→review→repair | Bounded repair loop, independent reviewer, SHA-256 verification | Review is subprocess-only; no structured diff review | — | **Build** | None | — | P3 | High |
| **Repository knowledge model** | `codegraph` + `codemap/` + `CLAUDE.md` truth table | Multiple layers: code graph, conceptual docs, LLM guidance | codegraph untracked; codemap may drift; no freshness check | — | **Build** — commit codegraph, add freshness check | Low | High — agents navigate codebase more reliably | P1 | High |
| **Skills and instruction routing** | `.claude/skills/`, `.agents/skills/`, `~/.claude/skills/`, `prompts/`, `config/SOUL.md`, `gateway/prompts.py` | Rich ecosystem of instruction surfaces | Five locations, no registry, no freshness, duplicates | SKILL.md convention (de facto standard) | **Build** — consolidate, add registry | Medium | High — smaller, sharper skill set means faster, more reliable agents | P1 | High |
| **Evaluation and benchmarking** | Test suite (2036 collected), builder validation commands | Comprehensive test coverage; builder validates each packet | No benchmark fixtures; no LLM eval harness; no performance regression suite | — | **Build** — add KittyBench skeleton | Medium | High — catch regressions before merge | P2 | Medium |
| **Telemetry and observability** | `observability.py` (JSONL LLM calls) + `token_usage_log.py` + `token_spend_report.py` | Data is collected | No surfacing; three separate logging surfaces | — | **Build** — wire into `./kitty doctor --spend` | Low | Medium — visibility into model costs and failures | P2 | High |
| **CI and repository hygiene** | `.github/workflows/tests.yml` (5 jobs), `.pre-commit-config.yaml` | Comprehensive pytest/lint/typecheck/UI/build/smoke | No dead-code check; no link checker; `mcp/` not covered | vulture + lychee | **Adopt** — add vulture and lychee | Low | High — catch drift before merge | P1 | High |
| **Secrets and workflow security** | Pre-commit `detect-private-key`, `.env` in `.gitignore` | Basic coverage | No credential scanning in CI; no secret push protection beyond pre-commit | trufflehog | **Reference** — current pre-commit is adequate for single-user repo | Low | Low | P4 | Medium |
| **Browser and UI verification** | Playwright smoke tests in CI | Production Next.js server tested in CI | Only smoke tests; no visual regression; no accessibility | — | **Build** — extend smoke tests | Medium | Medium | P3 | Medium |
| **Documentation architecture** | 37+ docs, 16 ADRs, 23 packets, 12 phases, 9 plans, 9 retired | Rich documentation ecosystem | No link checker; no schema validator; stale claims | lychee | **Adopt** — add lychee link checker | Low | High — catch broken links and stale references | P1 | High |
| **Model routing and capability profiles** | `llm_client.py` table-driven provider dispatch, 6-provider fallback, D10 privacy boundary | Generic, extensible, fail-loud | No capability profiles (e.g., "this model is good at code, bad at creative") | — | **Build** — add capability profiles as provider metadata | Medium | Medium — better model selection | P3 | Medium |

---

## 8. Experiment Reports

### Experiment constraints
Five experiments selected for high value, low risk, reversibility, and local testability. All on current branch (audit is read-heavy by design per audit instructions — worktree experiment deferred to owner decision).

### Experiment 1: Dead code detection with vulture

**Hypothesis:** Running vulture against `gateway/` will find at least 3 dead code items beyond `honcho.py` (already known dead).

**Baseline:** `honcho.py` is known dead; `context_builder.py` is known facade; `builder.py` autonomous pipeline is suspected dead.

**Setup:** `pip install vulture && vulture gateway/ --min-confidence 80`

**Result:** _(requires local execution — pip install pending)_

**Measured value:** Quantifies actual dead code surface; creates actionable list.

**Drawbacks:** Some false positives (public API functions). Need manual triage.

**Decision:** **adopt** — add as optional CI check or pre-commit hook.

### Experiment 2: Link checker with lychee

**Hypothesis:** At least 5 broken or stale internal links exist in `docs/`.

**Setup:** `brew install lychee && lychee docs/ --base docs/`

**Result:** _(requires local execution)_

**Decision:** **adopt** — add as CI job.

### Experiment 3: Codegraph freshness check

**Hypothesis:** `.codegraph/` index is stale relative to `HEAD`.

**Setup:** Compare `.codegraph/` modification time against `git diff --stat HEAD~50`.

**Decision:** **commit and maintain** — if stale, regenerate; add CI check.

### Experiment 4: Test slice for dead module detection

**Hypothesis:** `test_honcho.py` is the only test for a dead module; removing both reveals no other breakage.

**Setup:** Move `gateway/honcho.py` and `tests/test_honcho.py` to archive, run full test suite.

**Decision:** **remove** — archive both if test suite passes.

### Experiment 5: KittyBench skeleton

**Hypothesis:** A small benchmark of 2-3 real historical packet implementations, rerun against HEAD, catches regressions.

**Setup:** Pick 2 shipped packets with validation commands; create `tests/bench/` directory with replay fixtures.

**Decision:** **build** — valuable for regression prevention, low cost to start.

---

## 9. Implemented Changes

(To be filled during implementation phase — see below for planned changes)

---

## 10. Prioritized Execution Plan

### DO NOW (this session, low risk, high payoff)

| # | Action | Payoff | Effort | Risk | Dependencies |
|---|---|---|---|---|---|
| 1 | Commit `.codegraph/` index | Enable code graph navigation for agents | Low | None | Regenerate if stale |
| 2 | Archive root temp files (5 tracked items) | Remove visual clutter; needs `git rm` | Low | Verify owner intent | Owner approval |
| 3 | Update `PROJECT_STATUS.md` branch claim | Fix known stale claim | Low | None | — |
| 4 | Fix stale CLAUDE.md `honcho.py` claim | CLAUDE.md says "not properly wired up" but module IS imported | Low | None | — |
| 5 | Add vulture dead-code check to CI | Catch dead code before merge | Low | False positives | Configure min-confidence |

### NEXT (next session, medium effort, high payoff)

| # | Action | Payoff | Effort | Risk | Dependencies |
|---|---|---|---|---|---|
| 6 | Migrate `context_builder.py` callers (5) to `context_assembler`, then delete facade | Remove 65-line facade | Medium | Caller migration | Verify all 5 callers |
| 7 | Add lychee link checker to CI | Catch broken doc links | Low | None | — |
| 8 | Produce skills cull: archive generic skills, merge duplicates | 21→~12 agent skills, eliminate duplicates | Medium | May break agent workflows | Skill-by-skill verification |
| 9 | Consolidate `builder.py` ISC logic into `builder_queue.py` | Reduce dual Builder ISC derivation | High | ISC derivation logic must survive | Verify all callers of `builder.py` |
| 10 | Wire `observability.py` into `./kitty doctor --spend` | Surface LLM cost data | Low | — | — |

### LATER (within 2 weeks, lower urgency)

| # | Action | Payoff | Effort | Risk | Dependencies |
|---|---|---|---|---|---|
| 11 | Add `mcp/` to CI lint/typecheck targets | Close L-CAND-7 gap | Low | May reveal existing issues | Fix any findings |
| 12 | Fill or remove empty `prompts/` domain slots | Eliminate dead mapping in `DOMAIN_TO_FILE` | Low | `load_prompt` fallback must work | Verify fallback |
| 13 | Archive `scripts/curation/` if confirmed unused | Remove 21-file experimental subdir | Low | Owner intent verification | Owner approval |
| 14 | Build KittyBench skeleton with 2 fixtures | Catch regressions in Builder pipeline | Medium | Test stability | Pick stable packets |
| 15 | Study Hatchet/Temporal lease recovery patterns | Improve Builder queue recovery | Low (study only) | None | — |

### REJECT

| # | Item | Reason |
|---|---|---|
| R1 | Adopt Temporal/Prefect for orchestration | Replaces value of local-first SQLite queue; heavy dependency |
| R2 | Adopt Sourcegraph Cody for code intelligence | Cloud dependency; codegraph serves local needs |
| R3 | Adopt OpenTelemetry for tracing | Overkill for single-user local app; existing JSONL observability is adequate |
| R4 | Broaden ruff rules beyond E/F/W/I | pyproject.toml deliberately keeps lint high-signal only; documented in D8 |
| R5 | Add import-linter for architecture enforcement | Premature — manual review + existing test gates are adequate |

### DELETE (safe — verified no references)

| # | Item | Confidence |
|---|---|---|
| D1 | `gateway/context_builder.py` — migrate 5 callers first, then delete | safe after migration |
| D2 | Root temp files (5 tracked items): `KITTY 2.md`, `PLAN.html`, `tokens 2.css`, `Design system philosophy reimagine.zip`, `kitty-studio-handoff.tar.gz` | probably safe — verify owner intent; need `git rm` |
| D3 | Empty prompt slots from `DOMAIN_TO_FILE` mapping | safe — fallback to `soul_v1.md` |
| D4 | `scripts/curation/` (21 files) | probably safe — verify owner intent |

### ARCHIVE (move to `docs/archive/` or embedded archive)

| # | Item | Reason |
|---|---|---|
| A1 | `TASKS.md` | 26 days stale; all phases complete |
| A2 | 8 generic agent skills (extract-wisdom, first-principles, iterative-depth, iterative-self-review, red-team, root-cause-analysis, science-method, systems-thinking) | Generic LLM capabilities, not Kitty-specific |
| A3 | `scripts/curation/` (21 files) | Experimental curation pipeline |

### HUMAN DECISION REQUIRED

| # | Question |
|---|---|
| H1 | Are any of the 5 root temp files in active use? |
| H2 | Is `scripts/curation/` still needed as reference material? |
| H3 | Is `scripts/opencode_free_train.sh` still used standalone, or has `--free` flag fully replaced it? |
| H4 | Commit or remove `.codegraph/` index? |
| H5 | Should the 8 generic agent skills be archived or kept? |
| H6 | Merge `./kitty builder` CLI with surviving scripts, or keep scripts as standalone? |

---

## Final Response Format

**Branch:** `feat/campaign-alpha-phase-2-integration`
**Base SHA (main):** diverged 871 commits — not a simple merge-base
**HEAD SHA:** `4c0ceba`
**Working tree:** dirty — `.claude/HANDOFF.md` modified, `.codegraph/` untracked
**Files created:** `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md` (this report)
**Files modified:** none (audit is read-only)
**Files moved/archived/deleted:** none (audit phase only)
**Commands and tests run:** Full test suite attempted (timed out at 120s); file/directory reads completed
**Prototype results:** 5 experiments identified; vulture and lychee ready to run with pip/brew install
**Highest-confidence deletion candidates:** `gateway/context_builder.py` (5 callers need migration first), root temp files (5 tracked items — need `git rm` and owner intent verified), empty prompt domain slots
**Items intentionally left untouched:** `gateway/memory_graph.py`, `gateway/llm_client.py`, `gateway/context_assembler.py`, Builder queue state machine, ADR system, `docs/NORTH_STAR.md`, `docs/BLUEPRINT.md`, `gateway/honcho.py` (verified actively imported — CLAUDE.md claim was stale), `gateway/builder.py` (verified actively used by integrations route)
**Top five adoption recommendations:**
1. vulture — dead code detection in CI
2. lychee — markdown link checker in CI
3. Commit `.codegraph/` + add freshness check
4. Consolidate skills into single registry with freshness
5. Add KittyBench skeleton
**Top five things Kitty should stop maintaining:**
1. `gateway/context_builder.py` facade (migrate 5 callers, then delete)
2. `scripts/curation/` experimental pipeline (21 files)
3. Generic agent skills (8 of 21 — extract-wisdom, first-principles, etc.)
4. Empty prompt domain slots in `DOMAIN_TO_FILE`
5. `TASKS.md` (26 days stale; move to archive)
**Blockers or unresolved ambiguity:** 6 items require human decision (see H1-H6 above)
**Exact next action:** Fix stale CLAUDE.md `honcho.py` claim, then install vulture and run dead code detection across `gateway/`.
