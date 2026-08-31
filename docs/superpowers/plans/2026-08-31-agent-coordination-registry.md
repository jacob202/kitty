# Agent Coordination Registry — Implementation Plan

Base: `ba13cb194ecb3d725c9ea525e38febd39d44d495`
Branch: `feat/agent-coordination-registry-20260831`

## Task 1 — Protocol parser and validation

Tests first in `tests/test_agent_coordination.py`:

- parse v1 hidden JSON markers from issue comments;
- reject malformed schema, timestamps, statuses, paths, and overlong leases;
- collapse append-only events to current lane state;
- classify active vs stale vs terminal lanes.

Implementation: pure functions in `scripts/agent_coordination.py`.

## Task 2 — Deterministic collision engine

Tests first:

- exact path collision;
- subtree `/**` collision;
- sibling paths remain independent;
- stale/released claims do not block;
- earliest active owner wins when two overlapping claims exist;
- open-PR and unpublished-worktree files are conservative collision evidence.

## Task 3 — Evidence adapters and survey

Tests first around command-output parsers. Production adapters then read:

- #490 comments via `gh api`;
- open PR metadata/files via `gh pr list/view`;
- local worktrees via `git worktree list --porcelain` and `git diff`;
- Builder via the existing read-only `builder_status` projection when its DB
  exists in the canonical common-dir checkout.

All unavailable sources become explicit evidence gaps.

## Task 4 — Safe mutation commands

Tests first with an injected command runner:

- claim refuses any blocking collision;
- claim refuses UNKNOWN GitHub state unless explicitly dry-run;
- refresh requires current ownership;
- release preserves history;
- generated events are canonical JSON and include exact branch/worktree/base.

No GitHub write occurs in unit tests.

## Task 5 — Documentation and dogfood

- update `docs/reference/MULTI_AGENT_COORDINATION.md` to make v1 structured
  events the preferred interactive marker while keeping legacy prose readable;
- run the new survey against the actual current repository and #490;
- publish this lane itself using the new event format;
- verify it sees #705/#707/#709 and the existing worktrees without falsely
  claiming Builder has active work when its read-only queue says zero running.
