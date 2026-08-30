# Implementation Plan — Engineering Leverage Consolidation

**Date:** 2026-07-14
**Status:** Implementation blueprint — merge into execution after review
**Inputs:** `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md`, `docs/AUDIT_EXTERNAL_ARCHITECTURE_2026-07-14.md`
**Replaces:** Individual audit execution plans — this is the single canonical plan

---

## 1. Recommendation Reconciliation Matrix

Cross-referencing every finding from both audits. Source: I=Internal, E=External.

| # | Recommendation | Source | Duplicated? | Conflicting? | Obsolete? | Already Done? | Blocked? | Resolution |
|---|---|---|---|---|---|---|---|---|
| 1 | Fix stale CLAUDE.md claims (npm run, honcho, kitty-chat CI) | I§10.4, E§12 | No | No | No | No | No | **Keep** — single action |
| 2 | Update PROJECT_STATUS.md branch claim | I§10.3, E§13.5 | No | No | No | No | No | **Keep** |
| 3 | Add vulture dead-code check to CI | I§10.5, E§4.1, E§5.1 | Yes — both recommend | No | No | No | No | **Merge** into one action |
| 4 | Add lychee link checker to CI | I§10.7, E§4.2, E§5.2 | Yes — both recommend | No | No | No | No | **Merge** |
| 5 | Add deptry dependency check to CI | E§4.4, E§5.3 | No | No | No | No | No | **Keep** |
| 6 | Add trufflehog secret scanning | I§10 (P4-reference), E§4.3 (adopt) | Yes | **YES** — Internal says reference, External says adopt | No | No | No | **Resolve**: adopt as pre-commit hook, not CI. Single-user repo; pre-commit is sufficient. CI job adds latency for minimal additional coverage. |
| 7 | Commit .codegraph/ index | I§10.1, E§1.Lane 4 | Yes | No | No | No | No | **Keep** |
| 8 | Migrate context_builder.py callers (5) then delete facade | I§10.6 | No | No | No | No | No | **Keep** |
| 9 | Archive root temp files (5 tracked items) | I§10.2 | No | No | No | No | Yes — H1 (owner) | **Keep** — blocked on owner |
| 10 | Consolidate builder.py ISC logic | I§10.9 | No | No | No | No | No | **Keep** |
| 11 | Wire observability.py into `./kitty doctor --spend` | I§10.10, E§14 | Yes | No | No | No | No | **Keep** |
| 12 | Remove empty prompt domain slots from DOMAIN_TO_FILE | I§10.12 | No | No | No | No | No | **Keep** |
| 13 | Add mcp/ to CI lint/typecheck | I§10.11 | No | No | No | No | No | **Keep** |
| 14 | Build KittyBench skeleton | I§10.14, E§14 | Yes | No | No | No | No | **Keep** |
| 15 | Skills cull: archive 8 generic agent skills | I§4, I§10.8 | No | No | No | No | Yes — H5 (owner) | **Keep** — blocked on owner |
| 16 | Archive scripts/curation/ | I§10.13 | No | No | No | No | Yes — H2 (owner) | **Keep** — blocked on owner |
| 17 | Study Hatchet API patterns | I§10.15, E§5.5 | Yes | No | No | No | No | **Keep** — study only |
| 18 | Study Aider repomap for LLM context | E§5.4 | No | No | No | No | No | **Keep** — study only |
| 19 | Study DSPy for context optimization | E§5.8 | No | No | No | No | No | **Keep** — study only |
| 20 | Study Braintrust for KittyBench design | E§5.9 | No | No | No | No | No | **Keep** — study only |
| 21 | Adopt uv for package management | E§5.10, E§12 | No | No | No | No | No | **Keep** |
| 22 | Formalize evidence ledger concept | E§12, E§14 | No | No | No | No | No | **Keep** |
| 23 | Document local-first durable execution | E§12 | No | No | No | No | No | **Keep** |
| 24 | Vale doc consistency linting | E§5.6 | No | No | No | No | No | **Keep** |
| 25 | Kuzu for memory_graph (evaluate) | E§5.7 | No | No | No | No | No | **Keep** — evaluate only |
| 26 | Test honcho.py removal (Experiment 4) | I§8.4 | No | No | **YES** — obsolete | No | No | **REJECT** — honcho.py is verified actively imported |
| 27 | Adopt Temporal/Prefect | I§10.R1 | No | No | No | No | No | **REJECT** — confirmed by both audits |
| 28 | Adopt OpenTelemetry | I§10.R3 | No | No | No | No | No | **REJECT** — confirmed by both audits |
| 29 | Broaden ruff rules | I§10.R4 | No | No | No | No | No | **REJECT** — deliberate decision (D8) |
| 30 | Migrate Makefile to Earthly/poethepoet | E§12 (monitor) | No | No | No | No | No | **Defer to Future Research** — monitor, don't act |
| 31 | Archive TASKS.md | I§10.A1 | No | No | No | No | No | **Keep** |

### Conflict resolution

**trufflehog (I§10 P4-reference vs E§4.3 adopt):**
Internal audit said "reference — pre-commit already has detect-private-key" and assigned P4 priority. External audit listed trufflehog as adoption candidate #3. Resolution: **adopt as pre-commit hook only** (not CI job). The pre-commit hook runs locally on every commit and catches secrets before they reach the remote. A CI job adds latency for minimal additional coverage in a single-user repo. `detect-private-key` (current pre-commit) only catches SSH/GPG keys; trufflehog adds 800+ detectors including API keys, tokens, and credentials.

**Honcho.py test removal (I§8.4):**
Experiment 4 hypothesized removing honcho.py and its test. This is obsolete — subsequent verification (documented in the same internal audit) confirmed 14 imports from `kitty_tools.py` and `memory_consolidation.py`. **Rejected.**

---

## 2. Canonical Recommendation List

After deduplication, conflict resolution, and obsolescence removal. Total: 21 actionable recommendations.

| ID | Recommendation | Category |
|---|---|---|
| **IMM-01** | Fix stale CLAUDE.md claims (npm run, honcho wiring, kitty-chat CI) | Documentation correction |
| **IMM-02** | Update PROJECT_STATUS.md (branch claim, outdated entries) | Documentation correction |
| **IMM-03** | Remove empty prompt domain slots from DOMAIN_TO_FILE | Code cleanup |
| **IMM-04** | Add vulture dead-code check to CI | CI addition |
| **IMM-05** | Add lychee link checker to CI | CI addition |
| **IMM-06** | Add deptry dependency check to CI | CI addition |
| **IMM-07** | Add trufflehog as pre-commit hook | CI addition |
| **IMM-08** | Commit .codegraph/ index + add freshness check | Repository knowledge |
| **NT-01** | Migrate context_builder.py callers (5) then delete facade | Code consolidation |
| **NT-02** | Consolidate builder.py ISC logic into builder_queue/builder_attempt | Code consolidation |
| **NT-03** | Wire observability.py into `./kitty doctor --spend` | Feature addition |
| **NT-04** | Add mcp/ to CI lint/typecheck targets | CI addition |
| **NT-05** | Build KittyBench skeleton with 2 fixtures | Evaluation |
| **NT-06** | Study Hatchet API for queue improvement patterns | Research |
| **NT-07** | Study Aider repomap for LLM context optimization | Research |
| **STRAT-01** | Skills cull: archive 8 generic agent skills, merge duplicates | Architecture consolidation |
| **STRAT-02** | Formalize evidence ledger as architectural concept | Architecture documentation |
| **STRAT-03** | Document local-first durable execution as innovation | Architecture documentation |
| **STRAT-04** | Evaluate Kuzu for memory_graph entity modeling | Architecture exploration |
| **STRAT-05** | Evaluate DSPy for context_assembler optimization | Architecture exploration |
| **STRAT-06** | Evaluate Braintrust for full KittyBench design | Architecture exploration |
| **FUT-01** | Adopt uv for package management | Dev experience |
| **FUT-02** | Adopt vale for documentation consistency | Dev experience |
| **FUT-03** | Monitor Makefile → Earthly/poethepoet migration | Dev experience |
| **BLOCKED-H1** | Archive root temp files (5 tracked items) | Blocked — owner decision |
| **BLOCKED-H2** | Archive scripts/curation/ (21 files) | Blocked — owner decision |
| **REJ-01** | Adopt Temporal/Prefect/Hatchet for orchestration | Rejected |
| **REJ-02** | Adopt OpenTelemetry collector | Rejected |
| **REJ-03** | Broaden ruff lint rules | Rejected |
| **REJ-04** | Remove honcho.py (verified active) | Rejected |
| **REJ-05** | Delete builder.py (verified active via integrations route) | Rejected |

---

## 3. Prioritized Backlog

### Immediate (≤1 hour each — do this week)

| ID | Action | Effort | Risk | Dependencies |
|---|---|---|---|---|
| IMM-01 | Fix stale CLAUDE.md claims | 15min | None | None |
| IMM-02 | Update PROJECT_STATUS.md | 15min | None | None |
| IMM-03 | Remove empty prompt domain slots | 15min | None | None |
| IMM-04 | Add vulture to CI | 30min | False positives | pip install vulture |
| IMM-05 | Add lychee to CI | 30min | None | brew install lychee or Docker |
| IMM-06 | Add deptry to CI | 30min | False positives | pip install deptry |
| IMM-07 | Add trufflehog to pre-commit | 30min | False positives | brew install trufflehog |
| IMM-08 | Commit .codegraph/ + freshness check | 30min | Index may be stale | .codegraph/ exists |

### Near-term (2-8 hours each — this month)

| ID | Action | Effort | Risk | Dependencies |
|---|---|---|---|---|
| NT-01 | Migrate context_builder.py callers | 2h | Caller breakage | Verify all 5 callers |
| NT-02 | Consolidate builder.py ISC logic | 4h | ISC derivation behavior change | Verify integrations route + nudge + builder_contract |
| NT-03 | Wire `./kitty doctor --spend` | 2h | None | observability.py JSONL data exists |
| NT-04 | Add mcp/ to lint/typecheck | 1h | May surface existing issues | mcp/imagen/ code compiles |
| NT-05 | Build KittyBench skeleton | 4h | Test stability | 2 stable shipped packets |
| NT-06 | Study Hatchet API patterns | 2h | None (read-only) | None |
| NT-07 | Study Aider repomap | 2h | None (read-only) | None |

### Strategic (multi-session — Q3 2026)

| ID | Action | Effort | Risk | Dependencies |
|---|---|---|---|---|
| STRAT-01 | Skills cull (8 generic → archive, 3 merged) | 4h | Agent workflow disruption | Owner approval (H5) |
| STRAT-02 | Formalize evidence ledger concept | 4h | None (doc-only) | None |
| STRAT-03 | Document local-first durable execution as innovation | 4h | None (doc-only) | None |
| STRAT-04 | Evaluate Kuzu prototype | 8h | Architecture risk | memory_graph stability |
| STRAT-05 | Evaluate DSPy prototype | 4h | Prompt quality regression | context_assembler stability |
| STRAT-06 | Design full KittyBench with Braintrust patterns | 8h | None (eval-only) | NT-05 (skeleton) |

### Future Research (defer — monitor ecosystem)

| ID | Action | Trigger |
|---|---|---|
| FUT-01 | Adopt uv for package management | When pip install time becomes frustrating (>30s) |
| FUT-02 | Adopt vale for documentation consistency | When doc terminology drift is noticed |
| FUT-03 | Monitor Makefile → Earthly/poethepoet | When CI pipeline exceeds 5 jobs or needs portability |

### Blocked (owner decision required)

| ID | Action | Question |
|---|---|---|
| BLOCKED-H1 | Archive 5 root temp files | Are any in active use? |
| BLOCKED-H2 | Archive scripts/curation/ (21 files) | Is this pipeline still needed as reference? |

### Rejected (do not pursue)

| ID | Item | Reason |
|---|---|---|
| REJ-01 | Adopt external orchestration (Temporal, Hatchet, Prefect) | KittyBuilder SQLite queue is simpler and fit-for-purpose. Adopting adds a heavy runtime dependency. |
| REJ-02 | Adopt OpenTelemetry collector | Separate infrastructure for single-user app. JSONL observability is adequate. Emit OTel spans only when needed. |
| REJ-03 | Broaden ruff lint rules beyond E/F/W/I | Deliberate decision (D8). High-signal-only keeps lint actionable. |
| REJ-04 | Remove honcho.py | Verified actively imported (14 references). CLAUDE.md claim was stale. |
| REJ-05 | Delete builder.py | Verified actively used by integrations route, nudge, builder_contract. |

---

## 4. Builder Packet Breakdown

Each packet is scoped to one focused PR. Target: no packet exceeds ~200 lines changed.

### Wave A: Engineering Hygiene (IMM-01 through IMM-08)

---

**Packet A1: Fix Stale Documentation Claims**

- **Title:** Fix stale claims in CLAUDE.md and PROJECT_STATUS.md
- **Problem:** CLAUDE.md says "npm run is broken" (fixed), "honcho.py is not properly wired up" (false), and lists stale Phase B/Storage Migration references. PROJECT_STATUS.md says branch is `feat/council-routing` (actual: `feat/campaign-alpha-phase-2-integration`) and claims "No kitty-chat CI job" (has one since #51).
- **Goal:** All claims in canonical guidance docs match current repository state.
- **Acceptance criteria:**
  - `CLAUDE.md` no longer contains "npm run is broken on this machine"
  - `CLAUDE.md` no longer claims "honcho.py is not properly wired up"
  - `CLAUDE.md` sources-of-truth table no longer references `docs/phases/PHASE_B_PLAN.md` and `STORAGE_MIGRATION_PLAN.md` as current canonical docs
  - `PROJECT_STATUS.md` branch claim matches `git branch --show-current`
  - `PROJECT_STATUS.md` no longer lists "No kitty-chat CI job" under Active Technical Debt
- **Files expected:** `CLAUDE.md`, `docs/PROJECT_STATUS.md`
- **Validation:** `grep -n "npm run is broken\|not properly wired up\|PHASE_B_PLAN\|STORAGE_MIGRATION\|feat/council-routing\|No kitty-chat CI" CLAUDE.md docs/PROJECT_STATUS.md` returns no matches for stale claims
- **Dependencies:** None
- **Estimated effort:** 15min
- **Risk:** None — documentation-only
- **Rollback:** `git revert`
- **Suggested branch name:** `fix/stale-doc-claims`
- **Conventional Commit:** `docs: fix stale claims in CLAUDE.md and PROJECT_STATUS.md`

---

**Packet A2: Remove Empty Prompt Domain Slots**

- **Title:** Remove unreferenced prompt domain mappings from DOMAIN_TO_FILE
- **Problem:** `gateway/prompts.py` `DOMAIN_TO_FILE` maps 5 domains but only `soul_v1.md` exists. `load_prompt` already falls back to `soul_v1.md` when a domain file is missing. The 4 empty slots (repair, health, research, code) are dead configuration.
- **Goal:** DOMAIN_TO_FILE maps only existing prompt files.
- **Acceptance criteria:**
  - `DOMAIN_TO_FILE` contains only `"soul": "soul_v1.md"`
  - `load_prompt` falls back correctly for any domain not in the map
  - Existing tests pass
- **Files expected:** `gateway/prompts.py`
- **Validation:** `python3.12 -m pytest tests/test_prompts.py -q --tb=short`
- **Dependencies:** None
- **Estimated effort:** 15min
- **Risk:** None — fallback is already tested
- **Rollback:** `git revert`
- **Suggested branch name:** `fix/remove-empty-prompt-slots`
- **Conventional Commit:** `fix(prompts): remove empty domain slots from DOMAIN_TO_FILE`

---

**Packet A3: Add Repository Hygiene Tools to CI**

- **Title:** Add vulture, lychee, and deptry checks to CI pipeline
- **Problem:** Kitty has no automated dead-code detection, link validation, or dependency analysis. Both audits identified these as high-payoff, low-effort additions.
- **Goal:** CI pipeline catches dead code, broken links, and unused dependencies before merge.
- **Acceptance criteria:**
  - New `hygiene` CI job runs vulture against `gateway/` with `--min-confidence 80`
  - New `hygiene` CI job runs lychee against `docs/` directory
  - New `hygiene` CI job runs deptry against project root
  - All three checks pass on current HEAD (or known exceptions documented)
  - CI workflow file updated with the new job
- **Files expected:** `.github/workflows/tests.yml`
- **Validation:** CI run on PR passes the new `hygiene` job
- **Dependencies:** vulture, lychee, deptry installed in CI environment
- **Estimated effort:** 1h
- **Risk:** False positives from vulture (public API functions). Mitigate with `--min-confidence 80` and documented exceptions.
- **Rollback:** Revert CI workflow change
- **Suggested branch name:** `feat/ci-hygiene-tools`
- **Conventional Commit:** `ci: add vulture, lychee, and deptry hygiene checks`

---

**Packet A4: Add trufflehog Pre-Commit Hook**

- **Title:** Add trufflehog secret scanning to pre-commit hooks
- **Problem:** Current pre-commit only has `detect-private-key` which catches SSH/GPG keys but misses API tokens, cloud credentials, and other secrets. trufflehog has 800+ detectors.
- **Goal:** Pre-commit blocks commits containing secrets.
- **Acceptance criteria:**
  - `.pre-commit-config.yaml` includes trufflehog hook
  - Pre-commit runs trufflehog on every commit
  - No secrets detected on current HEAD
- **Files expected:** `.pre-commit-config.yaml`
- **Validation:** `pre-commit run trufflehog --all-files` passes
- **Dependencies:** trufflehog installed (`brew install trufflehog`)
- **Estimated effort:** 30min
- **Risk:** False positives on test fixtures containing fake tokens. Mitigate with `.trufflehogignore` or pre-commit `exclude` pattern.
- **Rollback:** Remove hook from `.pre-commit-config.yaml`
- **Suggested branch name:** `feat/trufflehog-precommit`
- **Conventional Commit:** `ci: add trufflehog secret scanning to pre-commit`

---

**Packet A5: Commit Codegraph Index + Freshness Check**

- **Title:** Commit .codegraph/ index and add staleness detection
- **Problem:** `.codegraph/` directory exists but is untracked and uncommitted. The code knowledge graph is initialized but inaccessible to agents on other branches or fresh clones.
- **Goal:** codegraph index is committed and a CI check warns when it's stale.
- **Acceptance criteria:**
  - `.codegraph/` added to git (`.gitignore` entry removed or adjusted)
  - New CI check (or Makefile target) compares `.codegraph/` timestamp against latest commit that changed `gateway/` files
  - Check warns (non-blocking) if index is older than 50 commits behind
- **Files expected:** `.codegraph/` (committed), `.gitignore`, `.github/workflows/tests.yml`
- **Validation:** `git ls-files .codegraph/` shows files; CI check passes on fresh index
- **Dependencies:** None
- **Estimated effort:** 30min
- **Risk:** Binary/large files in `.codegraph/` may bloat repo. Check file sizes before committing.
- **Rollback:** `git rm --cached .codegraph/` and restore `.gitignore`
- **Suggested branch name:** `feat/commit-codegraph-index`
- **Conventional Commit:** `feat(knowledge): commit codegraph index with staleness check`

---

### Wave B: Code Consolidation (NT-01 through NT-04)

---

**Packet B1: Migrate context_builder.py Callers**

- **Title:** Migrate 5 callers from context_builder facade to context_assembler
- **Problem:** `gateway/context_builder.py` is a 65-line facade whose docstring says "will be deleted in the release after context_assembler has proven stable." context_assembler has proven stable. 5 callers still import from the facade.
- **Goal:** All callers import directly from `context_assembler`; facade deleted.
- **Acceptance criteria:**
  - `gateway/researcher.py` imports `build_worker_context` from `context_assembler`
  - `gateway/troubleshooter.py` imports `build_worker_context` from `context_assembler` (or logic inlined if trivial)
  - `gateway/voice_pipeline.py` imports `get_system_prompt` from `context_assembler`
  - `gateway/telegram_bot.py` imports `get_system_prompt` from `context_assembler`
  - `gateway/reset.py` imports `build_worker_context` from `context_assembler`
  - `gateway/context_builder.py` deleted
  - All existing tests pass
- **Files expected:** `gateway/context_builder.py` (delete), `gateway/researcher.py`, `gateway/troubleshooter.py`, `gateway/voice_pipeline.py`, `gateway/telegram_bot.py`, `gateway/reset.py`
- **Validation:** `python3.12 -m pytest tests/ -q --tb=short -k "researcher or troubleshooter or voice or telegram or reset"`
- **Dependencies:** None
- **Estimated effort:** 2h
- **Risk:** Import behavior change — context_builder re-exports `ContextBundle`, `assemble_context`, and `assert_not_total_failure` from context_assembler. Verify these are the same objects.
- **Rollback:** Restore `context_builder.py` and revert import changes
- **Suggested branch name:** `refactor/migrate-context-builder-callers`
- **Conventional Commit:** `refactor(context): migrate context_builder callers to context_assembler, delete facade`

---

**Packet B2: Consolidate builder.py ISC Logic**

- **Title:** Merge ISC derivation from builder.py into builder_queue/builder_attempt
- **Problem:** `gateway/builder.py` (470 lines) contains ISC derivation (`_derive_sys`, `_check_sys`) and an autonomous build pipeline. The autonomous pipeline is actively used (integrations route, nudge, builder_contract) but the ISC logic duplicates what `builder_attempt.py` needs for packet validation. builder.py also uses a separate DB (`BUILDS_DB`) from the queue DB (`BUILDER_QUEUE_DB`).
- **Goal:** ISC derivation lives in one canonical location; builder.py retains only the autonomous pipeline surface.
- **Acceptance criteria:**
  - ISC derivation functions (`_derive_sys`, `_check_sys`, `MAX_CRITERIA`) extracted to a shared location (e.g., `gateway/builder_isc.py` or folded into `builder_attempt.py`)
  - `gateway/builder.py` imports ISC functions from the shared location
  - `gateway/builder_attempt.py` uses ISC functions from the shared location (if not already)
  - All existing tests pass (`test_builder.py`, `test_builder_attempt.py`, `test_success_criteria.py`)
- **Files expected:** `gateway/builder.py`, `gateway/builder_attempt.py`, new `gateway/builder_isc.py` (optional)
- **Validation:** `python3.12 -m pytest tests/test_builder.py tests/test_builder_attempt.py tests/test_success_criteria.py -q --tb=short`
- **Dependencies:** None
- **Estimated effort:** 4h
- **Risk:** ISC prompt constants (`_DERIVE_SYS`, `_CHECK_SYS`) must produce identical LLM behavior. Test via golden-file comparison if prompt text changes.
- **Rollback:** `git revert`
- **Suggested branch name:** `refactor/consolidate-builder-isc`
- **Conventional Commit:** `refactor(builder): consolidate ISC derivation from builder.py into shared module`

---

**Packet B3: Wire LLM Spend Report into Doctor**

- **Title:** Add `./kitty doctor --spend` command exposing LLM cost data
- **Problem:** `gateway/observability.py` collects LLM call data to JSONL but has no surfacing. `gateway/token_spend_report.py` and `scripts/spend_report.py` are separate reporting surfaces. Users have no CLI visibility into model costs.
- **Goal:** `./kitty doctor --spend` prints a concise spend summary from existing JSONL data.
- **Acceptance criteria:**
  - `./kitty doctor --spend` prints: total calls, total tokens (prompt + completion), estimated cost, top models by usage
  - `--json` flag outputs machine-readable format
  - Reads from existing `data/llm_calls.jsonl` and `data/kitty_token_log.jsonl`
  - Gracefully handles missing/empty log files (reports "no data")
- **Files expected:** `gateway/doctor.py` (or new `gateway/spend_report.py` if consolidated)
- **Validation:** `./kitty doctor --spend` and `./kitty doctor --spend --json` produce output on local data
- **Dependencies:** Existing observability JSONL files must exist
- **Estimated effort:** 2h
- **Risk:** None — read-only, existing data
- **Rollback:** `git revert`
- **Suggested branch name:** `feat/doctor-spend-report`
- **Conventional Commit:** `feat(doctor): add --spend flag for LLM cost visibility`

---

**Packet B4: Add mcp/ to CI Lint and Typecheck**

- **Title:** Extend CI lint and typecheck targets to cover mcp/ directory
- **Problem:** L-CAND-7: `mcp/` is not linted or typechecked in CI. The imagen server was broken for multiple commits with no check catching it. Ruff lints only `gateway/ tests/`; mypy runs only `gateway/`.
- **Goal:** `mcp/` code is statically checked in CI alongside `gateway/`.
- **Acceptance criteria:**
  - CI lint job runs `ruff check mcp/` (additionally, not replacing gateway/tests)
  - CI typecheck job runs `mypy mcp/` (additionally)
  - Any existing findings are fixed or explicitly excluded with justification
  - Tests that import from `mcp/` continue to pass
- **Files expected:** `.github/workflows/tests.yml`, possibly `mcp/imagen/*.py` (if fixes needed)
- **Validation:** CI run passes lint and typecheck for mcp/
- **Dependencies:** `mcp/` code must be lint-clean (or tolerate findings being surfaced)
- **Estimated effort:** 1h
- **Risk:** May surface latent issues in `mcp/imagen/`. Mitigate: fix in same PR or exclude specific files with comment.
- **Rollback:** Revert CI workflow change
- **Suggested branch name:** `fix/ci-mcp-lint-typecheck`
- **Conventional Commit:** `ci: add mcp/ to lint and typecheck targets`

---

### Wave C: Evaluation & Research (NT-05 through NT-07, STRAT-01 through STRAT-06)

---

**Packet C1: KittyBench Skeleton**

- **Title:** Build KittyBench evaluation skeleton with 2 historical packet fixtures
- **Problem:** Kitty has no regression benchmarks for Builder packet execution. A packet that passes validation today could silently regress on a refactor. Both audits recommend a lightweight benchmark.
- **Goal:** A `tests/bench/` directory with 2 replay fixtures and a runner that catches regressions.
- **Acceptance criteria:**
  - `tests/bench/` directory exists with README
  - 2 shipped packets selected as fixtures (packets that pass on current HEAD)
  - Runner script re-executes each packet's validation commands and reports pass/fail
  - Runner can be invoked via `python3.12 -m pytest tests/bench/ -v`
  - Fixture packets are documented with: packet ID, what they test, why they were chosen
- **Files expected:** `tests/bench/__init__.py`, `tests/bench/conftest.py`, `tests/bench/test_packet_*.py`, `tests/bench/README.md`
- **Validation:** `python3.12 -m pytest tests/bench/ -v` passes on current HEAD
- **Dependencies:** 2 stable shipped packets with deterministic validation commands
- **Estimated effort:** 4h
- **Risk:** Flaky packets — choose packets with no network-dependent or timing-dependent validation
- **Rollback:** Delete `tests/bench/` directory
- **Suggested branch name:** `feat/kittybench-skeleton`
- **Conventional Commit:** `test: add KittyBench skeleton with 2 replay fixtures`

---

**Packet C2: Hatchet API Pattern Study**

- **Title:** Document Hatchet's durable task API patterns relevant to KittyBuilder
- **Problem:** KittyBuilder queue is a custom SQLite state machine. Hatchet is the closest mature reference for durable task APIs. Studying their patterns can improve KittyBuilder's queue without adopting Hatchet.
- **Goal:** A concise reference document identifying which Hatchet design patterns KittyBuilder should adopt and which it already implements.
- **Acceptance criteria:**
  - `docs/reference/hatchet-patterns.md` created
  - Documents: task lifecycle comparison, lease management patterns, retry policy design, heartbeat strategy
  - Identifies 2-3 concrete improvements for `builder_queue.py`
  - Identifies patterns KittyBuilder already implements correctly
- **Files expected:** `docs/reference/hatchet-patterns.md`
- **Validation:** Document reviewed for accuracy against Hatchet source
- **Dependencies:** None (read-only)
- **Estimated effort:** 2h
- **Risk:** None — read-only research
- **Rollback:** N/A (new doc, revert if inaccurate)
- **Suggested branch name:** `docs/hatchet-pattern-study`
- **Conventional Commit:** `docs(reference): add Hatchet API pattern study for Builder queue`

---

**Packet C3: Aider Repomap Study**

- **Title:** Document Aider's repomap generation approach for Kitty agent context
- **Problem:** Kitty's codegraph + codemap provide structural and conceptual code understanding. Aider's repomap generates LLM-optimized codebase summaries. Comparing the two approaches could improve Kitty's agent context assembly.
- **Goal:** A reference document comparing Aider's repomap against Kitty's current code knowledge model.
- **Acceptance criteria:**
  - `docs/reference/aider-repomap-study.md` created
  - Documents: repomap algorithm overview, token budget strategy, comparison to codegraph output
  - Identifies whether repomap-style output would improve Kitty's agent context (e.g., in context bundles for Builder workers)
- **Files expected:** `docs/reference/aider-repomap-study.md`
- **Validation:** Document reviewed for accuracy against Aider source (`aider/repomap.py`)
- **Dependencies:** None (read-only)
- **Estimated effort:** 2h
- **Risk:** None — read-only research
- **Rollback:** N/A
- **Suggested branch name:** `docs/aider-repomap-study`
- **Conventional Commit:** `docs(reference): add Aider repomap study for agent context`

---

## 5. Permanent Doctrine Update Recommendations

### Changes to CLAUDE.md

```diff
- ## Commands
- bash scripts/preflight.sh
- npm run is broken on this machine (exit 194)

+ ## Commands
+ bash scripts/preflight.sh
+ make ui-test && make ui-build   # prefer Makefile targets over npm run

- "Honcho" → external mirror service, not properly wired up

+ "Honcho" → `gateway/honcho.py` — weekly pattern mirror, wired to kitty_tools route

- | Phase B plan        | `docs/phases/PHASE_B_PLAN.md`           |
- | Storage migration   | `docs/phases/STORAGE_MIGRATION_PLAN.md` |

+ | Phase B plan        | `docs/phases/PHASE_B_PLAN.md`           | (shipped — historical reference)
+ | Storage migration   | `docs/phases/STORAGE_MIGRATION_PLAN.md` | (shipped — historical reference)
```

### Changes to PROJECT_STATUS.md

```diff
- **Branch:** `feat/council-routing` (based on `main`)

+ **Branch:** `feat/campaign-alpha-phase-2-integration` (based on `main`)

- | No kitty-chat CI job | `.github/workflows/` | High — add a UI test job |
- | SIRI_SHORTCUT.md references dead launcher | `docs/SIRI_SHORTCUT.md` | Low — tombstone it |

+ | SIRI_SHORTCUT.md references dead launcher | `docs/SIRI_SHORTCUT.md` | Low — tombstone it |
```

### New sections for ARCHITECTURE.md

Add after "Architecture Rules" section:

```markdown
## Leverage Doctrine

Kitty's engineering philosophy for build-vs-adopt decisions.

### Never Build Again
Do not build: dead code detectors (use vulture), secret scanners (use trufflehog),
link checkers (use lychee), dependency analyzers (use deptry), tracing standards
(use OpenTelemetry), graph databases (use Kuzu), workflow engines (use Hatchet if
queue becomes insufficient), code formatters (use ruff/prettier), or release
automation (use GitHub Actions).

### Strategic Ownership
Kitty must own forever: Builder packet lifecycle, initiative model, reasoning
policy engine (OBSERVE→ORIENT→DECIDE→ACT→VERIFY→LEARN), repository knowledge
model (codegraph + codemap + ADRs + packets + memory_graph), evidence ledger
(attempt→review→publish chain with SHA-256 proofs), durable attempts with worktree
isolation, lease semantics, privacy boundary (D10), and life-first ordering
(ADR 0016).

### Decision Framework
1. Scout: find the best external project in the lane
2. Compare: can Kitty's implementation match or exceed it?
3. Prototype: if unsure, run a time-boxed experiment
4. Build or Adopt: decide with evidence

Rule of thumb: if we started today, would we build this again or adopt the
mature upstream? The answer must be defensible with evidence, not preference.
```

### New ADR: ADR-0017 — Leverage Before Reinvention

Create `docs/adr/0017-leverage-before-reinvention.md` codifying the Never Build Again registry and Strategic Ownership registry as permanent architecture decisions.

### New file: `docs/UPSTREAMS.md`

Design below (Section 6).

---

## 6. Upstream Registry Design

Create `docs/UPSTREAMS.md` as the canonical registry of external projects Kitty references, adopts, or benchmarks against. Each entry records:

```markdown
## <project-name>

- **Repository:** <github-url>
- **Purpose:** <one-line description>
- **Lane:** <from the 14 engineering domains>
- **Role:** dependency | reference | prototype-candidate | benchmark | rejected
- **Owner:** <who on the Kitty team owns the relationship>
- **Review cadence:** quarterly | annually | on-trigger
- **Adopted because:** <exact Kitty problem it solves>
- **License:** <SPDX identifier>
- **Risk:** low | medium | high (<explanation>)
- **Status:** adopted | evaluating | reference-only | rejected
- **Revisit trigger:** <what would cause us to reconsider>
- **Do NOT copy:** <specific patterns/choices in this project that Kitty should deliberately diverge from>
```

### Populate with initial entries from the external audit:

| Project | Role | Status |
|---|---|---|
| hatchet-dev/hatchet | reference | reference-only |
| Aider-AI/aider | reference | reference-only |
| temporalio/temporal | reference (rejected for adoption) | reference-only |
| tree-sitter/tree-sitter | dependency (indirect, via ast-grep/codegraph) | adopted |
| ast-grep/ast-grep | dependency | adopted |
| BerriAI/litellm | dependency | adopted |
| langfuse/langfuse | reference | reference-only |
| run-llama/llama_index | reference | reference-only |
| kuzudb/kuzu | prototype-candidate | evaluating |
| e2b-dev/e2b | reference | reference-only |
| jendrikseipp/vulture | dependency | adopted |
| lycheeverse/lychee | dependency | adopted |
| trufflesecurity/trufflehog | dependency | adopted |
| fpgmaas/deptry | dependency | adopted |
| microsoft/playwright | dependency | adopted |
| stanfordnlp/dspy | prototype-candidate | evaluating |
| braintrustdata/braintrust | reference | reference-only |
| dbos-inc/dbos-transact | reference | reference-only |
| riverqueue/river | reference | reference-only |
| errata-ai/vale | prototype-candidate | evaluating |
| astral-sh/uv | dependency candidate | evaluating |
| jdx/mise | dependency candidate | evaluating |
| codegraph (in-repo) | dependency | adopted |

---

## 7. Architecture Roadmap

### Wave A — Engineering Hygiene (Week 1)
**Goal:** Zero stale claims, automated code/doc quality gates.

```
A1 → A2 → A3 → A4 → A5
(fix docs) → (clean prompts) → (CI tools) → (secrets) → (codegraph)
```

These are all independent and can run in parallel except A5 should come after A3 (codegraph check is part of CI).

**Packets:** A1, A2, A3, A4, A5
**Estimated total:** 2.5 hours
**Dependencies:** None external

### Wave B — Code Consolidation (Weeks 1-2)
**Goal:** Remove dead facade, consolidate ISC logic, surface observability data, close CI gaps.

```
B1 → B2 → B3 → B4
```

B1 and B2 are independent of each other. B3 and B4 are independent. Run in parallel where possible.

**Packets:** B1, B2, B3, B4
**Estimated total:** 9 hours
**Dependencies:** Wave A complete (CI must be clean before code changes)

### Wave C — Evaluation & KittyBench (Weeks 2-3)
**Goal:** Regression benchmark, upstream pattern research.

```
C1 → C2 → C3
```

C1 (KittyBench skeleton) is independent of C2/C3. C2/C3 are research only and can run in parallel with C1.

**Packets:** C1, C2, C3
**Estimated total:** 8 hours
**Dependencies:** C1 needs 2 stable shipped packets

### Wave D — Reasoning Engine Foundation (Week 3-4)
**Goal:** Document architectural innovations, formalize core concepts.

```
STRAT-02 → STRAT-03
```
(evidence ledger) → (local-first durable execution)

**Estimated total:** 8 hours
**Dependencies:** None — documentation only

### Wave E — Long-Term Architecture (Q3 2026)
**Goal:** Evaluate graph DB, prompt optimization, full eval framework.

```
STRAT-01 → STRAT-04 → STRAT-05 → STRAT-06
(skills cull) → (Kuzu eval) → (DSPy eval) → (Braintrust eval)
```

STRAT-01 is blocked on owner approval. STRAT-04/05/06 are independent evaluations.

**Estimated total:** 24 hours across Q3
**Dependencies:** STRAT-01 blocked on owner (H5)

---

## 8. Recommended First 10 Implementation PRs

In priority order, each independently reviewable:

| # | Packet | Title | Branch | Effort | Waves |
|---|---|---|---|---|---|
| 1 | A1 | Fix stale CLAUDE.md and PROJECT_STATUS.md claims | `fix/stale-doc-claims` | 15min | A |
| 2 | A2 | Remove empty prompt domain slots | `fix/remove-empty-prompt-slots` | 15min | A |
| 3 | A3 | Add vulture, lychee, deptry to CI | `feat/ci-hygiene-tools` | 1h | A |
| 4 | A4 | Add trufflehog to pre-commit | `feat/trufflehog-precommit` | 30min | A |
| 5 | A5 | Commit codegraph index + freshness | `feat/commit-codegraph-index` | 30min | A |
| 6 | B1 | Migrate context_builder callers | `refactor/migrate-context-builder-callers` | 2h | B |
| 7 | B4 | Add mcp/ to CI lint/typecheck | `fix/ci-mcp-lint-typecheck` | 1h | B |
| 8 | B3 | Wire ./kitty doctor --spend | `feat/doctor-spend-report` | 2h | B |
| 9 | C1 | KittyBench skeleton | `feat/kittybench-skeleton` | 4h | C |
| 10 | B2 | Consolidate builder ISC logic | `refactor/consolidate-builder-isc` | 4h | B |

---

## 9. Risks and Sequencing Notes

### Risks
1. **vulture false positives** — public API functions flagged as dead. Mitigate with `--min-confidence 80` and a documented exceptions list.
2. **context_builder migration** — 5 callers with different import patterns. Mitigate by testing each caller's module individually before full suite.
3. **trufflehog false positives** — test fixtures with fake tokens/keys. Mitigate with `.trufflehogignore` or pre-commit `exclude`.
4. **codegraph binary bloat** — index files may be large. Verify total size before committing. If >5MB, consider git-lfs or `.gitattributes` with diff strategy.
5. **KittyBench flakiness** — packets with network/time-dependent validation will produce false regressions. Select only deterministic packets.

### Sequencing
- **Wave A is fully parallelizable** — all 5 packets touch different files and can be implemented simultaneously.
- **Wave B requires Wave A complete** — CI must be clean before refactoring code.
- **Wave C is independent of A and B** — research packets (C2, C3) and KittyBench (C1) don't touch existing code.
- **Wave D is documentation-only** — can run anytime, even in parallel with B/C.
- **Wave E is blocked** — owner decisions (H1, H2, H5) and requires C1 (KittyBench skeleton) to inform STRAT-04/05/06 design.

### Dependencies between waves
```
Wave A ──→ Wave B ──→ Wave C ──→ Wave E
                              └──→ Wave D (parallel)
```

---

*This plan is the implementation blueprint. Next action: present Wave A packets for owner approval and begin PR #1 (A1: fix stale doc claims).*
