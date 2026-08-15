# Design: Autonomous Campaign Supervisor v3 Walking Skeleton

## Goal

Deliver the complete autonomous supervisor walking skeleton as one coherent Builder packet because current packet dependencies gate eligibility but do not carry implementation branches forward.

## Evidence

The v1 Mission proved two runtime gaps: clean worktrees do not inherit the root Python environment, and a worktree symlink is rejected as dirty. The v2 review also confirmed `gateway/builder_run.py:420-480` invokes each packet through its own task/worktree and `gateway/builder_runner.py:182-270` binds each worktree to its base; `depends_on` does not create a branch handoff. Therefore separate dependent implementation packets would create isolated, non-integrable branches.

## Decision

Use one bounded walking-skeleton packet. It owns runtime preflight, supervisor/CLI/launchd wiring, Claude adapter, tests, and operations documentation in one branch. This sacrifices packet-level parallelism for an integrable result under the current Builder contract. Builder remains the durable authority; no new queue, state database, event bus, or Discord control plane is added.

## Runtime contract

Follow `scripts/kittybuilder_opencode_worker.sh:1-60` and `gateway/builder_attempt.py:933-1030`. Propagate the existing repository runtime through child `PATH` when present; use portable `python3.12 -m`/`python -m` validation commands as appropriate; never install dependencies, create worktree files, or weaken clean-tree checks. Missing runtime fails loudly.

## Acceptance evidence

One Builder branch contains the complete reviewed walking skeleton. A clean worktree executes worker and validation commands without setup files or package downloads; duplicate supervisor ticks are no-ops; at most two canonical initiative runs launch; Claude worker/reviewer contracts are fake-tested; docs preserve Builder authority and manual publication. No service is installed and no PR is pushed or merged automatically.
