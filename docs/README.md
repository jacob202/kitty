# Kitty Documentation

Existing does not mean current. This is a human map of the `docs/` directory:
what each file or folder is and which category it belongs to. It is not a
reading order and not a second authority table — [`AUTHORITY_MAP.md`](AUTHORITY_MAP.md)
routes each concern to its owner, and [`../START_HERE.md`](../START_HERE.md)
owns the canonical cold-start reading order. For a cold start, follow
[`../START_HERE.md`](../START_HERE.md).

## Current authorities

Canonical owners of current truth, grouped for navigation. Concern-to-owner
routing lives in [`AUTHORITY_MAP.md`](AUTHORITY_MAP.md); this list is a
directory map, not a competing authority table.

- [`AUTHORITY_MAP.md`](AUTHORITY_MAP.md) — concern router; names the owner of each kind of truth.
- [`CONSTITUTION.md`](CONSTITUTION.md) — highest design authority; all ADRs, roadmaps, and plans must be consistent with it.
- [`NORTH_STAR.md`](NORTH_STAR.md) — product purpose and the life-first outcome.
- [`../AGENTS.md`](../AGENTS.md) — shared engineering and agent operating doctrine (root contract).
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — current runnable system shape and component boundaries.
- [`DECISIONS.md`](DECISIONS.md) and [`adr/`](adr/) — accepted decisions, amendments, and supersession.
- [`decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md`](decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md) — cross-cutting architectural adjudication of accepted decisions.
- [`ROADMAP.md`](ROADMAP.md) — the one active forward-looking delivery order and exit criteria.
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — dated shipped-capability and limitation evidence at its stated SHAs.
- [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md) — the one approved mission record and acceptance contract.

## Current supporting and reference docs

Reusable technical guidance and supporting layering references. They extend an
authority; they do not replace the owners above.

- [`ALIGNMENT_MAP.md`](ALIGNMENT_MAP.md) — Kitty/KittyBuilder layering, boundaries, and non-goals reference (the `execution_frame` concern owner; not a roadmap, status, or authority-order source).
- [`reference/CODEBASE_MAP.md`](reference/CODEBASE_MAP.md) — code and data-flow map.
- [`reference/GATEWAY_API.md`](reference/GATEWAY_API.md) — Gateway HTTP schema discovery and client-integration boundary.
- [`reference/CONTEXT_ENGINEERING.md`](reference/CONTEXT_ENGINEERING.md) — staged context-loading playbook by task type.
- [`reference/LAUNCHER_CONTRACT.md`](reference/LAUNCHER_CONTRACT.md) — the single launcher interface across production and development.
- [`reference/PREVENTION_MECHANISMS.md`](reference/PREVENTION_MECHANISMS.md) — enforceable repository prevention mechanisms.
- [`FREE_MODEL_PACKET_STANDARD.md`](FREE_MODEL_PACKET_STANDARD.md) — packet-quality/classification standard for deterministic free-exec work.
- [`contracts/`](contracts/) — supporting design/runtime contracts; individual files state whether they are executable policy, proposed schema, or historical input.
- [`KITTYBUILDER_QUICKSTART.md`](KITTYBUILDER_QUICKSTART.md) — supported Builder operator commands and execution safety rails.
- [`reference/`](reference/) — reusable technical guidance generally.

## Execution inputs

Candidate work and scoped contracts. These are inputs, not authority, until
explicitly approved and owned through current ROADMAP/mission evidence.

- [`plans/README.md`](plans/README.md) — index for candidate implementation plans; plans are inert until activated by current authority/ownership.
- `packets/` — scoped execution contracts and historical packet material.
- `initiatives/` — approved and retired initiative records.
- `research/` — dated research and decision inputs (indexed in [`research/README.md`](research/README.md)); ADR inputs, not authority.
- `campaigns/` — campaign records; live execution still requires current ownership/Builder evidence.
- [`superpowers/README.md`](superpowers/README.md) — live Builder plan/spec output convention; not a second roadmap.

## Historical and derived catalogs

Dated evidence and derived syntheses. They are not current authority; the
current sequence lives in [`ROADMAP.md`](ROADMAP.md).

- [`DISPOSITION_LEDGER.md`](DISPOSITION_LEDGER.md) — compatibility pointer to the archived 2026-08-08 planning snapshot; not current activation authority.
- [`KNOWLEDGE_GRAPH.md`](KNOWLEDGE_GRAPH.md) — compatibility pointer to the archived 2026-08-05 relationship analysis.
- [`KITTY_MASTER_PROGRAM.md`](KITTY_MASTER_PROGRAM.md) — derived historical synthesis; current sequence lives in `ROADMAP.md`.
- [`audit/`](audit/) — dated findings and evidence, including [`audit/GITHUB_OPERATING_PICTURE_2026-08-04.md`](audit/GITHUB_OPERATING_PICTURE_2026-08-04.md). Sequential-audit companion (dated 2026-08-23): [`audit/post_audit_support_2026-08-23/README.md`](audit/post_audit_support_2026-08-23/README.md).
- `phases/` — legacy organization; treat as historical unless current authority links to it.
- `archive/planning-2026-07-24/` — the retired former `docs/planning/` tree, preserved for history only.

## History

`archive/` preserves superseded plans, handoffs, status snapshots, and operating
material. Archived content may explain why a decision was made, but it is never
current instruction. The pre-reconciliation roadmap is preserved by Git history
and indexed at [`archive/ROADMAP_PRE_RECONCILIATION_2026-08-04.md`](archive/ROADMAP_PRE_RECONCILIATION_2026-08-04.md).

## Maintenance rule

When current truth changes:

1. update the canonical owner;
2. preserve superseded reasoning in `archive/`, an ADR, or a dated audit;
3. repair inbound links;
4. remove the obsolete document from current navigation;
5. never convert historical prose into live execution state.
