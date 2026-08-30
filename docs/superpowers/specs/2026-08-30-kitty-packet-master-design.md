# Kitty Packet Master — Resumable Registry and Campaign Design

**Date:** 2026-08-30  
**Status:** approved design; design-only slice  
**Owner:** ChatGPT Packet Master  
**Lane:** packet registry, roadmap, and specification only

## Decision

Use a registry-first Packet Master. `docs/ACTIVE_MISSION.md` owns the
objective and ordered outcomes; `docs/ROADMAP.md` owns priority and sequence;
validated JSON initiative manifests are the only Builder-executable contracts.
Generated registry and immutable sidecar checkpoints carry disposition,
ownership, provenance, evidence, and resume data. They must not be added to
the executable manifest.

This design does not activate a mission, apply a manifest, mutate Builder, or
replace the roadmap. It preserves history and makes credit-stop recovery
deterministic.

## Authority boundaries

| Concern | Authority | Treatment |
|---|---|---|
| Purpose | `docs/NORTH_STAR.md` | reference |
| Architecture/decisions | `docs/CONSTITUTION.md`, `docs/DECISIONS.md`, `docs/adr/` | reject conflicts |
| Sequence | `docs/ROADMAP.md` | source of order |
| Mission | `docs/ACTIVE_MISSION.md` | source of objective/acceptance |
| Executable contract | `gateway/builder_initiative.py` | exact validator |
| Free execution | `docs/FREE_MODEL_PACKET_STANDARD.md` | deterministic gates |
| Disposition | `docs/DISPOSITION_LEDGER.md` until generated registry exists | reconcile only |
| Live execution | supported Builder CLI/API projection | read-only |
| Session continuation | `.claude/STATE.md`, `.claude/HANDOFF.md` when valid | evidence input |

Gateway is product truth and KittyBuilder is execution control plane. Native
Kitty UI is canonical. This lane changes neither.

## Fresh evidence snapshot

- Fresh `git ls-remote origin refs/heads/main`: `a1c0f09a7e86ff8a368b5a96e87c081ed0dae204`.
- Isolated worktree: `/Users/jacobbrizinnski/orca/workspaces/kitty/kitty-packet-master-20260830`.
- Branch: `jacob202/kitty-packet-master-20260830`; HEAD exactly equals fresh main.
- Canonical checkout is dirty and was not modified.
- PR #704 is open at `5eb17380f20b8add2b4166299c2d73e5cb3d97b0`; lane is Builder agent-operability.
- PR #677 is open at `da3ace79ef7e274b41ca5fc012463d09587a74ea`; lane is actionable Work/Builder scheduling.
- Preserved worktrees and open PRs are not automatically live agents. Only a
  currently verified owner/lease counts as active; stale lock metadata is not
  ownership.
- `kb_mtgatvyi_340e` remains live/UNKNOWN until its terminal state is
  reverified; this docs-only lane does not overlap it, #704, or #677.
- Inventory: 29 packet Markdown files (25 numbered), 40 initiative JSON files,
  152 manifest packet entries, and 126 unique manifest packet IDs.
- Current mission sequence: `REC-001 → WORK-001 → BUILDER-001 → IMAGE-001 → LIBRARY-001 → AUTO-001 → HOME-001 → ACCEPT-001`.

The snapshot is time-bound. Live Builder queue, runtime health, and current
review state are UNKNOWN until the resume protocol refreshes them.

## Legacy duplicate problem

The repository has numbered Markdown packets, 40 JSON manifests, campaign plans,
superpowers plans/specs, research, audits, and a hand-maintained ledger. The
packet README was updated 2026-07-14; the ledger is dated 2026-08-08; both
predate this mission. Known defects include:

- packet files 021/022 were renumbered to 023/024 but ghosts remain;
- KTF-004 has four superseded manifests for one daylight-proof concern;
- recovery-control-plane V1–V6 reuse three packet IDs;
- aggregate and split KX manifests reuse eleven packet IDs;
- a tracked manifest does not prove application to Builder.

The README is provenance/intake guidance, not current queue truth. The generated
registry must label missing live evidence UNKNOWN rather than infer from prose.

## Canonical artifact set

1. `docs/ACTIVE_MISSION.md`: mission and outcome order.
2. `docs/ROADMAP.md`: sole active sequence.
3. `docs/initiatives/<initiative-id>.json`: immutable Builder input.
4. `docs/packets/<source>.md`: human-readable source/provenance only.
5. `docs/packet-registry.json`: deterministic generated index and collision guard.
6. `docs/packet-dispositions.json`: explicit disposition/supersession sidecar.
7. `docs/packet-checkpoints/<initiative-id>/<packet-id>.json`: immutable resume/evidence receipts.
8. `docs/packet-roadmap.md`: resumable campaign map, never executable.

No history is rewritten; superseded files remain provenance until explicitly
authorized archival.

## Strict runtime-compatible manifest schema

The validator permits exactly these top-level keys:

```json
{"manifest_version":1,"initiative_id":"stable-id","title":"...","description":"...","packets":[]}
```

Each packet permits exactly `id`, `title`, `objective`, `depends_on`,
`acceptance_criteria`, `allowed_paths`, `policy`, and
`validation_commands`. Policy permits `max_attempts`, `priority`, and
`routing`; routing permits only `model` and `provider`. IDs are bounded,
dependencies must exist and be acyclic, and validation commands are limited.

Sidecar-only fields include `class`, `owner`, `activation`, `source_refs`,
`base_sha`, `demo_contract`, `scope_budget`, `privacy`,
`stop_conditions`, `evidence_requirements`, `status`, `supersedes`,
`superseded_by`, `ratification`, `plan_only`, `reason`,
`replaced_commit`, and `constraints`. Putting these in manifest JSON fails
validation; `ktf-005-life-resume-loop-gate-v1.json` intentionally demonstrates
this rejected plan-only shape.

## Registry and collision guard

Add a read-only `scripts/generate_packet_registry.py`. It should enumerate
`docs/initiatives/*.json), run
`./kitty builder initiative validate --json`, extract valid IDs/dependencies/
paths/commands, join the disposition sidecar, and emit deterministic sorted JSON
with source SHA and generation time. It must report duplicate initiative/packet
IDs, invalid or intentionally rejected records, missing/cyclic dependencies,
stale sources with no replacement, and manifests absent from the sidecar.

Before mutation, explicitly check `kb_mtgatvyi_340`, PR #704, and PR #677.
Collision means REVIEW or DEPENDENCY, never a competing implementation. A
manifest on disk is not evidence that it is queued. Add a CI/preflight check
for invalid manifests, duplicate active IDs, and missing dispositions.

## KFP packet-wave catalog

KFP IDs are Packet Master planning waves, not Builder packet IDs. They are
stable sidecar identifiers; `planned` is not executable and `active` requires
mission/roadmap authorization.

| ID | Title | Status | Depends |
|---|---|---|---|
| KFP-01 | Freeze authority map and mission receipt | active | — |
| KFP-02 | Capture fresh GitHub main SHA | complete | KFP-01 |
| KFP-03 | Inventory packet Markdown | complete | KFP-01 |
| KFP-04 | Inventory initiative manifests | complete | KFP-01 |
| KFP-05 | Detect duplicate packet IDs | complete | KFP-04 |
| KFP-06 | Reconcile 021/022 packet ghosts | planned | KFP-03,KFP-05 |
| KFP-07 | Reconcile initiative revisions | planned | KFP-04,KFP-05 |
| KFP-08 | Define disposition sidecar | planned | KFP-06,KFP-07 |
| KFP-09 | Implement deterministic registry | planned | KFP-08 |
| KFP-10 | Add validator wrapper | planned | KFP-09 |
| KFP-11 | Add duplicate-ID CI guard | planned | KFP-09 |
| KFP-12 | Add missing-disposition guard | planned | KFP-09 |
| KFP-13 | Add dependency-cycle report | planned | KFP-09 |
| KFP-14 | Add source-to-manifest crosswalk | planned | KFP-09 |
| KFP-15 | Record PR #704 boundary | active | KFP-02 |
| KFP-16 | Record PR #677 boundary | active | KFP-02 |
| KFP-17 | Record Builder task boundary | active | KFP-02 |
| KFP-18 | Reconcile issue #490 | planned | KFP-15,KFP-16,KFP-17 |
| KFP-19 | Define immutable packet identity | planned | KFP-07 |
| KFP-20 | Define supersession graph | planned | KFP-19 |
| KFP-21 | Define provenance retention | planned | KFP-20 |
| KFP-22 | Define checkpoint schema | planned | KFP-19 |
| KFP-23 | Define evidence schema | planned | KFP-22 |
| KFP-24 | Define credit-stop resume | planned | KFP-22,KFP-23 |
| KFP-25 | Draft resumable campaign roadmap | planned | KFP-08,KFP-24 |
| KFP-26 | Map REC-001 baseline | planned | KFP-25 |
| KFP-27 | Map WORK-001 repair | planned | KFP-26 |
| KFP-28 | Map BUILDER-001 loop | planned | KFP-27 |
| KFP-29 | Map IMAGE-001 truth | planned | KFP-28 |
| KFP-30 | Map LIBRARY-001 artifacts | planned | KFP-29 |
| KFP-31 | Map AUTO-001 automation | planned | KFP-30 |
| KFP-32 | Map HOME-001 home | planned | KFP-31 |
| KFP-33 | Map ACCEPT-001 acceptance | planned | KFP-32 |
| KFP-34 | Author BUILDER-001 manifest | planned | KFP-28 |
| KFP-35 | Validate BUILDER-001 manifest | planned | KFP-34 |
| KFP-36 | Obtain explicit Builder approval | planned | KFP-35 |
| KFP-37 | Prove bounded Builder loop | planned | KFP-36 |
| KFP-38 | Prove interruption/recovery | planned | KFP-37 |
| KFP-39 | Author IMAGE-001 packets | planned | KFP-29,KFP-38 |
| KFP-40 | Author LIBRARY-001 packets | planned | KFP-30,KFP-39 |
| KFP-41 | Author AUTO-001 packets | planned | KFP-31,KFP-40 |
| KFP-42 | Author HOME-001 packets | planned | KFP-32,KFP-41 |
| KFP-43 | Independent desktop acceptance | planned | KFP-33,KFP-42 |
| KFP-44 | Independent iPhone acceptance | planned | KFP-43 |
| KFP-45 | Reconcile acceptance evidence | planned | KFP-44 |
| KFP-46 | Publish campaign checkpoint | planned | KFP-45 |
| KFP-47 | Retire superseded registry sources | planned | KFP-46 |
| KFP-48 | Declare mission outcome | planned | KFP-47 |

## Commit, checkpoint, and routing protocol

Each commit has one purpose, owner, and non-main branch. Before mutation refresh
main SHA, issue #490, PR/Builder collision state, and exact base. After mutation
run `git diff --check`, validate affected manifests, record changed paths and
exact results, and write a checkpoint containing manifest/source SHA, base SHA,
owner, status, Builder IDs when known, evidence, unknowns, one next action, and
blockers.

Use Luna for inventory, validation, registry generation, crosswalks, formatting,
and narrow docs. Escalate only for unresolved architecture/product choices,
adversarial review, live UX acceptance, or human-judgment packets. Paid work
stays within the mission budget. Credentials, spending, external delivery,
physical checks, and product decisions are human-only.

## Credit-stop resume protocol

Preserve branch, manifest, checkpoint, and partial worktree. Record blocked or
unknown with exact failure; never mark success. Do not recreate IDs or duplicate
lanes. On resume refresh GitHub main, #490, PR #704/#677, Builder projection, and
checkpoint identity; continue from `next_action`, rerun exact-head validation,
then advance the wave.

## Non-goals and risks

No Builder code, queue/lease/attempt mutation, runtime/DB writes, second
scheduler/roadmap/state machine, automatic apply, history rewrite, deletion,
merge, push, credentials, or paid provider call. Risks are stale ledgers,
duplicate IDs, aggregate/split overlap, sidecar fields copied into manifests,
and planning status mistaken for live Builder status. Fail closed and expose
UNKNOWN.

## Exact next commits

1. `docs: add packet registry generator and validator` — deterministic
   generator and focused duplicate/dependency/disposition tests.
2. `docs: reconcile packet dispositions and supersession map` — sidecar for
   packet ghosts, 026 audit, KTF-004, recovery V1–V6, and KX duplicates.
3. `docs: add resumable packet-master campaign roadmap` — mission sequence
   and KFP catalog; no Builder activation.

This design document is intentionally the only artifact in the initial commit.

