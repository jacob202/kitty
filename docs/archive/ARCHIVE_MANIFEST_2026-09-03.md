# Archive Manifest — 2026-09-03 docs consolidation

**Task:** `.superpowers/sdd/repository-documentation-consolidation-20260903/archive.md`
(history/organization lane). Remove misleading current-looking legacy material
from the active docs surface while preserving useful history and stable provenance.
**Method:** `git mv` with established compatibility-pointer discipline. Before
each move, inbound references were searched across current authorities, ADRs,
decisions, code, tests, and scripts. Load-bearing or widely-cited paths kept a
short compatibility pointer at the original path; low/no-reference dated
snapshots were moved without a stub and their small number of meaningful inbound
links were repaired. Accepted decision history (ADR bodies, `docs/decisions/`)
was preserved verbatim — no historical link was mass-edited; pointers keep those
references resolving instead.
**Scope:** this worktree only. No commit. Excluded paths (README, START_HERE,
AUTHORITY_MAP, current ADRs/DECISIONS, `docs/packets/*`, runtime code, active
initiative manifests) were not modified.

## Archive groups created

| Group | Path | Contents |
|---|---|---|
| Planning | `docs/archive/planning-2026-07-24/` | 7 frozen `docs/planning/` files |
| Recon | `docs/archive/recon-2026-07/` | `docs/recon/` files + the agent-leverage experiment dir |
| Legacy snapshots | `docs/archive/legacy-snapshots/` | 11 flat dated/orphan status snapshots |
| Superseded design | `docs/archive/superseded-design/` | 9 superseded/unratified large design families |
| Documentation audit | `docs/archive/audits-2026-07/DOCUMENTATION_AUDIT.md` | stale 2026-07-30 doc-health audit (joined existing 2026-07 audits) |

## Moved WITH a compatibility pointer (stub left at original path)

A stub was left where the old path is load-bearing or cited by accepted
ADR/decision history that must not be edited. Each stub says it is
historical/non-authoritative and links to the archived copy; none repeats the old
document's status or phase sequence.

### Superseded/unratified design families → `docs/archive/superseded-design/`

| Original path | Why archived | Superseding authority | Why stubbed |
|---|---|---|---|
| `docs/BLUEPRINT.md` | 2026-07-11 product direction; predates Constitution and ADRs 0027–0036 | `NORTH_STAR.md`, `ARCHITECTURE.md`, ratified ADRs | Cited as source by ADR 0015; cited by ADRs 0028/0032/0035 and `NORTH_STAR.md`; path read by runtime code (see note) |
| `docs/BUILDER_ORGANIZATION.md` | 2026-08-05 unratified 16-role org design | ADR 0017/0036; `ARCHITECTURE_RATIFICATION_2026-08-06.md` Decision 4 | Cited by `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` |
| `docs/BUILDER_V2.md` | 2026-08-05 unratified engine-replacement blueprint | ADR 0017/0036; `ARCHITECTURE_RATIFICATION_2026-08-06.md` Decision 4 | Cited by `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` |
| `docs/KITTY_PRODUCT_ARCHITECTURE.md` | 2026-07 large architecture + aspirational execution plan | `ARCHITECTURE.md`, `ALIGNMENT_MAP.md`, `ROADMAP.md` (ADR 0017 amended the boundary) | Cited by `CAPABILITY_MANIFEST.md` and `PLANS.md` as authority |
| `docs/KITTY_MASTER_PROGRAM.md` | 2026-08-05 derived synthesis; supersede claim rejected | `ROADMAP.md` (ADR 0020); `ARCHITECTURE_RATIFICATION_2026-08-06.md` Decision 5 | Real markdown link from `docs/README.md`; cited by `AUTHORITY_MAP.md` and `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` |
| `docs/OPENWEBUI_PRODUCT_PLAN.md` | 2026-08-05 product plan; research input | ADR 0027/0033 (replaceable shell); `NORTH_STAR.md` | Cited by `CAPABILITY_MANIFEST.md` and `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` |
| `docs/OPENWEBUI_OS_ARCHITECTURE.md` | 2026-08-05 research; "permanent UI" framing rejected | ADR 0027/0033; Constitution I.2; `ARCHITECTURE_RATIFICATION_2026-08-06.md` Decision 1 | Cited by `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` |
| `docs/OPENWEBUI_EXTENSION_BACKLOG.md` | 2026-08-05 ranked extension inventory; research input | ADR 0027/0033; `ROADMAP.md` | Cited by `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` |
| `docs/OPERATOR_STRATEGY.md` | 2026-07-01 product archaeology + 30-day plan | `ROADMAP.md`, `ARCHITECTURE.md`, `ALIGNMENT_MAP.md` | Cited by ADRs 0010/0011/0012 and `docs/packets/README.md` |

### Dated/orphan snapshots → `docs/archive/legacy-snapshots/`

| Original path | Why archived | Superseding authority | Why stubbed |
|---|---|---|---|
| `docs/FEATURE_REALITY_2026-07-28.md` | 2026-07-28 point-in-time capability reality check | `PROJECT_STATUS.md`, runtime evidence | Listed in the active `repomix.config.json` include bundle (archive is ignored by repomix) and cited by `reference/CODEBASE_MAP.md`; stub keeps the include valid without editing config |
| `docs/INITIATIVES_OPTIMIZED_2026-07-24.md` | 2026-07-24 feature-sequencing claim; predates ADR 0020 | `ROADMAP.md` (ADR 0020) | Cited by ADR 0020 |
| `docs/CONTINUITY_RECOVERY.md` | 2026-08-05 full-repo recovery snapshot; verified-state now stale | `ACTIVE_MISSION.md`, live Builder/GAR/Git evidence | Cited by a `docs/superpowers/plans/` plan (protected lane) and `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` |

### Recon → `docs/archive/recon-2026-07/`

| Original path | Why archived | Superseding authority | Why stubbed |
|---|---|---|---|
| `docs/recon/REPO_SCOUTING_2026-07-24.md` | 2026-07-24 repo scouting snapshot | ADR 0028 (the durable decision) | Cited as a research source by ADR 0028 |

## Moved WITHOUT a stub (low/no current-surface reference)

Internal cross-references among these archived files are preserved as-is
(historical content, not mass-edited per rule 9); the current-doc link scan
excludes `docs/archive/`.

### `docs/planning/` → `docs/archive/planning-2026-07-24/` (folder retired)

- `agent-prompts-2026-07-24.md` — 2026-07-24 agent task briefs; consumed (per
  `archive/DISPOSITION_LEDGER_2026-08-08.md`).
- `feature-reference-map.md` — long-range reference; backlog input.
- `image-studio-character-system-2026-07-24.md` — explicitly superseded by
  `docs/plans/image-studio-character-first-architecture-2026-07-28.md`.
- `kitty-next-evolution-working-notes.md` — 2026-07-07 working notes; historical.
- `kitty-vision-gap-analysis-2026-07-24.md` — gap analysis; backlog input.
- `kittybuilder-redesign-2026-07-24.md` — consumed into Builder outcomes.
- `vision-horizons.md` — self-described "canonical future-direction catalog";
  `archive/DISPOSITION_LEDGER_2026-08-08.md` marks it BACKLOG ("activates Phase
  4"). Moved per task as part of the frozen `docs/planning/` family; no current
  inbound link required a stub. Retrievable from archive when Phase 4 activates.

### `docs/recon/` → `docs/archive/recon-2026-07/`

- `repo-landscape-2026-07-24.md` — 2026-07-24 external landscape comparison;
  research input.
- `2026-07-17-agent-leverage/` (5 files: `github_metadata.txt` + 4 experiment
  prototypes) — 2026-07-17 recon experiment bundle; referenced only by the
  already-archived `RECON_KITTY_AGENT_LEVERAGE_2026-07-17.html`.

### `docs/` flat snapshots → `docs/archive/legacy-snapshots/`

- `CLOSEOUT_LEDGER_2026-08-05.md` — 2026-08-05 closeout deliverable ledger.
- `DECISION_REVIEW_2026-07-26.md` — 2026-07-26 ADR review pass; record only.
- `LOOSE_ENDS_2026-08-05.md` — 2026-08-05 loose-ends register; companion to the
  closeout ledger.
- `SESSION_META_2026-07-24.md` — 2026-07-24 session meta-analysis; absorbed.
- `scout-report.md` — 2026-04-06 open-source inspiration report; zero inbound refs.
- `worktree-cleanup-report.md` — 2026-09-01 worktree cleanup report; zero inbound refs.
- `memory-stale.md` — 2026-08-10 ephemeral mem0 maintenance report (a later
  snapshot than the 2026-06-22 copy already in `docs/archive/`).
- `skill-improvement-queue.md` — 2026-08-10 ephemeral skill audit output (a later
  snapshot than the 2026-06-22 copy already in `docs/archive/`).

### `docs/reference/` → `docs/archive/audits-2026-07/`

- `DOCUMENTATION_AUDIT.md` — 2026-07-30 doc-health classification audit; stale.
  Joined the existing 2026-07 audit-harvest folder.

## Inbound links repaired (current docs only)

| File | Change |
|---|---|
| `docs/PLANS.md` (operating rule) | `docs/planning/` noted as archived to `docs/archive/planning-2026-07-24/` |
| `docs/PLANS.md` (superseded Image Studio list) | `docs/planning/image-studio-character-system-2026-07-24.md` → archive path |
| `docs/plans/image-studio-character-first-architecture-2026-07-28.md` (sources) | same path update |
| `docs/reference/CODEBASE_MAP.md` (docs map table) | `docs/reference/DOCUMENTATION_AUDIT.md` → archive path |

Left as historical prose (not repaired, per rule 9 / protected stores): the
`docs/planning/` mention in `docs/README.md` (guarded by
`tests/test_documentation_authority.py`; treated as do-not-touch), the casual
`DOCUMENTATION_AUDIT.md` example in `docs/research/README.md`, and the
`CLOSEOUT_LEDGER` markdown link inside `docs/archive/DISPOSITION_LEDGER_2026-08-08.md`
(archive-internal; excluded from the current-doc link scan).

## Checked and explicitly NOT moved

- **`TASKS.md` (root) — REFUSED.** Self-marked "Superseded 2026-07-17" (already a
  tombstone, not misleading current-looking material). Tooling depends on it:
  `tests/test_run_gates_script.py::test_tasks_md_present` asserts
  `(ROOT / "TASKS.md").exists()`. Per the task's own condition ("if no tooling
  depends on it"), it stays at root.
- **Packet-number collisions in `docs/packets/` — NOT TOUCHED.** Prefixes `021`,
  `022`, `026` each have two packets (`021-memory-taste-and-creative-continuity`
  vs `021-project-registry-and-resume`; `022-chat-log-idea-mine` vs
  `022-magic-kitty`; `026-audit-implement-low-risk` vs `026-builder-reliability`).
  Recorded only; another active packet lane owns their resolution (rule 4).

## Runtime-code interaction (BLUEPRINT)

`docs/BLUEPRINT.md` is referenced by runtime code:
`gateway/builder_context.py::_context_files` hashes it (gracefully skipped if
absent), and `gateway/context_receipt_legacy.py::_BUILDER_DESCRIPTION_PATHS`
scans it. The task forbids modifying runtime code, so the stub keeps the path
valid: both code paths still find a file at `docs/BLUEPRINT.md` (now the short
pointer). The Builder context manifest now records the stub's hash rather than
the full blueprint — an expected, non-breaking consequence of archiving a
historical doc out of the active context surface. No test asserts BLUEPRINT's
content or hash (`tests/test_builder_context.py` uses temp fixtures).

## Exclusions honored (rule 3 — not moved)

`ROADMAP_V2.md` (explicit historical compatibility detail), live named packet
families, initiatives, audit/research/proof stores, session-notes, superpowers
plans/specs, and the MEMPALACE runbook were not moved.

## Verification

See the task report for: `git status`/moves/stubs, the current-doc markdown-link
scan (excluding vendor/history), `tests/test_documentation_authority.py` and
`tests/test_run_gates_script.py` results, and `git diff --check`. No commit was
made.
