---
type: procedure
title: "Builder Campaign Controller"
status: active
owner: jacob
primary_purpose: Runtime operating manual for the campaign orchestrator — stop conditions, retry limits, evidence requirements, self-measuring state, canonical source resolution
derives_from:
  - docs/roadmap/BUILDER_IMPLEMENTATION_CAMPAIGN.md
  - docs/builder/BUILDER_OPERATING_MODEL.md
  - docs/builder/BUILDER_PACKET_LIFECYCLE.md
review_cycle: as needed
---

# Builder Campaign Controller

Runtime operating manual. This is read by the orchestrator at campaign start and every packet transition. It governs execution, not planning.

## Section 1: Campaign State

The campaign maintains a machine-readable state file at:

```
docs/roadmap/campaign_state.json
```

Schema:

```json
{
  "campaign": "alpha",
  "phase": 1,
  "completed_packets": 0,
  "remaining_packets": 31,
  "blocked": [],
  "failed": [],
  "review_pending": 0,
  "in_progress": [],
  "verification": "green",
  "last_updated": "ISO-8601",
  "next_dispatchable": [],
  "concurrent_workers": 3,
  "stalled_workers": []
}
```

The orchestrator writes to this file after every state transition. Workers read it to understand what's dispatchable. No state is inferred — it is explicit.

### State Transitions

| Transition | Trigger | Action |
|---|---|---|
| Packet dispatched | Worker claims packet | Move from `next_dispatchable` to `in_progress` |
| Packet completed | Review passes, merge succeeds | Move from `in_progress` to `completed_packets`; recalculate `next_dispatchable` |
| Packet failed | Max retries reached | Move from `in_progress` to `failed` |
| Packet blocked | Architecture review gate, spec contradiction, owner escalation | Move from `in_progress` to `blocked` |
| Packet under review | PR opened, reviewer assigned | Move from `in_progress` to `review_pending` |
| Worker stalled | No output for 30 min | Move from `in_progress` (if any) to `blocked`; add worker to `stalled_workers` |
| Verification failing | CI red on main | Set `verification` to `red`; block all new dispatches |

## Section 2: Automatic Stop Conditions

The campaign stops automatically when:

1. **All 31 packets completed.** State shows `remaining_packets: 0`.
2. **All remaining packets are blocked.** No `next_dispatchable`, all uncompleted in `blocked` state.
3. **Three consecutive merges reverted.** Something is systematically wrong.
4. **Verification is red on main.** No new dispatch until green.
5. **Owner escalation has no response.** Wait, do not work around.

## Section 3: Automatic Continue Conditions

The campaign continues automatically when:

1. **Verification is green AND next_dispatchable is non-empty.** Dispatch the next packet.
2. **A blocked packet becomes unblocked.** Recalculate `next_dispatchable`, dispatch if green.
3. **A review completes successfully.** Merge, update state, dispatch next.
4. **A stalled worker is rotated out.** Reassign its packet to a fresh worker.

## Section 4: Packet Failure Definition

A packet has failed when:

1. **Three implementation attempts** with different approaches all fail verification.
2. **Review rejects three times** on the same architectural concern.
3. **Worker cannot determine the requirement** after reading the canonical specification.
4. **Implementation is impossible** within the packet's scope (requires breaking a frozen invariant).

A packet has NOT failed when:
- One or two attempts fail (retry).
- Review rejects for fixable reasons (repair).
- CI is red due to infrastructure (retry, not failure).
- Worker stalls (rotate, don't fail the packet).

## Section 5: Retry Policy

| Scenario | Action | Max Retries |
|---|---|---|
| Test failure | Return to worker with failure output | 3 per worker, 3 workers max |
| Build failure | Return to worker | Same packet, no limit on repair |
| Review rejection (fixable) | Repair and re-submit | 3 per packet |
| Review rejection (architectural) | Block packet, escalate | 1 — do not retry |
| CI infrastructure failure | Wait 5 min, retry | 3 |
| Merge conflict | Resolve conflict, re-verify | No limit |
| Worker crash mid-packet | Reconcile stale attempts, reassign | No limit on reassignment |

## Section 6: Blocked Packet Rules

A packet becomes blocked when:

1. **Architecture review gate** — packet marked "Architecture review: Required" and owner unavailable.
2. **Spec contradiction** — canonical spec says X, implementation reality says Y, owner must resolve.
3. **Owner escalation triggered** — per escalation rules below.
4. **Dependency stalled** — packet depends on a blocked packet.

Blocked packets do NOT consume worker capacity. Skip them. Dispatch the next eligible packet.

## Section 7: Worker Continuation

A different worker may continue a packet when:
1. The original worker crashed (stale attempt reconciled).
2. The original worker is retired after 3 failed packets.
3. The original worker stalled for >30 minutes without output.

A worker MAY NOT continue a packet when:
1. The original worker is actively working on it (lease conflict).
2. The packet is blocked awaiting architectural decision.
3. The packet is under review.

## Section 8: Merge Evidence Requirements

Before merging a PR, the orchestrator must confirm:

| Requirement | Evidence |
|---|---|
| Tests pass | `python3.12 -m pytest tests/test_builder_*.py -q -x` exit code 0 |
| Lint passes | `python3 -m ruff check gateway/ tests/` exit code 0 |
| Typecheck passes | `python3 -m mypy gateway/ --ignore-missing-imports` exit code 0 |
| Docs lint passes | `python3 scripts/docs_lint.py` exit code 0 (if governed docs touched) |
| SYSTEM_MAP current | `python3 scripts/docs_system_map.py --check` exit code 0 (if governed docs touched) |
| Frontend builds | `cd gateway/kitty-chat && npm run build` exit code 0 (if UI touched) |
| Reviewer approved | Review verdict is `approve` |
| No spec violation | Reviewer confirmed conformance to architecture, KM, operating model |
| No duplicate behavior | Reviewer confirmed no second source of truth created |
| Owner approval | Not required unless packet is marked "Architecture review: Required" |
| Campaign state updated | State file reflects merge |

Missing any of these: do not merge.

## Section 9: Human Approval Mandatory

Human approval is mandatory when:

1. Packet is marked "Architecture review: Required."
2. Packet modifies a frozen document (governance, KM, ADRs, specs).
3. Three consecutive merges reverted — owner must diagnose.
4. Any blocked packet with architecture review gate.
5. Campaign state shows `verification: "red"` — owner must green-light restart.

Human approval is NOT required for:
- Test/bugfix packets within implementation code.
- Review-passed packets within allowed paths.
- Standard merge within campaign flow.

## Section 10: Escalation Thresholds

| Trigger | Action |
|---|---|
| 3 workers fail same packet | Escalate to owner. Requirement may be ambiguous. |
| Same packet fails 3 times after review rejection | Block packet. Escalate to owner. |
| 3 consecutive merges reverted | Stop campaign. Escalate to owner. |
| Spec contradiction discovered | Stop packet. Document in campaign contradictions. Escalate to owner. |
| Stalled workers exceed 2 | Reduce concurrent workers by 1. Continue. Escalate if persists. |
| Verification stays red for >1 hour | Stop dispatches. Escalate to owner. |

## Section 11: Campaign Health Metrics

Reported every 5 completed packets:

```json
{
  "packets_completed": 5,
  "packets_in_progress": 2,
  "review_pending": 1,
  "blocked": 0,
  "failed": 0,
  "avg_attempts_per_packet": 1.4,
  "review_pass_rate": "80%",
  "merge_revert_count": 0,
  "escalation_count": 0,
  "hours_running": 3,
  "verification": "green"
}
```

Metrics are derived from the campaign state file. No manual collection.

## Section 12: Canonical Source Resolution (Worker Invariant)

Before implementing ANY packet, the worker MUST resolve:

| Question | Source |
|---|---|
| What does the architecture say? | `docs/architecture/REFERENCE_ARCHITECTURE.md` |
| What does the Knowledge Model say? | `docs/knowledge/KNOWLEDGE_MODEL.md` |
| What does the Builder spec say? | `docs/builder/BUILDER_SPECIFICATION_INDEX.md` → correct spec |
| What does the ADR say? | `docs/adr/` referenced by packet or relevant area |
| What does the campaign say? | `docs/roadmap/BUILDER_IMPLEMENTATION_CAMPAIGN.md` — exact packet |
| What does the runtime look like? | `gateway/builder_*.py` — current implementation |

If ANY of these documents disagree with each other:

1. **STOP.**
2. **Record the contradiction** in the campaign state.
3. **Do NOT choose** one interpretation over another.
4. **Escalate to owner.**

Never implement from a document that is not the canonical source. Never assume which of two conflicting documents is correct.

## Section 13: Reviewer Invariant

Before approving ANY PR, the reviewer MUST verify:

1. **Conforms to Architecture:** Does the implementation respect subsystem boundaries, ownership, and dependency rules?
2. **Conforms to Knowledge Model:** Does it use the correct vocabulary? Does it avoid redefining "Knowledge," "Evidence," "Receipt," etc.?
3. **Conforms to Builder Operating Model:** Does it stay within Builder's decision boundary? Does it escalate when required?
4. **Conforms to Packet Contract:** Does it satisfy the explicit objective, acceptance criteria, and allowed paths?
5. **Conforms to Existing Runtime Semantics:** Does it break any existing packet execution, state machine, or event flow?
6. **No duplicate behavior:** Does it create a second implementation of something that already exists?
7. **No second source of truth:** Does it introduce a new canonical definition that already exists elsewhere?

Failure on any of these: REJECT with specific finding. Do not approve "close enough."

## Section 14: Self-Measuring State File

The state file `docs/roadmap/campaign_state.json` must be updated after EVERY state transition. It is the orchestrator's memory. If the orchestrator restarts, it resumes from this file — not from chat history, not from inference, not from git log.

### Recovery from Restart

If the orchestrator process dies or is restarted:

1. Read `docs/roadmap/campaign_state.json`.
2. Parse `in_progress` — each entry may have a stale worker. Reconcile.
3. Check git log for recent merges since last state update.
4. Re-derive `next_dispatchable` from campaign document × state file.
5. If verification is green and `next_dispatchable` non-empty: resume.
6. If verification is red: wait for owner.
7. If state file is missing: reconstruct from campaign document (all packets mark `Completed: Yes` in git) and rebuild.

## Section 15: Campaign Kill Switch

The orchestrator MUST stop the entire campaign immediately — halt all workers, block all dispatches — when any of these occur:

1. **Canonical source conflict detected.** Two frozen documents disagree on the same concept. The invariant has been violated. Human must resolve which document is correct.
2. **A packet requires architectural judgment beyond its scope.** The packet's allowed paths cannot be achieved without modifying architecture, doctrine, or frozen specs. Human must decide: expand scope or reject packet.
3. **A packet proposes modifying a frozen architectural document.** Governance, KM, ADRs, Builder specs are frozen. Worker has overstepped. Human must approve or reject.
4. **Repository-wide validation regresses unexpectedly.** A previously passing test or lint rule now fails systemically (not one test, not one file). Something deeper broke.
5. **Two workers modify overlapping semantic ownership.** If Worker 1 changes `builder_scope.py` while Worker 2 also changes `builder_scope.py` without coordination. Ownership collision. Human must reconcile.
6. **A reviewer rejects the same packet twice for architectural reasons.** Not fixable implementation errors — fundamental design disagreement. Human must break the tie.

When the kill switch fires:
- Halt ALL workers. No new dispatches.
- Set `verification` to `"red"` in campaign state.
- Record the kill-switch reason in `blocked` state entries.
- Await human intervention.
- Do NOT attempt to auto-resolve. Do NOT continue other packets.
- The campaign is paused until the human clears the kill switch.

Events that do NOT trigger the kill switch:
- Test failures (retry).
- Build failures (retry).
- Worker crashes (reassign).
- Merge conflicts (resolve).
- Review rejections for fixable reasons (repair).
- Infrastructure timeouts (retry).
- Single regression on a new packet (expected during implementation).

## Section 16: Campaign Metrics

Tracked across the entire campaign, not per packet. Updated every 5 completed packets.

| Metric | What | Why |
|---|---|---|
| Packets completed / hour | Throughput | Is the campaign making forward progress? |
| First-pass review approval rate | % of packets approved on first review | Are specs clear enough for workers? |
| Retry rate | Avg attempts per packet | Are workers succeeding or struggling? |
| Mean time to green | Avg time from PR open to merge | Where's the bottleneck? |
| Merge success rate | % of PRs merged without revert | Stability |
| Human interventions | Count of escalation triggers | Is the autonomous boundary too tight or too loose? |
| Architectural escalations | Count of spec contradictions, frozen document conflicts, authority oversteps | Is architecture drifting? |
| Regression count | Number of previously passing tests that broke in non-touching areas | Is coupling too high? |
| Validation failures | Count of lint/docs/typecheck failures across the campaign | Is quality holding? |
| Blocked packet count | How many packets are stuck awaiting human/architectural decision | Is the campaign stalling? |
| Kill switch events | Count of campaign-level halts | How often does the system need human intervention? |

These metrics are appended to `metrics` in the campaign state file:

```json
{
  "metrics": {
    "packets_per_hour": 1.7,
    "first_pass_approval_rate": "73%",
    "avg_attempts": 1.4,
    "mean_time_to_green_minutes": 45,
    "merge_success_rate": "95%",
    "human_interventions": 2,
    "architectural_escalations": 1,
    "regression_count": 0,
    "validation_failures": 3,
    "blocked_packet_count": 0,
    "kill_switch_events": 0
  }
}
```

After each phase, evaluate: Did a control prevent a real mistake? Did a review gate catch an actual bug? Did an invariant stop architectural drift? Which steps produced no value? If a control never catches anything over many successful packets, flag it for simplification.

## Section 17: Phase Retrospective

After EVERY phase completion, before dispatching the next phase, generate a retrospective answering:

1. **What assumptions were wrong?** Did any spec, ADR, or architecture document describe reality incorrectly?
2. **What architecture proved correct?** Which decisions held up under implementation pressure?
3. **What implementation friction repeated?** Same merge conflict? Same test failure pattern? Same worker misunderstanding?
4. **What should change before the next phase?** Any spec needs clarification? Any invariant needs enforcement? Any process needs simplification?
5. **Did any specification need clarification?** Which document was ambiguous during implementation?
6. **Did any recurring pattern emerge that should become automation?** Something manual that could be encoded as a script, lint rule, or CI check?

The retrospective is written to `docs/roadmap/retrospective_phase_N.md`. It is concise — findings, not narratives. It feeds directly into campaign metrics evaluation and process simplification.

### Retrospective Template

```markdown
# Phase N Retrospective

**Date:** YYYY-MM-DD
**Packets:** X completed, Y retried, Z blocked
**Duration:** N hours

## Wrong Assumptions

- [Assumption]: [What actually happened]. [Evidence].

## Proven Architecture

- [Decision]: [How it held up]. [Evidence].

## Recurring Friction

- [Pattern]: [Frequency]. [Impact].

## Spec Changes Needed

- [Document]: [Clarification needed].

## Automation Candidates

- [Manual work]: [Proposed automation].
```

## Section 18: Phased Rollout

Do NOT launch all 31 packets at once.

1. **Phase 1 only.** Run to completion. Merge.
2. Generate Phase 1 retrospective.
3. Evaluate campaign metrics: if merge success rate >90%, first-pass review >70%, kill switch events = 0.
4. If healthy: authorize Phases 2+ to flow according to the dependency graph.
5. If unhealthy: pause. Fix the orchestration machinery. Then resume Phase 2.

This validates the campaign machinery against a real workload before the campaign becomes too large to reason about.

## Section 19: The One Rule

The orchestrator's overriding instruction:

```
Never implement from a document that is not the canonical source.
Before every packet: resolve canonical ADR, spec, roadmap entry, target.
If documents disagree: stop, report, do not choose.
```

That single rule prevents documentation drift from reappearing.
