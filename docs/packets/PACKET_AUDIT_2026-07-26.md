# Packet Audit — 2026-07-26

Re-examination of the prose packet inventory against `docs/ALIGNMENT_MAP.md`,
ADR 0020, ADR 0021, and `docs/FREE_MODEL_PACKET_STANDARD.md`.

**Nothing is deleted.** Ideas are reclassified, not discarded. Prose packets
are planning inputs; Builder executes approved packets inside JSON initiative
manifests.

## 1. Numbering and identity defects

Five collisions or duplicate-draft pairs must be resolved before packet numbers
can be trusted as references:

| Number | Files | Nature |
|---|---|---|
| 021 | `021-memory-taste-and-creative-continuity`, `021-project-registry-and-resume` | different packets, same number |
| 022 | `022-chat-log-idea-mine`, `022-magic-kitty` | different packets, same number |
| 026 | `026-audit-implement-low-risk`, `026-builder-reliability` | different packets, same number |
| 021 / 023 | `memory-taste-and-creative-continuity` | two non-identical drafts of one idea |
| 022 / 024 | `chat-log-idea-mine` | two non-identical drafts of one idea |

Resolution requires a strong planning pass: choose the surviving draft, archive
the other, and assign unique stable IDs. A free worker must not guess which
contract a number means.

## 2. Verified shipped or substantially implemented work

These prose packets are not candidates for blind re-execution. Their remaining
work, if any, must be calculated from current code and evidence.

| Packet | Disposition |
|---|---|
| `001-state-spine` | shipped |
| `002-inbox-triage` | shipped |
| `003-action-queue` | shipped |
| `004-state-home` | implemented in PR #96; current product fit requires a fresh delta review, not replaying the original packet |
| `006-project-resume` | shipped as the repository/session resume tool; distinct from life-project resume |
| `007-delegation-packet-generator` | implementation surfaces exist, but its contract renders Markdown drafts rather than executable manifests; historical implementation, not the planning engine |
| `015-phone-channel` | recorded as shipped in later packet evidence; verify current transport before relying on it |
| `021-project-registry-and-resume` | shipped in PR #106; current project store/resume modules exist |
| `016-next-step-navigator` | implementation surfaces (`gateway/next_step.py` and migration 011) exist; completion and product quality require a current acceptance review |

Packet status prose is lower-authority than current Git and supported runtime
evidence. The canonical roadmap therefore calls for delta reviews, not packet
replays.

## 3. Current Phase 1 work

| Work | Class | Required treatment |
|---|---|---|
| Restore Python dependency installation | `paid-exec` | separate reviewed dependency PR; no automatic merge |
| Regenerate frontend lockfile | `paid-exec` | separate reviewed lockfile PR; no automatic merge |
| PR #261 review/checker | current PR work | finish scoped review and merge after functioning gates |
| PR #262 manifest gate repairs | current PR work | finish and merge after functioning gates |
| Packet 014 remainder | `paid-author` → possible `free-exec` | derive the exact remaining delta after #261/#262 and CI repair; do not execute the original historical packet wholesale |
| Packet 026 Builder reliability | `paid-exec` | calculate only the unproven recovery/closeout delta and prove it with deterministic fixtures |
| Packet 026 low-risk audit | historical bundle | close rows already shipped; split any truly unfinished row into one-outcome packets |
| Planning authority repair | strong-model planning | completed in this PR through ADRs 0020/0021, `docs/ROADMAP.md`, and the new active Mission |
| `kx-01` / `kx-02` | strong-model planning | combine into one initiative with internal phases; do not add cross-initiative dependency machinery |

## 4. Free-model readiness

**Zero existing prose packets are automatically `free-exec`.**

A packet qualifies only after its executable JSON contract has been fully read,
re-authored at patch level, and checked against the standard. In particular:

- exact files, functions, anchors, and replacements are named;
- every decision is already resolved;
- the gate runs on the execution machine;
- the gate fails on the unmodified tree;
- partial work stops honestly and remains inspectable;
- no dependency, lockfile, CI, auth, secret, destructive, or human-judgment work
  is included.

The nightly drain currently has nothing proven safe to drain.

## 5. Correct conversion order

The earlier version of this audit incorrectly put Packet 007 first because it
"generates packets." Its actual output is another Markdown draft with unfilled
markers, not a validated executable manifest. It does not reduce strong-model
planning work enough to deserve first priority.

The corrected order is:

1. **Repair CI.** No packet acceptance is trustworthy while installation gates
   are dead.
2. **Derive the exact Packet 014 delta.** Convert only remaining mechanical gate
   work into one-outcome JSON packets.
3. **Split any unfinished low-risk audit row.** Use rows with literal edits and
   deterministic tests as the first `free-exec` candidates.
4. **Author a second tiny Phase 1 packet** from a proven Builder reliability or
   authority-cleanup delta.
5. Verify both gates fail on the unmodified tree and run on Jacob's Mac.
6. Run them manually through the unattended path in daylight.
7. Redesign Packet 007 later as a manifest compiler/authoring assistant only
   after the executable contract and planning hierarchy are stable.

The scarce resource is correct authoring. The metric is verified
`paid-author → free-exec` conversions, not prose packets produced.

## 6. Nightly autonomy

### Existing infrastructure to extend

- `scripts/nightly_packet_drain.sh` already uses the free ladder, an atomic
  lock, a runtime wall, logs, and `LAST_DRAIN.md`.
- `docs/FREE_WORKERS.md` records the adapter's clean-failure and partial-work
  rules.
- Builder already owns durable execution state; `launchd` will only trigger the
  existing execution surface.

Do not create another scheduler, queue, state store, or orchestrator.

### Gaps against ADR 0021

The current drain:

- selects only one active initiative;
- uses a fixed 90-minute campaign wall;
- stops at a manual gate;
- does not proactively continue across unrelated initiatives;
- does not implement the approved draft-PR/ready/low-risk-merge lifecycle;
- does not explicitly represent provider exhaustion as a resumable pause.

Those are extension requirements after the evidence prerequisites below are
met.

### Preconditions to scheduling

1. Python and frontend installation/CI are green from a clean checkout.
2. PRs #261 and #262 are resolved.
3. At least two real JSON packets are verified `free-exec`.
4. Each gate is runnable and falsifiable.
5. One daylight unattended run is read end to end and reconciled against Git,
   GitHub, and Builder evidence.
6. Low-risk merge classification and exclusions from ADRs 0018/0021 are
   enforced.

Only then install the macOS `launchd` schedule. Provider exhaustion must leave
state safe to resume on the next invocation.

## 7. Backlog disposition

All remaining feature packets stay visible as roadmap/backlog input, including
home, project continuity, benefits, experts, image generation, reasoning,
Magic Kitty, memory/taste, and chat-log mining.

They do not become current work until `docs/ROADMAP.md` promotes them. Human and
life-first items remain Jacob's decisions and continue to outrank Kitty code
when activated under ADR 0016.
