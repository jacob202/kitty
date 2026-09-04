# Delivery-System Repair Candidates — 2026-09-03

**Status:** final audit input; **not execution authority** and not a task queue.

**Purpose:** preserve the delivery-system changes that survived the meta-audit without activating a second methodology project. The Lead Integrator decides whether any candidate is needed from observed product failures. Existing Builder/GAR/KX/Git authorities remain authoritative; this file creates no new state machine.

## What the audit actually proved

1. Implementation evidence and user-outcome completion have been conflated.
2. Automated/browser proof is frequently hermetic or stubbed and must not be described as canonical dogfood.
3. Test and acceptance runs have written synthetic records into canonical product stores.
4. Builder packet economics encourage backend/frontend/acceptance fragmentation because isolated Builder worktrees do not have a usable local Node dependency tree.
5. `continue`/multi-agent coordination correctly prevents duplicate ownership, but it needs to preserve proactive discovery without letting discovery silently become a new assignment.
6. Review/model spend needs explicit stop rules; more reviewers do not substitute for empirical product evidence.

## Candidate interventions

### A. Thin outcome authority

For the **currently active** user outcome only, keep a concise durable statement of starting state, intended result, prohibited workaround, failure/recovery behavior, and acceptance evidence. Do not pre-create six Product Contracts. Do not add dependencies, leases, scheduling, dashboards, or another database to the contract.

**Behavioral proof required:** at least one real implementation must remain incomplete when its local PR/tests are green but the user outcome still fails. If the contract does not change a real completion decision, simplify or delete it.

### B. Evidence classes that cannot be confused

Mirror the evidence vocabulary in the meta-audit rather than creating a parallel taxonomy. Use these distinct names:

- **mechanical/component proof** — unit/static/component behavior;
- **hermetic integration proof** — assembled components with controlled dependencies or route stubs;
- **exact-candidate isolated proof** — the real candidate stack against isolated owner-like data;
- **canonical dogfood proof** — the actual running Kitty and real user workflow.

Live-provider proof is an additional property when the outcome inherently depends on a provider. Canonical proof is required only where the claimed outcome needs it; it is not a per-PR ritual.

### C. Test-data isolation

Make `KITTY_ENV`, `KITTY_TEST_GUARD`, and `KITTY_DATA_ROOT` load-bearing. Automated test/acceptance runs must use an explicit noncanonical data root. Do not infer test mode from filenames, `sys.argv`, or `PYTEST_CURRENT_TEST`. Before cleaning existing canonical records, back up and classify them; prefer reversible archive/quarantine over deletion.

**Behavioral proof required:** a deliberately misconfigured acceptance run must fail before it can write canonical owner data.

### D. Builder validation parity

Investigate the simplest way for isolated Builder worktrees to validate the frontend as well as Python. The current `node_modules` gap is a mechanical cause of horizontal packet splitting. Prefer a reproducible/shared dependency approach before inventing a validation service or changing package managers.

**Kill trigger:** if the simplest parity approach costs more operationally than CI-only validation and does not improve vertical delivery, keep CI-only validation and strengthen parent-outcome acceptance instead.

### E. Initiative without lane theft

Preserve proactive discovery. Agents may inspect and root-cause adjacent problems, but mutation/activation stays under explicit ownership. Use existing `next` + multi-agent coordination authorities; do not build an idea-management subsystem. The load-bearing wording belongs in `.agents/skills/next/SKILL.md` and `docs/reference/MULTI_AGENT_COORDINATION.md`, not in this candidate inventory.

### F. Review and cost discipline

Run deterministic evidence before model review. Cache review by exact unchanged SHA. Do not pay for repeated independent reviews when no implementation/evidence changed. Stop when reviewers converge, the remaining question is empirical, or a provider/credit boundary is reached.

### G. One-shot lifecycle reconciliation

Before mutating accumulated Builder/Projects/Library history, produce a read-only classification using supported projections. Preserve useful history. Do not blindly cancel old Builder initiatives or infer personal-record deletion from age/name alone.

## What is explicitly rejected

- a second task/claims database;
- six Product Contracts written up front;
- a Product Contract dashboard/service;
- calendar-based CI failures or weekly reconciliation ceremonies;
- rewriting Rust/Go/SwiftUI/React Native/Tauri to solve workflow problems;
- treating persistence diversity itself as a defect;
- broad API/type migration before an active product loop requires it;
- a multi-week "governance first" pause before product repair.

## Falsifier

After the first repaired user outcome, every new process rule must answer: **what real failure did this prevent, and what attention did it cost?** Rules that do not materially prevent premature completion, collision, data contamination, or repeated manual checking are removed or simplified.
