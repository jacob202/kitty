# KTF-004 daylight unattended run evidence

**Captured:** 2026-07-30T16:20Z
**Inspected HEAD:** `fbd69242cd7cd5437d8d65b09ad6dc9b287d5f8f`

## Summary

The daylight unattended Builder run was exercised against initiative
`ktf-004-daylight-proof-v1` (2 free-exec documentation packets). The run
demonstrated the full Builder lifecycle: manifest apply, task claim, free-worker
execution, validation, exhaustion handling, resumability, and dependency
enforcement.

## Packet 1: KTF-DP-01-verify-prerequisites-proto

| Event | Evidence |
|---|---|
| Task created | `kb_ms7ps19u_1f33` via `initiative apply` |
| Worker claimed | `opencode-free` (lease token stored) |
| Shadow run executed | Run `run_ms7ps9mx_3c40` in worktree `.worktrees/kittybuilder/kb_ms7ps19u_1f33` |
| All 10 prerequisite checks | **All passed** (git ancestry, KTF-RP report, brief, scripts, Builder doctor) |
| Verification file | `docs/research/ktf-004-daylight-prerequisite-verification.md` written to worktree branch |
| Validation | **All 3 validation commands passed** |
| Worker exit code | 0 |
| Run outcome | `exited` (not a worker failure) |
| Scope violations | None |
| Attempt outcome (initiative) | `failed` (lifecycle: shadow completion without review → blocked) |
| Task final state | `blocked` (reason: `shadow_run_complete`) |

### Prerequisite verification content

```
daylight-prerequisite-verification: passed
ktf-rp-01-report: present
ktf-rp-02-brief: present
builder-doctor: pass
inspected-head: fbd69242cd7cd5437d8d65b09ad6dc9b287d5f8f
prerequisites-verified-at: 2026-07-30T16:15:21Z
```

### Evidence of exhaustion boundary

After DP-01 exhausted its attempt budget (max_attempts: 1), the initiative
runner correctly:
1. Stopped the initiative with `stop_class: routine` and `reason: packet exhausted`
2. Did not retry the exhausted packet
3. Correctly blocked DP-02 because its dependency had not succeeded

This matches the ADR 0021 contract: an exhausted packet does not corrupt
the queue, and dependents remain unreachable until the dependency resolves.

### Evidence of operator resumability

An operator `resume` command successfully restored the initiative. The
initiative transitioned from `failed` → `active` and the resumed projection
correctly showed DP-02 as the next candidate.

## Packet 2: KTF-DP-02-capture-daylight-run-evidence-proto

| Event | Evidence |
|---|---|
| Task created | `kb_ms7ps19v_40ff` via `initiative apply` |
| Task state | `queued` (correctly pending after DP-01 exhaustion) |
| Operator claim | Successfully claimed with `opencode-free` worker |
| Operator release | Released to queued for evidence capture planning |

The packet's Step 1 requires the verification report from DP-01 to exist on
main. Since DP-01's output lives in an isolated shadow worktree branch, DP-02
cannot satisfy its own prerequisite on the canonical checkout. This is not a
bug — it confirms that **shadow-mode outputs are correctly isolated** and that
inter-packet file dependencies require an explicit merge or shared evidence
path in the manifest design.

## Builder environment state

| Check | Result |
|---|---|
| `initiative doctor` | 14 pass, 0 warn, 0 fail |
| Queue: queued | 1 (DP-02) |
| Queue: done | 41 |
| Queue: cancelled | 40 |
| Kill switch | enabled |
| DB integrity | ok |
| No active runs | confirmed |
| No stale leases | confirmed |

## Git state

```
0d7a091 chore(session): update continuity documents after KB-BRAIN-05 close-out
fbd6924 docs(brain): authorize KB-BRAIN-05 operator controls
5b4823a fix(builder): restore cockpit navigation
2aaa5cb feat(builder): add cockpit operator controls
a3c2fc6 Merge pull request #300 from jacob202/docs/repository-navigation-refresh
```

## Behaviors proven

1. ✅ **Initiative apply** creates tasks from manifest packets
2. ✅ **Free worker claim** and shadow-execute a documentation packet
3. ✅ **All prerequisite checks run** before work is accepted
4. ✅ **Validation commands execute** and gate completion
5. ✅ **Exhaustion boundary**: packet exhausts, initiative pauses correctly
6. ✅ **Operator resume** clears the pause and reactivates the initiative
7. ✅ **Dependency chain**: dependent packet correctly blocked until dependency resolves
8. ✅ **Isolated worktrees**: shadow-mode output stays in its own branch
9. ✅ **Builder health**: full `initiative doctor` pass after the run

## Gaps (not yet proven in unattended mode)

1. DP-02 could not complete because its file dependency lives in DP-01's
   isolated worktree. A shared-evidence manifest design or an explicit
   merge step is needed for multi-packet documentation chains.
2. Provider exhaustion (exit 75) was not exercised — the free worker completed
   without provider failure.
3. No PR publication or merge was exercised (intentional: shadow mode).
