# Skill Registry

Single source of truth for every skill bundled with this repo. User-installed
skills under home-directory tool configs are intentionally excluded.

**Last verified:** 2026-09-16 — second pass on this date. First pass registered
the four engineering skills added 2026-09-08 and added the upkeep family. The
second pass (a) added `audit-architecture` to the upkeep family, (b) archived
three skills, then restored `isa` on the ported-skills test's evidence —
`expert-swarm` and `provider-credit-debugging` stay archived, (c)
recorded the dual-location arrangement for the four `.claude/skills/` entries,
(d) added `tests/test_documentation_authority.py` as the enforcement for frontmatter
strictness, spec limits, registry sync, and trigger-phrase matching, and (e)
disabled 20 non-Kitty global skills for this project via
`.commandcode/settings.json`.

## Canonical skill locations

| Path | Purpose | Loaded by |
|---|---|---|
| `.claude/skills/` | Repo-local Claude Code skills | Claude Code native discovery |
| `.agents/skills/` | Repo-local cross-tool agent skills | OpenCode / agents; Claude and Codex route through `START_HERE.md`, `CLAUDE.md`, and `AGENTS.md`; Command Code and the Kitty gateway registry discover them directly |

**Dual-location rule (recorded 2026-09-16):** the four skills that exist in both
`.claude/skills/` and `.agents/skills/` are intentionally dual-published so both
native Claude discovery and the cross-tool consumers (`gateway/skill_registry.py`,
Command Code, OpenCode) see them. The copies must stay content-identical except
for consumer-specific document references (`CLAUDE.md` vs `AGENTS.md` in
`second-opinion` is the accepted example). The canonical-owner rule is retired:
any *other* cross-location duplicate is a defect. No files were moved or deleted
by the audits that found this arrangement.

## Skill families (2026-09-16)

- **Improvement family** (`engineering/`): `improve-codebase` (router) →
  `improve-codebase-architecture` (internal shape) / `harden-codebase` (runtime
  failure behaviour + dependency boundary) / `improve-daily-ux` (user surface) /
  `verify-by-mutation` (test trustworthiness).
- **Upkeep family** (`engineering/`): `maintain-repo` (router) → `audit-docs`
  (written truth) / `audit-workflow` (process and enforcement truth) /
  `audit-architecture` (documented-design conformance) / dependency lane →
  `harden-codebase` (its recorded boundary, not a separate skill).
- Routers triage and route; specialists are the owners and cross-route freely.
  `aim42-software-improvement` remains the strategy method for modernization
  (legacy assessment, debt, migration planning) — not routine upkeep.

## Skills by location

### `.claude/skills/` (4 skills)

| Skill | Verified | Verdict | Why |
|---|---|---|---|
| catchup | 2026-09-16 | KEEP | Rebuilds session context; dual-published in `.agents/skills/` |
| debug-fix | 2026-09-16 | KEEP | Active bug-fixing workflow; dual-published |
| remember | 2026-09-16 | KEEP | Persists durable preferences (backs `/remember` in `config/PREFERENCES.md`); dual-published |
| second-opinion | 2026-09-16 | KEEP | Independent model review before asking Jacob; dual-published, one consumer-specific doc reference differs by design |

### `.agents/skills/` (21 active + 12 archived)

| Skill | Verified | Verdict | Why |
|---|---|---|---|
| agent-council | 2026-08-10 | KEEP | Fans an explicit council request to read-only local Codex/Claude/OpenCode workers; `scripts/agent_council.py` driver |
| aim42-software-improvement | 2026-08-03 | KEEP | Evidence-first modernization workflow (analyze→evaluate→improve→verify); referenced by `AGENTS.md`, `docs/contracts/OPERATING_CONTRACTS.md`, and `tests/test_aim42_skill.py` |
| catchup | 2026-09-16 | KEEP | Rebuilds session context; dual-published canonical pair |
| debug-fix | 2026-09-16 | KEEP | Active bug-fixing workflow; dual-published canonical pair |
| engineering/audit-architecture | 2026-09-16 | KEEP | Upkeep family: documented-design conformance specialist (boundaries, owners, ADRs, layout); boundary test |
| engineering/audit-docs | 2026-09-16 | KEEP | Upkeep family: documentation staleness, drift, and opportunity specialist; claim test; dispositions feed existing authorities and `docs/audit/` evidence |
| engineering/audit-workflow | 2026-09-16 | KEEP | Upkeep family: delivery/enforcement machinery auditor (ghost, paper, orphaned gates; stale enforcement claims); gate test; builds on `PREVENTION_MECHANISMS.md` status vocabulary and the workflow ledger |
| engineering/harden-codebase | 2026-09-08 | KEEP | Runtime failure-behaviour specialist; fail-loud test; owns the dependency boundary and its executable procedure (`DEPENDENCY-AUDIT.md`) |
| engineering/improve-codebase | 2026-09-08 | KEEP | Improvement-family router; triages shape/behaviour/surface/tests; cross-routes upkeep lanes to `maintain-repo` |
| engineering/improve-codebase-architecture | 2026-05-21 | KEEP | Architecture improvement guided by domain docs; deletion test; deepening opportunities |
| engineering/improve-daily-ux | 2026-09-08 | KEEP | User-surface specialist for loading/empty/error/degraded/stale states, copy, and recovery; daily-touch test; `AsyncState` grounding |
| engineering/maintain-repo | 2026-09-16 | KEEP | Upkeep-family router; routes docs, workflow, architecture conformance, and dependency staleness/drift; cross-routes code layers to `improve-codebase` |
| engineering/verify-by-mutation | 2026-09-08 | KEEP | Test-trustworthiness specialist; mutation test; a vacuous pass is a fake pass |
| image-gen | 2026-07-21 | KEEP | Wired to the live ComfyUI/runpod image workers (`workers/comfy_worker/`, `mcp/imagen/`, `runpod-image-build.yml`) |
| isa | 2026-09-16 | KEEP | Retained active member of the PAI port (`tests/test_ported_skills.py` encodes the decision); description compressed under the 1024-char spec limit 2026-09-16 so strict-YAML consumers load it |
| journal-entry | 2026-07-21 | KEEP | Wired to the Kitty journal subsystem (`gateway/journal.py`); also the representative fixture in `tests/test_skill_registry.py` |
| next | 2026-08-01 | KEEP | Continues one valid interactive assignment; inspects Builder for collisions but never consumes its queue without explicit Builder intent |
| orca-orchestration | 2026-09-03 | KEEP | Parallel/phased Builder execution layer; touched 2026-09-03 |
| remember | 2026-09-16 | KEEP | Persists durable preferences; dual-published canonical pair |
| second-opinion | 2026-09-16 | KEEP | Independent model review before asking Jacob; dual-published canonical pair |
| session-end | 2026-08-01 | KEEP | Surveys live work, preserves evidence/continuity, records execution ownership, writes a strict KB-effectiveness receipt, extracts durable knowledge/corrections, and records workflow signals |
| verified-delivery | 2026-08-06 | KEEP | Evidence-bound outcome contract; distinguishes implementation checks from independent verification; provider-agnostic compaction/handoff contract |

Deleted 2026-07-21 after verification/confirmation: `debug-issue`,
`explore-codebase`, `refactor-safely`, `review-changes`, `autonomy_tune`, and
`tune`.

Archived 2026-07-21 under `.agents/skills/_archive/`: `extract-wisdom`,
`first-principles`, `iterative-depth`,
`iterative-self-review-meta-optimization`, `red-team`,
`root-cause-analysis`, `science-method`, and `systems-thinking`.

Archived 2026-09-16 under `.agents/skills/_archive/` (lean-out, content
preserved and restorable with one `git mv`). `isa` was archived in the first
pass and restored the same day: `tests/test_ported_skills.py` encodes a
standing decision that it is the one active member of the PAI port, and the
lean-out had no evidence strong enough to overturn that. Remaining:

- `expert-swarm` — registry verdict was UNVERIFIED ("low historical usage;
  requires Jacob confirmation before archive"); touched 2026-07-23; no active
  references beyond this registry.
- `provider-credit-debugging` — built around provider routers that current
  `AGENTS.md` marks dead or optional-only ("AgentRouter is dead", "Freebuff and
  9Router are optional only"); untouched since 2026-07-21; no active references.

Archived here means inert for Kitty's own registry: `gateway/skill_registry.py`
excludes the top-level `_archive` namespace, enforced by
`tests/test_skill_registry.py`. External recursive discovery (Command Code)
still enumerates `_archive/`; where that matters, a machine-local, gitignored
`.commandcode/settings.json` → `disabledSkills` entry hides the archived names
from invocation. That entry is local hygiene, not a tracked repo contract —
the tracked guarantee is the Kitty-registry exclusion.

## Recorded human decisions

- **H5**: archive the eight unused generic reasoning skills while preserving
  their content.
- **H6** (2026-09-03 repository documentation consolidation): archive the
  superseded `mcp-kitty-council` skill after verifying its MCP server/orchestrator
  targets are gone and `agent-council` is the current council procedure.
- **H7** (2026-09-16): add the repository-upkeep family — `maintain-repo` router
  plus `audit-docs` and `audit-workflow` specialists — and give the dependency
  boundary an executable procedure (`harden-codebase/DEPENDENCY-AUDIT.md`).
  Dependency hygiene remains a facet of `harden-codebase`; no separate
  dependency skill was created. The four engineering skills added 2026-09-08
  were registered in the same walk.
- **H8** (2026-09-16 lean-out, Jacob's request): archive the three unused skills
  above; add `audit-architecture` as the upkeep family's conformance specialist;
  retire the canonical-owner duplicate rule in favour of the dual-location rule;
  disable 20 non-Kitty global skills for this project in
  `.commandcode/settings.json`; add `tests/test_documentation_authority.py` to enforce
  strict frontmatter parsing, spec limits, registry sync, and trigger-phrase
  matching.
- **Interactive continuation boundary** (corrected 2026-08-01): bare `next`
  continues the current interactive Claude Code/OpenCode/Codex assignment. It
  does not apply initiatives, select packets, or drain Builder. Explicit
  `builder next` or a valid Builder bundle enters Builder's lane.
- **Single execution owner** (2026-08-01): every implementation is owned by
  exactly one of `interactive` or `builder`. Review does not transfer ownership.
- **Learning without a second backlog** (ADR 0025): session-end records evidence
  signals in `~/kb`; execution promotion remains governed and deduplicated.
- **Measured KB effectiveness** (2026-08-01): session-end writes a hash-chained,
  tamper-evident receipt through `scripts/kb_effectiveness.py`. Unknown token,
  time, cost, and quality measurements stay null. Cohort comparisons are
  observational and do not prove causation.

## Supporting scripts

| Script | Purpose | Authority boundary |
|---|---|---|
| `scripts/session_learning.py` | Record repeated workflow failures/corrections | Evidence only; no automatic issue or Builder task |
| `scripts/kb_effectiveness.py` | Record KB retrieval/outcome receipts and produce rolling reports | Measurement only; no roadmap, queue, issue, or priority mutation |
| `scripts/session_end_survey.sh` | Read-only field inventory | Must report unavailable sources honestly |
| `tests/test_documentation_authority.py` | Enforce strict frontmatter YAML, spec limits, registry sync, glossary include expansion, and literal trigger-phrase routing for the engineering family | Test only; fails the suite, changes nothing |

## Freshness check

Re-verify this file whenever:

- a skill is added, removed, merged, archived, or rewired;
- a supported coding tool changes its `next` semantics;
- session-end changes its KB, continuity, or measurement contract;
- the leverage audit runs; or
- this verification date is older than 90 days.

The 2026-08-01 re-walk verified that bare `next` is interactive-only,
Builder remains autonomous, session-end records exactly one execution owner, and
KB effectiveness is measured without creating another execution authority.

The 2026-09-03 re-walk inventoried the tree directly: 4 `.claude/skills/`
entries (`catchup`, `debug-fix`, `remember`, `second-opinion`), 12 active
`.agents/skills/` entries, and 9 archived entries under
`.agents/skills/_archive/`. The legacy `mcp-kitty-council` skill was archived on
2026-09-03 after its server/orchestrator targets were removed and
`agent-council` became the current read-only council procedure. `expert-swarm`
stayed UNVERIFIED pending Jacob's confirmation until the 2026-09-16 lean-out.

The 2026-09-16 re-walk (two passes, same date) registered the four engineering
skills added 2026-09-08, added the upkeep family (`maintain-repo`, `audit-docs`,
`audit-workflow`, then `audit-architecture`) and the executable dependency
procedure, archived three unused skills with the evidence recorded above, and
recorded the dual-location arrangement. Counts after this walk: 4
`.claude/skills/`, 21 active `.agents/skills/`, 12 archived. Enforcement lives in
`tests/test_documentation_authority.py`; it fails the suite if an active skill stops parsing
as strict YAML, exceeds the Agent Skills limits, disappears from this registry,
or stops matching its advertised trigger phrases.
