# Builder V2 — Execution Engine Redesign

**Status:** Replacement blueprint — not yet implemented. Not ratified. Implementation requires separate ADR.
**Author:** Jacob
**Date:** 2026-08-05
**Ratification:** `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` Decision 4 — preserved as design input. Builder's ratified role is execution control plane (ADR 0017) with internal refactoring (ADR 0036). V2 redesign concepts may inform future ADR amendments.

Building on the organization architecture (`docs/BUILDER_ORGANIZATION.md`), this
document redesigns the execution engine itself. It keeps the primitives that
work (SQLite, worktrees, leases, evidence, review, governance) and replaces
everything else with an engine designed for the agent landscape of 2026.

---

## 1. Engine Principles

**1. The engine is a coordination kernel, not a pipeline.** It does not encode
a sequence of steps. It provides primitives for claiming, isolating, producing,
reviewing, and publishing artifacts. The path through those primitives is
determined by the artifact graph, not by a workflow definition.

**2. Workers are discoverable agents, not subprocess launch targets.** The
engine knows about worker capabilities (roles, model classes, available
providers, worktree readiness). Workers advertise what they can do. The engine
matches needs to capabilities.

**3. The artifact is the message.** Workers do not call each other. They read
artifacts from and write artifacts to the engine. The engine notifies interested
workers when artifacts they consume change state.

**4. Trust is cryptographic, not reputational.** Every artifact has a content
hash bound to the producing worker's identity, the input artifacts it consumed,
and the exact execution context. A reviewer verifies the artifact, not the
worker's claim.

**5. Budget is a first-class constraint.** Every paid operation is gated
through a single ledger. Free work proceeds without budget. The governor is not
a plugin — it is a kernel primitive.

**6. Failure is honest state, not a workflow exception.** Provider exhaustion,
rate limiting, stale leases, and crashed workers are normal operating conditions
that produce durable evidence and resumable state. Nothing is inferred as
success or failure — everything is recorded.

---

## 2. The Kernel

The kernel is a SQLite database plus a thin coordination runtime. It has no
opinion about what work looks like — it manages artifacts, claims, leases,
and evidence.

### 2.1 Core Tables

```sql
-- A unit of intent: what should be accomplished, with what evidence.
CREATE TABLE work_item (
    id            TEXT PRIMARY KEY,          -- stable identifier
    type          TEXT NOT NULL,             -- packet | research | review | refactor | audit | doc | image
    state         TEXT NOT NULL,             -- proposed | approved | claimed | running | blocked | done | failed | cancelled
    model_class   TEXT NOT NULL,             -- free-exec | free-exec-blocked | paid-author | paid-exec | human | idea
    priority      INTEGER NOT NULL DEFAULT 0,
    parent_id     TEXT REFERENCES work_item(id),  -- initiative, mission, parent packet
    dependencies  TEXT NOT NULL DEFAULT '[]',      -- JSON array of work_item ids
    contract      TEXT NOT NULL,             -- JSON: the full work contract
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- A role definition: what kind of worker can do what.
CREATE TABLE role (
    id            TEXT PRIMARY KEY,          -- implementer | reviewer | planner | research | qa | ...
    capabilities  TEXT NOT NULL,             -- JSON: {produces: [artifact types], consumes: [artifact types], model_classes: [...]}
    concurrency   INTEGER NOT NULL DEFAULT 1 -- max parallel instances of this role
);

-- A worker instance: a live agent that can claim and execute work.
CREATE TABLE worker (
    id            TEXT PRIMARY KEY,
    role_id       TEXT NOT NULL REFERENCES role(id),
    model         TEXT NOT NULL,             -- provider/model
    provider      TEXT NOT NULL,
    cost_tier     TEXT NOT NULL,             -- free | cheap | frontier
    state         TEXT NOT NULL,             -- idle | busy | degraded | dead
    capabilities  TEXT NOT NULL,             -- JSON: has_worktree, has_browser, has_shell, allowed_paths
    heartbeat_at  TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

-- A lease: exclusive ownership of a work item by a worker for a bounded time.
CREATE TABLE lease (
    work_item_id  TEXT NOT NULL REFERENCES work_item(id),
    worker_id     TEXT NOT NULL REFERENCES worker(id),
    token         TEXT NOT NULL UNIQUE,      -- cryptographic lease token
    version       INTEGER NOT NULL,          -- monotonic claim version
    acquired_at   TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    released_at   TEXT,                      -- null = active
    PRIMARY KEY (work_item_id, version)
);

-- An artifact: a durable named object produced by a worker.
CREATE TABLE artifact (
    id            TEXT PRIMARY KEY,          -- content hash (SHA-256)
    work_item_id  TEXT NOT NULL REFERENCES work_item(id),
    artifact_type TEXT NOT NULL,             -- diff | review_verdict | screenshot | benchmark | report | doc | ...
    worker_id     TEXT NOT NULL REFERENCES worker(id),
    mime_type     TEXT NOT NULL,             -- application/json | image/png | text/markdown | ...
    content_ref   TEXT NOT NULL,             -- filesystem path or inline content reference
    content_hash  TEXT NOT NULL,             -- SHA-256 of content
    input_hashes  TEXT NOT NULL,             -- JSON: {artifact_id: hash, ...} — the artifacts consumed
    created_at    TEXT NOT NULL,
    verified      INTEGER NOT NULL DEFAULT 0 -- 0 = unverified, 1 = verified by a separate worker
);

-- An evidence chain: links artifacts to each other and to their verification.
CREATE TABLE evidence_chain (
    artifact_id   TEXT NOT NULL REFERENCES artifact(id),
    verifier_id   TEXT REFERENCES worker(id),
    verification  TEXT,                      -- JSON: methodology, result, timestamp
    parent_hash   TEXT REFERENCES artifact(id),
    chain_root    TEXT NOT NULL REFERENCES artifact(id),  -- root artifact of this evidence chain
    created_at    TEXT NOT NULL,
    PRIMARY KEY (artifact_id, verifier_id)
);

-- Budget ledger: every paid operation.
CREATE TABLE ledger (
    id            TEXT PRIMARY KEY,
    work_item_id  TEXT REFERENCES work_item(id),
    worker_id     TEXT REFERENCES worker(id),
    operation     TEXT NOT NULL,             -- plan | implement | review | research | audit
    model         TEXT NOT NULL,
    provider      TEXT NOT NULL,
    tokens_in     INTEGER,
    tokens_out    INTEGER,
    cost_cad      REAL,                      -- estimated CAD at snapshot prices
    dispatched_at TEXT NOT NULL,
    settled_at    TEXT
);

-- Scheduling: which work items are eligible and why.
CREATE TABLE schedule (
    work_item_id  TEXT PRIMARY KEY REFERENCES work_item(id),
    eligible_at   TEXT NOT NULL,             -- when it became eligible
    reason        TEXT NOT NULL,             -- why (dependencies satisfied, unblocked, retry)
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_after TEXT                  -- backoff for retries
);

-- Worker discovery: advertised capabilities for matching.
CREATE TABLE capability (
    worker_id     TEXT NOT NULL REFERENCES worker(id),
    capability    TEXT NOT NULL,             -- has_worktree | has_browser | has_gpu | has_ssh | ...
    detail        TEXT,                      -- JSON: version, limits, constraints
    PRIMARY KEY (worker_id, capability)
);
```

### 2.2 Kernel Operations

The kernel exposes exactly these operations. Everything else is built on top.

```text
-- Work lifecycle
register_work_item(contract) → work_item_id
approve_work_item(id, approver_identity)
cancel_work_item(id, reason)

-- Scheduling
mark_eligible(id, reason)                   -- called when dependencies resolve
defer_until(id, timestamp, reason)          -- backoff, provider exhaustion
next_eligible(role, limit) → [work_item]    -- what should a worker of this role do next?

-- Claims and leases
claim(id, worker_id, capabilities_proof) → lease_token
renew(lease_token) → new_expiry
release(lease_token, reason)
recover_stale_leases()                      -- run periodically

-- Artifacts
write_artifact(work_item_id, type, content, input_hashes) → artifact_id
read_artifact(artifact_id) → content_ref
verify_artifact(artifact_id, verifier_id, methodology, result)
chain_artifacts(parent_id, child_id)        -- build evidence chain

-- Budget
check_budget(work_item_id, model, operation) → allowed | denied | downgraded
record_spend(ledger_entry)
spend_report(window_start, window_end) → report

-- Worker registry
register_worker(role, model, provider, capabilities) → worker_id
heartbeat(worker_id)
deregister_worker(worker_id)

-- Observation
list_work_items(state, role, limit)
get_evidence_chain(artifact_id) → [artifact]
worker_status(worker_id) → state, current_lease, recent_artifacts
```

### 2.3 What the Kernel Does NOT Do

- It does not route work. The scheduler marks eligibility; workers pull.
- It does not understand packet semantics. A work item's contract is opaque JSON to the kernel.
- It does not verify artifact content. Verification is a worker's job.
- It does not decide merge eligibility. Publication is a work item like any other.
- It does not manage worktrees directly. Worktree provisioning is a worker capability.
- It does not pick models. Workers register their model; budget gates the operation.

---

## 3. Scheduling

### 3.1 Artifact-Driven Scheduling

The scheduler does not walk a pipeline. It maintains a set of eligibility
conditions per work item:

```text
A work item is eligible when:
  1. Its state is 'approved'
  2. All dependency work items are in state 'done'
  3. Its model_class budget check passes (or it's free)
  4. It is not deferred (not in backoff)
  5. No conflicting lease exists (another worker working on overlapping paths)
```

When a work item transitions to `done`, the kernel evaluates all work items
that depend on it. Those whose dependency set is now complete are marked
eligible. This is a single SQL query:

```sql
UPDATE schedule SET eligible_at = datetime('now')
WHERE work_item_id IN (
  SELECT w.id FROM work_item w
  WHERE w.state = 'approved'
    AND NOT EXISTS (
      SELECT 1 FROM work_item d
      WHERE d.id IN (SELECT value FROM json_each(w.dependencies))
        AND d.state != 'done'
    )
    AND NOT EXISTS (
      SELECT 1 FROM schedule s
      WHERE s.work_item_id = w.id
        AND s.next_attempt_after > datetime('now')
    )
);
```

### 3.2 Worker Pull Model

Workers call `next_eligible(role, limit)`. The kernel returns work items that
match the worker's role and whose model class aligns with the worker's cost
tier. A free worker gets `free-exec` and `free-exec-blocked` work. A frontier
worker gets `paid-exec` and `paid-author` work (after budget check).

The worker then calls `claim()` to take ownership. Claiming is atomic — two
workers cannot claim the same item.

This is pull, not push, because:
- Workers know their own availability better than the kernel does.
- A worker that crashes or becomes overloaded simply stops pulling.
- Adding workers doesn't require reconfiguring dispatchers.
- Workers can be heterogeneous (some have browsers, some have GPUs).

### 3.3 Concurrency Control

The kernel enforces concurrency through overlapping path detection. When a
worker claims a work item, the kernel compares its `allowed_paths` (from the
contract) against the `allowed_paths` of all currently leased work items. If
any paths overlap, the claim is rejected with `conflicting_lease`.

```python
def check_path_conflicts(work_item_id: str) -> bool:
    contract = json.loads(get_work_item(work_item_id)["contract"])
    paths = set(contract.get("allowed_paths", []))
    if not paths:
        return False

    active = list_active_leases()
    for lease in active:
        other_contract = json.loads(get_work_item(lease["work_item_id"])["contract"])
        other_paths = set(other_contract.get("allowed_paths", []))
        if paths & other_paths:
            return True
    return False
```

### 3.4 Retry and Backoff

When a work item fails (worker reports `failed`, lease expires without result,
or reviewer rejects), the kernel applies a role-specific backoff:

| Failure kind | Backoff | Rationale |
|---|---|---|
| Provider exhaustion | 5 min | Provider may recover; retry aggressively |
| Worker crash | 30 sec | Likely transient; fast retry |
| Review rejection (fixable) | 0 sec | Immediate retry after repair |
| Review rejection (architectural) | block until escalated | Human decision needed |
| Validation failure | 0 sec | Immediate retry with repair worktree |
| Three identical failures | block permanently | Systematic issue; operator intervention |

After backoff, the work item is re-marked eligible. The attempt count
increments. After `max_attempts` (default 3), the item is permanently
`failed`.

### 3.5 Priority and Starvation

Priority is a simple integer. Higher priority items are returned first by
`next_eligible`. But to prevent starvation, after an item has been eligible for
more than 4 hours, it receives a +1 priority boost per hour. This is computed
at query time:

```sql
SELECT w.id, w.priority +
  CAST((julianday('now') - julianday(s.eligible_at)) * 24 AS INTEGER)
  AS effective_priority
FROM work_item w
JOIN schedule s ON w.id = s.work_item_id
ORDER BY effective_priority DESC
LIMIT ?
```

---

## 4. Agent Orchestration

### 4.1 Worker Discovery

Workers register with the kernel on startup. Registration is the worker saying:
"I am a reviewer, running on `deepseek-v4-pro`, cost tier `frontier`, I have a
worktree at `/path`, and I can also run a browser."

```json
{
  "role": "reviewer",
  "model": "openrouter/deepseek/deepseek-v4-pro",
  "provider": "openrouter",
  "cost_tier": "frontier",
  "capabilities": {
    "has_worktree": true,
    "has_browser": false,
    "has_shell": true
  }
}
```

Workers heartbeat every 10 seconds. After 30 seconds without a heartbeat, the
worker is marked `dead`. Its leases are released. Its claimed work items go
back to `approved` (if no work was produced) or `blocked` (if work was in
progress).

### 4.2 Role-Based Routing

The `next_eligible` query matches work items to workers by role. The routing
logic is:

```sql
SELECT w.* FROM work_item w
JOIN schedule s ON w.id = s.work_item_id
WHERE s.eligible_at IS NOT NULL
  AND s.next_attempt_after <= datetime('now')
  AND w.model_class IN (
    SELECT value FROM json_each(
      (SELECT r.capabilities FROM role r WHERE r.id = ?)
    )
  )
  AND NOT EXISTS (
    -- no active lease on this item
    SELECT 1 FROM lease l
    WHERE l.work_item_id = w.id AND l.released_at IS NULL
  )
ORDER BY w.priority DESC
LIMIT ?
```

The worker's cost tier further filters: a `free` worker only sees `free-exec`
and `free-exec-blocked` work items, even if its role could handle paid work.

### 4.3 Multi-Worker Coordinated Work

Some work items require multiple workers in sequence or parallel. The kernel
does not sequence them — it models them as separate work items with
dependencies.

**Sequential (implement → review):**
```
work_item: impl-123 (role: implementer)
work_item: review-123 (role: reviewer, dependencies: [impl-123])
```

The review work item becomes eligible when the implementation work item
reaches `done`. The reviewer worker (a different worker identity) claims it,
reads the implementation artifact, and writes a review artifact.

**Parallel (two independent implementations):**
```
work_item: impl-A (role: implementer, allowed_paths: [gateway/auth.py])
work_item: impl-B (role: implementer, allowed_paths: [gateway/chat.py])
```

These become eligible simultaneously. Two implementer workers can claim them in
parallel because their paths don't overlap. The kernel's path-conflict check
prevents accidental collision.

**Phased (research → plan → implement):**
```
work_item: research-42 (role: research, dependencies: [])
work_item: plan-42   (role: planner, dependencies: [research-42])
work_item: impl-42   (role: implementer, dependencies: [plan-42])
```

### 4.4 Worker Replaceability

A worker is identified by role + model + provider, not by a persistent ID. If
a worker crashes, a new worker of the same role registers and picks up where
the old one left off. The lease system handles ownership transfer: the kernel
releases stale leases, marks the work item back to `approved`, and the new
worker claims it.

The new worker reads the previous worker's artifacts (final report, partial
output) from the artifact store and continues. It does not need the old
worker's memory, chat log, or handoff note.

---

## 5. Retries

### 5.1 The Retry Loop Is In the Kernel

The kernel owns the retry lifecycle, not the worker. A worker attempts once.
If it fails, the kernel schedules a retry. The retry may go to a different
worker.

```
worker attempts work_item
  → worker reports outcome: succeeded | failed_recoverable | failed_permanent
  → kernel records outcome
  → if succeeded: mark done, cascade eligibility to dependents
  → if failed_recoverable: increment attempt_count, apply backoff, re-mark eligible
  → if failed_permanent: mark failed, cascade to parent
  → if worker crashes (lease expires): release lease, mark eligible for retry
```

### 5.2 What Changes Between Retries

| Attempt factor | Behavior |
|---|---|
| Same worker? | Not guaranteed. Any worker of the same role can retry. |
| Same worktree? | If previous attempt was `repairable` (validation failure, fixable review rejection), reuse dirty tree. Otherwise, fresh worktree. |
| Same model? | If provider exhaustion was the cause, the kernel may route to a different provider. |
| Budget consumed? | Failed attempts do not settle the governor allowance — the work is still owed. |

### 5.3 Retry Budget

Each work item has:
- `max_attempts`: default 3, configurable per contract
- `max_consecutive_identical_failures`: default 3 (infrastructure crashes)

After `max_attempts`, the work item is `failed` permanently. After
`max_consecutive_identical_failures`, the work item is `blocked` (requires
operator inspection — something is systematically wrong).

---

## 6. Leasing

### 6.1 Lease Model

A lease is the kernel's mechanism for exclusive ownership. It has three
properties:

1. **Exclusive:** Only one worker holds a lease on a work item at a time.
2. **Bounded:** Every lease expires. No infinite leases.
3. **Renewable:** A worker can extend its lease by proving it's still alive.

### 6.2 Lease Lifecycle

```
claim(work_item_id, worker_id, proof) → lease_token, version
  └─ Sets work_item.state = 'claimed'
  └─ Creates lease row with expires_at = now + lease_duration
  └─ Worker may now begin work

heartbeat(worker_id) → extends lease
  └─ Resets expires_at = now + lease_duration
  └─ If worker is 'dead', this does nothing

start_work(lease_token, version) → work_item.state = 'running'
  └─ Must present valid token and correct version

complete_work(lease_token, version, artifact_refs) → work_item.state = 'done'
  └─ Releases the lease

fail_work(lease_token, version, reason, failure_kind) → work_item.state = 'failed'
  └─ Releases the lease
  └─ failure_kind determines retry behavior

release(lease_token, version, reason)
  └─ Worker voluntarily gives up the lease
  └─ Work item returns to 'approved'
```

### 6.3 Lease Fencing

Every lease mutation must present:
1. The correct `lease_token` (a random 256-bit value, not guessable)
2. The correct `version` (monotonic counter that increments on each claim)

A stale token or wrong version is rejected. This prevents:
- A zombie worker process from modifying a work item after its lease expired
- A worker from releasing a lease that isn't theirs
- Race conditions between claim and heartbeat

### 6.4 Lease Duration

| Work class | Lease duration | Rationale |
|---|---|---|
| `free-exec` | 30 min | Free models are slow; long enough for ladder fallback |
| `paid-exec` | 15 min | Paid models are faster; shorter leash |
| `paid-author` | 30 min | Reasoning takes time |
| Review | 10 min | Reviews should be fast |
| Research | 60 min | Investigation takes real time |

### 6.5 Stale Lease Recovery

The kernel runs `recover_stale_leases()` on startup and periodically (every 60
seconds). It finds leases where `expires_at < now AND released_at IS NULL`:

- If the work item is `claimed` (work never started): return to `approved`
- If the work item is `running` (work was in progress): set to `blocked` with
  reason `stale_lease`, save any artifacts the worker produced before crashing

Never auto-requeue a `running` work item — the operator must inspect.

---

## 7. Artifact Flow

### 7.1 Artifacts Are the Data Model

Everything a worker produces is an artifact, recorded in the kernel with:

- Content hash (integrity)
- Worker identity (provenance)
- Input hashes (what it was built from)
- Creation timestamp

Artifacts are immutable. A worker never modifies an existing artifact — it
writes a new one.

### 7.2 Artifact Types

| Type | Produced by | Consumed by | Format |
|---|---|---|---|
| `packet_contract` | Planner | Implementer, Reviewer | JSON |
| `diff` | Implementer | Reviewer, Release Manager | git diff |
| `review_verdict` | Reviewer | Release Manager, Implementer | JSON |
| `validation_result` | QA, Implementer | Reviewer, Release Manager | JSON |
| `research_finding` | Research | Planner, Chief Architect | Markdown + JSON |
| `screenshot` | Browser Verification | UI/UX, Release Manager | PNG |
| `benchmark` | Performance | Chief Architect, Planner | JSON |
| `architectural_decision` | Chief Architect | All | Markdown |
| `security_audit` | Security | Release Manager | JSON |
| `merge_record` | Release Manager | All | JSON |
| `health_report` | Operations | All | JSON |
| `image_artifact` | Image Team | Browser Verification | PNG/JPEG |
| `kb_entry` | Knowledge Curator | All | Markdown |

### 7.3 Artifact Chains

Artifacts form directed acyclic graphs through their `input_hashes`. An
implementation diff artifact's input is the packet contract artifact. A review
verdict artifact's inputs are the packet contract and the diff. This creates a
verifiable chain:

```
packet_contract (SHA: abc123)
  └── diff (SHA: def456, inputs: {packet_contract: abc123})
        └── review_verdict (SHA: ghi789, inputs: {packet_contract: abc123, diff: def456})
              └── merge_record (SHA: jkl012, inputs: {review_verdict: ghi789, diff: def456})
```

### 7.4 Evidence Resolution

When a work item completes, the kernel resolves its evidence chain. It walks
the artifact DAG from the terminal artifact back to the root, verifying that:
- Every required artifact type is present
- Every artifact has been verified by a different worker than its producer
- The chain is unbroken (no missing links)
- The final artifact's state matches the work item's declared outcome

This is the kernel's definition of "done" — an unbroken, verified evidence
chain.

---

## 8. Trust

### 8.1 Cryptographic Identity

Every worker has a cryptographic identity (an Ed25519 keypair generated at
registration time). Artifacts are signed. The kernel verifies signatures before
accepting artifacts.

```
artifact = {
  id: SHA256(content),
  content: {...},
  signature: sign(worker_private_key, SHA256(content)),
  worker_public_key: "...",
  timestamp: "..."
}
```

This prevents:
- A worker from claiming another worker's identity
- An artifact from being tampered with after creation
- A worker from repudiating its own output

### 8.2 Artifact Verification

Every artifact must be independently verified before it can be part of a
completed evidence chain. Verification is a separate work item:

```
work_item: verify-diff-123
  role: reviewer
  dependencies: [impl-123]
  contract: {artifact_to_verify: "diff-123", methodology: "read diff, check scope, run gate"}
```

The verifier (always a different worker) writes a verification artifact. The
kernel records the verification in `evidence_chain`.

An unverified artifact may be read by any worker, but a work item cannot reach
`done` until all its required artifact types are verified.

### 8.3 Trust Is Not Identity

The kernel does not trust a worker because of what it claims to be. It trusts
an artifact because:
1. It has a verified chain back to an approved contract
2. Every link was verified by an independent worker
3. Every artifact's content hash matches
4. Every signature is valid

A worker claiming to be a "reviewer" who signs an `approve` verdict is not
trusted — the reviewer's evidence (what did you check? what was the result?)
is trustable only after a separate verification worker confirms it.

### 8.4 What the Kernel Cannot Trust

- Worker claims of success without evidence
- A worker reviewing its own output
- Two workers sharing the same cryptographic identity
- An artifact whose input hashes reference artifacts that have since been
  modified (detected by hash mismatch)

---

## 9. Publication

### 9.1 Publication Is a Work Item

Publication (merge, tag, release) is modeled as a work item like any other. It
has:

```
work_item: publish-impl-123
  role: release_manager
  dependencies: [impl-123, review-123, verify-ui-123]
  contract: {
    type: "merge",
    base_sha: "abc123",
    branch: "builder/impl-123",
    target: "main",
    required_gates: ["ci_green", "review_approved", "browser_verified", "security_cleared"],
    auto_merge: true  -- per ADR 0021 auto-merge eligibility
  }
```

### 9.2 Gate Evaluation

The release manager worker evaluates each required gate:

| Gate | How evaluated |
|---|---|
| `ci_green` | Query GitHub Checks API for the branch |
| `review_approved` | Read review artifact, verify verdict is `approve` |
| `browser_verified` | Read browser verification artifact, verify evidence exists |
| `security_cleared` | Read security audit artifact, verify no blocking findings |
| `validation_passed` | Read validation artifact, verify exit code is 0 |
| `diff_scope_clean` | Read scope artifact, verify no violations |

All gates must pass. If any gate fails, the publish work item is `blocked` with
the specific failing gate named.

### 9.3 Merge Execution

If all gates pass and `auto_merge` is true:

```
1. Fetch latest main
2. Merge builder branch into main (or rebase)
3. Push main
4. Tag with version
5. Write CHANGELOG entry
6. Write merge record artifact
7. Mark publish work item done
```

If the merge fails (conflict, CI red after merge), auto-revert:

```
1. Revert the merge on main
2. Push the revert
3. Write revert record artifact
4. Mark publish work item failed
5. Escalate to operations
```

### 9.4 Auto-Merge Boundaries

Per ADR 0021, auto-merge is disallowed for:
- Dependencies or lockfiles
- CI workflow changes
- Auth, secrets, permissions, or security boundaries
- Destructive operations or data migration
- Schema migrations (unless separately approved)
- UX, copy, visual, or product judgment requiring human inspection
- Unresolved cross-initiative path collisions
- Gates that are not runnable and falsifiable
- Any material scope expansion

When `auto_merge` is false, the publish work item transitions to `blocked`
after verifying all non-human gates. It waits for Jacob's explicit merge
command.

### 9.5 Publication Is Evidence

The publication itself produces artifacts:
- `merge_record` — what was merged, from what SHA, to what SHA
- `changelog_entry` — what changed, for which version
- `tag_record` — the version tag created

These artifacts feed into the evidence chain, completing the work item's full
lifecycle.

---

## 10. Budgeting

### 10.1 The Ledger Is Part of the Kernel

The budget ledger is not a separate system. It's a table in the kernel's
SQLite database. Every paid operation writes a row before dispatch.

### 10.2 Budget Check

Before any paid worker claims a work item, the kernel checks:

```python
def check_budget(work_item_id: str, model: str, operation: str) -> Decision:
    item = get_work_item(work_item_id)

    # Free work always passes
    if item["model_class"] in ("free-exec", "free-exec-blocked"):
        return Decision.allowed(route=ROUTE_FREE)

    # Idea and human work don't consume budget
    if item["model_class"] in ("human", "idea"):
        return Decision.allowed(route=ROUTE_FREE)

    # Check reserve
    config = load_reserve_config()
    ledger = get_ledger_current_window()
    reserve = config["weekly_budget_cad"] - ledger["total_spent_cad"]

    if reserve <= 0:
        return Decision.denied(["budget_exhausted"])

    # Estimate cost
    estimated_cost = estimate_cost(model, operation)

    if route == ROUTE_FRONTIER:
        if reserve < config["frontier_floor_ratio"] * config["weekly_budget_cad"]:
            return Decision.downgraded(to_route=ROUTE_CHEAP, reasons=["frontier_reserve_low"])

    if estimated_cost > reserve:
        return Decision.denied(["insufficient_reserve"])

    return Decision.allowed(route=route)
```

### 10.3 Cost Tiers

| Tier | Models | Used for | Weekly allocation |
|---|---|---|---|
| `free` | OpenCode free ladder | `free-exec`, `free-exec-blocked` | Unlimited |
| `cheap` | `deepseek-v4-flash` | Routine paid work | CAD 4.50/week (75%) |
| `frontier` | `deepseek-v4-pro` | Review, planning, difficult execution | CAD 1.50/week (25%) |

### 10.4 Idempotent Spending

The kernel guarantees that the same `(work_item_id, operation, head_sha)` is
only paid for once. The compute governor (now a kernel primitive) rejects
duplicate dispatches:

```sql
SELECT 1 FROM ledger
WHERE work_item_id = ?
  AND operation = ?
  AND settled_at IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM work_item w
    WHERE w.id = work_item_id
      AND json_extract(w.contract, '$.base_sha') = ?
  )
```

A failed attempt does not settle the allowance — the work is still owed. Only
a `succeeded` outcome settles. This prevents paying twice for the same failed
attempt and then the successful retry.

---

## 11. Concurrency

### 11.1 Path-Based Concurrency Control

The kernel prevents two workers from modifying overlapping files
simultaneously. This is enforced at claim time, not at commit time (fail
early, not after work is done).

```python
def can_claim(work_item_id: str, worker_id: str) -> bool:
    # Check no other worker holds a lease on this item
    if has_active_lease(work_item_id):
        return False

    # Check path conflicts
    contract = json.loads(get_work_item(work_item_id)["contract"])
    paths = set(contract.get("allowed_paths", []))

    if paths:
        active_leases = list_active_leases()
        for lease in active_leases:
            other_contract = json.loads(
                get_work_item(lease["work_item_id"])["contract"]
            )
            other_paths = set(other_contract.get("allowed_paths", []))
            if paths & other_paths:
                return False

    return True
```

### 11.2 Role-Based Concurrency Limits

Each role has a `concurrency` field in the `role` table. The kernel enforces
that no more than `concurrency` workers of that role are `busy` at once.

```sql
SELECT COUNT(*) FROM worker
WHERE role_id = ?
  AND state = 'busy'
HAVING COUNT(*) >= (SELECT concurrency FROM role WHERE id = ?)
```

If the limit is reached, `next_eligible` returns empty for that role until a
worker finishes or releases.

### 11.3 Maximum Parallelism

The kernel itself is single-writer (SQLite). But worker parallelism is high:

| Role | Max concurrent | Rationale |
|---|---|---|
| Implementer | 4 | Limited by Mac resources (4 worktrees) |
| Reviewer | 2 | Reviews are fast, two is plenty |
| Planner | 1 | One planner avoids duplicate packets |
| Research | 3 | Independent investigations can run in parallel |
| QA | 2 | Test suites don't parallelize well |
| Browser Verification | 1 | One browser at a time |
| Release Manager | 1 | Serial merges to main |
| Chief Architect | 1 | One architectural authority |
| Others | 1 | Most supporting roles are singletons |

### 11.4 Deadlock Prevention

The kernel prevents deadlock through dependency ordering: a work item cannot
have a cyclic dependency. The kernel rejects contracts with cycles at
registration time (topological sort on the dependency graph).

Path-conflict deadlocks are prevented by the claim ordering: a worker that
cannot claim because of a path conflict simply retries later. The conflicting
worker will eventually release.

---

## 12. Worker Discovery

### 12.1 Registration Protocol

When a worker starts, it registers with the kernel:

```
POST /builder/worker/register
{
  "role": "implementer",
  "model": "opencode/deepseek-v4-flash-free",
  "provider": "opencode",
  "cost_tier": "free",
  "capabilities": {
    "has_worktree": true,
    "has_shell": true,
    "has_browser": false,
    "has_git": true,
    "allowed_paths": ["gateway/", "tests/"]
  }
}
```

The kernel responds with a `worker_id` and a `session_token` for heartbeats.

### 12.2 Capability Advertisement

Capabilities are key-value pairs. Standard capabilities:

| Capability | Meaning |
|---|---|
| `has_worktree` | Can operate in an isolated git worktree |
| `has_shell` | Can run shell commands |
| `has_browser` | Can run browser automation (Playwright, browser-use) |
| `has_git` | Can commit and push |
| `has_gpu` | Can run GPU workloads (image generation, ML) |
| `has_api_access` | Can make HTTP requests |
| `allowed_paths` | Which filesystem paths this worker may access |
| `max_timeout` | Maximum duration for a single work item |

Custom capabilities are supported. An image generation worker advertises
`has_comfyui: true` and `has_runpod: true`.

### 12.3 Heartbeat

Workers heartbeat every 10 seconds:

```
POST /builder/worker/heartbeat
{
  "worker_id": "worker-abc123",
  "session_token": "...",
  "current_lease": "lease-xyz789" | null,
  "load": 0.5
}
```

The kernel updates the worker's `heartbeat_at`. If a worker misses 3
heartbeats (30 seconds), it's marked `dead`.

### 12.4 Worker Ladder

Multiple workers of the same role can register. The kernel's `next_eligible`
returns work items that match the worker's capabilities AND cost tier. A free
worker sees free work, a frontier worker sees paid work after budget check.

If a free worker exhausts the free-work queue, it goes idle. If a frontier
worker finds no paid work, it goes idle. Neither tier bleeds into the other.

The free-worker ladder (try free model A, if exhausted try free model B) is
handled by the worker itself, not the kernel. The worker retries with different
models; the kernel only sees claims and results.

---

## 13. Organization

### 13.1 Roles Are Kernel Primitives

The roles defined in `BUILDER_ORGANIZATION.md` map to kernel role entries. Each
role declares:

```json
{
  "id": "implementer",
  "capabilities": {
    "produces": ["diff", "validation_result", "final_report"],
    "consumes": ["packet_contract"],
    "model_classes": ["free-exec", "paid-exec"]
  },
  "concurrency": 4
}
```

### 13.2 Organization Hierarchy

The escalation ladder from the organization architecture is enforced by
dependency chains:

```
chief_architect (owns architectural decisions)
  ├── planner (consumes architectural decisions, produces packet contracts)
  │     ├── implementer (consumes packet contracts)
  │     └── research (consumes planner questions)
  └── reviewer (consumes implementer output, escalates to chief architect)
```

A reviewer who finds an architectural violation doesn't "tell" the chief
architect — it creates a review verdict artifact with `escalation:
"architectural"`. The kernel detects this and makes the work item eligible for
the chief architect role.

### 13.3 The Organization Is the Scheduling Domain

Work items are routed by role, not by a global queue. Each role has its own
eligible work queue. The kernel returns the highest-priority eligible work for
the requesting worker's role.

This means the organization structure IS the scheduling structure. There is no
separate "orchestrator" that decides what happens next — the artifact graph and
role registry together determine it.

---

## 14. Communication

### 14.1 Artifact-Based Communication

Workers do not communicate with each other. They communicate through the kernel
by reading and writing artifacts. This is the entire communication model.

### 14.2 Notification Model

When an artifact is written, the kernel evaluates which work items just became
eligible (their dependency set is now complete). It does NOT push notifications
— workers pull. But the kernel provides a `watch(work_item_id)` operation that
returns immediately if the item is eligible, or blocks until it becomes
eligible. This gives workers the option of blocking wait instead of polling.

### 14.3 Escalation Protocol

Escalation is modeled as an artifact with type `escalation`. It names the
escalated-to role, the reason, and references the triggering artifact.

```json
{
  "type": "escalation",
  "from_role": "reviewer",
  "to_role": "chief_architect",
  "reason": "architectural_violation",
  "triggering_artifact": "review-verdict-ghi789",
  "detail": "packet introduces a circular import between gateway/ and tools/"
}
```

The kernel creates an implicit work item for the escalated-to role when an
escalation artifact is written. This work item has the escalation artifact as
its sole dependency-in-progress. When the escalated-to role produces a
response artifact, the original work item is unblocked.

### 14.4 The Event Log

Every kernel operation writes to an append-only event log:

```sql
CREATE TABLE event_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT NOT NULL,
    event_type TEXT NOT NULL,    -- work_claimed | artifact_written | lease_expired | ...
    payload    TEXT NOT NULL,    -- JSON
    work_item_id TEXT REFERENCES work_item(id),
    worker_id    TEXT REFERENCES worker(id),
    artifact_id  TEXT REFERENCES artifact(id)
);
```

The event log is the single source of truth for what happened. Every state
change, claim, artifact write, verification, and escalation is recorded. The
event log is never truncated or modified.

---

## 15. Observability

### 15.1 Read-Only Projections

The kernel provides read-only projections. No consumer (UI, Kitty, operator)
joins kernel tables — they query projections:

```sql
-- Work item status with its evidence chain
SELECT w.*, GROUP_CONCAT(a.artifact_type) as evidence_types
FROM work_item w
LEFT JOIN artifact a ON a.work_item_id = w.id
GROUP BY w.id;

-- Worker load and health
SELECT w.*, COUNT(l.work_item_id) as active_leases
FROM worker w
LEFT JOIN lease l ON l.worker_id = w.id AND l.released_at IS NULL
GROUP BY w.id;

-- Budget consumption
SELECT DATE(dispatched_at) as day, SUM(cost_cad) as spent
FROM ledger
GROUP BY day
ORDER BY day DESC;
```

### 15.2 The Builder Operator UI

The operator UI consumes these projections. It does not write to the kernel. It
visualizes:
- Work items by state, role, priority
- Active leases and workers
- Evidence chains with artifact links
- Budget consumption and remaining reserve
- Escalations and blocked items
- Event log timeline

The CLI remains the repair floor for operator actions (release, cancel,
override).

### 15.3 Instrumentation

Every kernel operation is instrumented:

```python
@instrument
def claim(work_item_id: str, worker_id: str) -> LeaseToken:
    start = time.monotonic()
    result = _claim_impl(work_item_id, worker_id)
    duration_ms = (time.monotonic() - start) * 1000
    emit_metric("kernel.claim.duration_ms", duration_ms)
    emit_metric("kernel.claim.result", "success" if result else "conflict")
    return result
```

Metrics are written to the event log and exposed as a projection. An
observability work item (role: operations) can query metrics and produce
health reports.

### 15.4 What Observability Covers

| Signal | Source | Consumer |
|---|---|---|
| Active work items by state | `work_item` projection | Operator UI, Kitty |
| Worker health and load | `worker` projection | Operations |
| Budget remaining | `ledger` projection | Compute governor, Operations |
| Blocked/escalated items | `work_item` projection (state=blocked) | Operator, Chief Architect |
| Evidence chain completeness | `artifact` + `evidence_chain` projection | Release Manager |
| Event timeline | `event_log` | All |
| Kernel operation latency | Instrumentation metrics | Operations, Performance |

---

## 16. Implementation Path

### 16.1 Phase 1: Kernel Core

Replace the current 27-module Builder with the kernel. This is the minimum
viable replacement:

- `builder_kernel.py` — the kernel operations from §2.2
- `builder_kernel_db.py` — the SQLite schema from §2.1
- `builder_kernel_leases.py` — lease management from §6
- `builder_kernel_schedule.py` — artifact-driven scheduling from §3
- `builder_kernel_budget.py` — ledger and budget check from §10
- `builder_kernel_artifacts.py` — artifact store and evidence chains from §7
- `builder_kernel_workers.py` — worker registry and discovery from §12

### 16.2 Phase 2: Worker Adapters

Adapt the existing worker launches to the kernel protocol:

- `builder_worker_adapter.py` — wraps OpenCode, Claude Code, and shell workers
  to register, heartbeat, claim, produce artifacts, and report outcomes through
  the kernel API

### 16.3 Phase 3: Organization Layer

Implement the role-based routing from §13 — roles defined as kernel
configuration, `next_eligible` extended with role matching, and the escalation
protocol implemented as specialized work items.

### 16.4 Phase 4: Publication and Observability

Implement the publication work item type from §9, the read-only projections
from §15.1, and the operator UI consuming them.

### 16.5 What Survives from the Current Builder

- `builder_queue.py` → `builder_kernel.py` (redesigned, but the concept of
  queue-as-kernel survives)
- `builder_queue_db.py` → `builder_kernel_db.py` (new schema, same SQLite)
- `builder_queue_leases.py` → `builder_kernel_leases.py` (same lease concept,
  simpler table)
- `builder_runner.py` → worktree provisioning moves into the worker adapter
- `builder_loop.py` → the repair loop moves into the kernel scheduler
- `builder_attempt.py` → attempts become retries in the kernel
- `builder_publish.py` → publication work item type
- `builder_initiative.py` → initiatives become parent work items with
  dependencies
- `builder_contract.py` → contracts are the `contract` JSON column on work
  items
- `builder_scope.py` → scope enforcement is path-based concurrency control

### 16.6 What Is Removed

- `builder_adapters.py` — workers register themselves now
- `builder_brief.py` — briefs are artifacts, not a separate module
- `builder_isc.py` — ISC checking is artifact verification
- `builder_report.py` — reports are artifacts
- `builder_events.py` — events are the kernel event log
- `builder_runtime.py` — runtime state is kernel state
- `builder_worker_session.py` — workers announce their sessions through
  registration and heartbeat
- `builder_identity.py` — replaced by cryptographic keypairs
- `builder_doctor.py` — replaced by observability projections
- `builder_status.py` — replaced by read-only projections
- `builder_context.py` — context assembly is artifact resolution
- `builder_run.py` — initiative runner becomes multi-work-item dependency
  resolution
- `builder_cli.py` / `builder_commands.py` — rebuilt on the kernel API

13 modules removed out of 27. The remaining 14 are redesigned as 7 kernel
modules plus 1 worker adapter.

---

## 17. Design Decisions

### Decision 1: Pull, Not Push

Workers pull work from the kernel. The kernel does not push work to workers.
This avoids the need for a persistent dispatcher, handles worker heterogeneity
cleanly, and naturally handles worker crashes (dead workers stop pulling).

### Decision 2: Artifacts as the Communication Model

Workers don't call each other. They read and write artifacts. This decouples
worker lifetimes, makes the system introspectable, and makes evidence chains
trivial to construct.

### Decision 3: Single SQLite Kernel

The kernel is a single SQLite database. There is no separate queue DB, event
DB, or artifact store. One DB means one transaction scope, which makes
atomic operations (claim + check budget + write event) trivial.

### Decision 4: Roles as Configuration, Not Code

Roles are JSON configuration loaded by the kernel. Adding a new role is a
config change, not a code change. Role capabilities define what work they
can do — the kernel doesn't need to know the semantics.

### Decision 5: Evidence Chains, Not State Machines

The current Builder models everything as a state machine (queued → claimed →
running → pr_opened → awaiting_review → done). The V2 engine models everything
as an evidence chain. "Done" means the chain is complete and verified. The
state is derived from the chain, not separately managed.

### Decision 6: Budget in the Kernel, Not Beside It

The current compute governor is a separate module with its own DB. In V2, the
ledger is a kernel table. Budget checks are kernel operations. The governor's
rules are kernel configuration. This makes budget a first-class constraint,
not a bolt-on.

### Decision 7: Cryptographic Trust

The current Builder trusts worker identity (a string). V2 trusts cryptographic
signatures. Every artifact is signed. Every evidence chain is verifiable down
to the key. A worker can't claim to be a different worker. An artifact can't
be tampered with after creation.

### Decision 8: Operator Actions Are Specialized Work Items

Operator actions (release, cancel, override) are not separate commands — they
are work items of type `operator_action` that the kernel routes to the
operations role. This means operator actions are tracked, budgeted (free),
and auditable through the same evidence chain as any other work.

---

## 18. Migration

### From Current State to V2

1. The kernel writes to `data/kittybuilder/builder_kernel.db` (new file).
2. A migration helper reads existing queue tasks and converts them to work
   items with artifact references pointing at existing evidence.
3. The old Builder runs in read-only mode during migration.
4. New workers register with the kernel.
5. When migration is complete, the old Builder is disabled and the kernel
   becomes the single source of truth.
6. The old `builder_queue.db` is archived (not deleted).

### Compatibility

The CLI surface (`./kitty builder ...`) is redesigned but maintains backward
compatibility shims where possible. The `./kitty builder queue *` commands
delegate to the kernel's work item operations. The `./kitty builder initiative *`
commands delegate to kernel work items with parent dependencies.
