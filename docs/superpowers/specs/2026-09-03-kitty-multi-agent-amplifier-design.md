# Kitty Multi-Agent Amplifier Design

## Purpose
Kitty needs two separate capabilities: a Coordination Kernel that prevents conflicting mutation, and a Collective Intelligence Engine that turns safe parallelism into review, research, critique, synthesis, and durable learning. This design preserves Git/GitHub as publication truth, KittyBuilder as engineering execution authority, and `workspace_global` as communication truth.

## Coordination Kernel
Every supported mutating agent session must hold a live claim recording participant, session, role, lane, base SHA, branch, worktree, path fence, semantic resources, and lease expiry. `OWN` and `INTEGRATE` are mutating roles. `REVIEW` and `RESEARCH` are read-only roles and do not exclude one another.

Claims are acquired with a SQLite `BEGIN IMMEDIATE` transaction. A mutating claim conflicts with another live mutating claim when their normalized repo-relative paths overlap by ancestry or when they name the same semantic resource. The transaction is the ownership mutex; GAR and issue #490 are projections, not locks.

The mutation guard resolves the current worktree to its live claim and refuses staged paths outside that claim. A supported commit therefore fails closed when no valid mutation claim exists, when the lease expired, or when any staged path is outside scope. Canonical-checkout mutation can later be restricted to `INTEGRATE`; that policy is not required for the first proof.

The kernel must not become a task queue. It never selects work, changes Builder task states, or decides product priority. Builder ownership is read and projected into the same collision view; Builder remains authoritative for Builder work.

GAR projection posts meaningful lifecycle events: claim acquired, conflict, release, and transfer/recovery where applicable. Heartbeats renew silently to avoid room noise.

## Collective Intelligence Engine
After safety is proven, Kitty can add typed intellectual artifacts (`QUESTION`, `HYPOTHESIS`, `FINDING`, `PROPOSAL`, `REVIEW`, `EXPERIMENT`, `LEARNING`, `DECISION_REQUEST`), blind independent exploration, cross-model review, research swarms, patch/diagnosis tournaments, a discovery market, and a Process Scientist that proposes bounded workflow improvements from repeated failures.

Independent reasoning should precede collaboration for high-value ambiguous work. The default sequence is independent hypotheses -> evidence -> critique -> rebuttal -> synthesis. Agents should not continuously ingest every other agent's full context because premature sharing can destroy useful diversity.

## First Milestone
The first reviewable deliverable proves only the safety primitive:

1. two independent mutating sessions cannot both acquire overlapping semantic or path ownership;
2. read-only review/research sessions can coexist;
3. expired claims stop authorizing mutation;
4. a staged path outside the winning claim is rejected;
5. claim lifecycle is visible through a machine-readable CLI;
6. meaningful claim lifecycle events can be projected to GAR;
7. no Builder task state, roadmap packet, or amplifier scheduler is activated.

## Non-goals
Do not replace Builder, create another general queue, silently spend provider credits, autonomously schedule swarms, merge this milestone without review, or require all agents to read all peer context.
