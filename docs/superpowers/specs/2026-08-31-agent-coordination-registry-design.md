# Kitty Agent Coordination Registry — Design

Date: 2026-08-31

## Goal

Turn GitHub issue #490 from a human-only comment stream into a durable,
machine-readable coordination surface for interactive coding agents without
creating a second execution queue or replacing KittyBuilder authority.

## Research synthesis

Recent open-source agent coordination systems converge on a small set of useful
primitives: one owner per task, scoped path/file claims, expiring leases,
worktree isolation, stale-session detection, collision checks, structured
handoffs, and a queryable live registry. Concord, Keel, ATC, Agent Collab,
Agentlocks, Pact, Onetree, and pi-ensemble all implement variants of these.

Kitty already has Builder leases, worktrees, evidence gates, PR checks, and a
coordination issue. The missing layer is deterministic discovery and enforcement
for interactive ChatGPT/Codex/Claude/OpenCode lanes.

## Authority boundary

- KittyBuilder remains authoritative for Builder initiative/task/attempt/lease
  and worker execution state.
- GitHub issue #490 remains authoritative for interactive lane claims.
- The coordination registry derives projections from existing GitHub, git, and
  Builder evidence. It does not own execution state.
- No new database, daemon, scheduler, queue, or background agent is introduced.

## Registry protocol

Structured issue comments use a hidden `kitty-lane:v1` marker containing JSON.
Each event records a stable `lane_id`, event type, owner, base/head identity,
branch/worktree/output, repo-relative path claims, status, lease expiry, host,
and timestamp. Events are append-only; current lane state is the newest valid
event for that lane.

Interactive mutable states are `own`, `review`, `integrate`, and `dependency`.
Terminal states are `released` and `complete`. Only `own` claims block another
interactive implementation lane.

Path claims are intentionally simple: exact repo-relative paths plus `/**`
subtree claims. Absolute paths, parent traversal, empty paths, and arbitrary
glob syntax are rejected so overlap is deterministic.

## Collision model

Before an `own` claim is published, the CLI checks:

1. active unexpired structured #490 claims;
2. changed files in open pull requests;
3. unpublished local worktrees whose branch differs from current `origin/main`;
4. Builder read-only summary so active Builder execution is never silently
   reported as an empty plane.

A collision is evidence, not an automatic deletion/reassignment. Expired claims
are marked stale and require preservation/reclamation checks before reuse.

## CLI

`scripts/agent_coordination.py` provides:

- `survey` — JSON or Markdown live board with claims, PRs, worktrees, Builder
  summary, collisions, stale claims, and evidence gaps;
- `claim` — validate scope, reject collisions, and optionally publish a v1 event;
- `refresh` — extend the lease for an existing owned lane;
- `release` — publish a terminal event without deleting history;
- `validate-comment` — validate one machine-readable event for CI/tooling.

GitHub mutations use the existing authenticated `gh` CLI. Read failures remain
UNKNOWN/UNAVAILABLE rather than being converted into an empty green result.
