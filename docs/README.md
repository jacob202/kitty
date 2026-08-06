# Kitty Documentation

Existing does not mean current. Use this index instead of inferring authority from filenames, detail, or recency.

## Current authority

| Concern | Document |
|---|---|
| Truth ownership | [`AUTHORITY_MAP.md`](AUTHORITY_MAP.md) |
| Product purpose | [`NORTH_STAR.md`](NORTH_STAR.md) |
| Architecture and boundaries | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Durable decisions | [`DECISIONS.md`](DECISIONS.md) and [`adr/`](adr/) |
| Active delivery order | [`ROADMAP.md`](ROADMAP.md) |
| Verified repository state | [`PROJECT_STATUS.md`](PROJECT_STATUS.md) |
| One approved mission | [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md) |
| Code/data-flow map | [`reference/CODEBASE_MAP.md`](reference/CODEBASE_MAP.md) |
| Current GitHub truth pass | [`audit/GITHUB_OPERATING_PICTURE_2026-08-04.md`](audit/GITHUB_OPERATING_PICTURE_2026-08-04.md) |

## Supporting material

- `plans/` — candidate work and implementation inputs; not authority until absorbed.
- `research/` — dated research and decision inputs (indexed in [`research/README.md`](research/README.md)); ADR inputs, not authority.
- `packets/` — scoped execution contracts and historical packet material.
- `audit/` — dated findings and evidence.
- `reference/` — reusable technical guidance.
- `phases/` and `planning/` — legacy organization; treat as historical unless current authority links to it.

## History

`archive/` preserves superseded plans, handoffs, status snapshots, and operating material. Archived content may explain why a decision was made, but it is never current instruction.

The pre-reconciliation roadmap is preserved by Git history and indexed at [`archive/ROADMAP_PRE_RECONCILIATION_2026-08-04.md`](archive/ROADMAP_PRE_RECONCILIATION_2026-08-04.md).

## Maintenance rule

When current truth changes:

1. update the canonical owner;
2. preserve superseded reasoning in `archive/`, an ADR, or a dated audit;
3. repair inbound links;
4. remove the obsolete document from current navigation;
5. never convert historical prose into live execution state.

For a cold start, follow [`../START_HERE.md`](../START_HERE.md).
