# Handoff — Free-Worker Initiative Queue, Ready to Launch

<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-18T00:38:31Z",
  "head_sha": "41a18b44bc92d3a259caa4df8e7104297c9c8daf",
  "branch": "claude/kitty-test-hardening-0j2yn0",
  "worktree": ".",
  "status": "valid",
  "completed_items": [
    "authored and applied builder-test-hardening-v1 (3 packets), chat-recovery-v1 (7), reasoning-backend-v1 (3)",
    "repaired packet-027-v1.json to today's manifest schema and applied it (5 packets)",
    "proved the free ladder is unreachable from the remote container (egress proxy 403s opencode.ai/models.dev/openrouter.ai) with evidence under data/kittybuilder/attempts/kb_mrpmm5qy_e78a/"
  ],
  "blockers": [
    "free-worker execution requires a host that can reach the free endpoints - run from the Mac, not a remote Claude container with default network policy"
  ],
  "next_action": "On the Mac: apply the four manifests, launch TH-01 then TH-02 with --free --watch, review final diffs, operator-gated publish",
  "invalidation_conditions": [
    "HEAD changes outside one checkpoint-only commit",
    "the branch or registered worktree changes",
    "a fetch changes origin/main",
    "any of the four initiative manifests under docs/initiatives/ changes",
    "a pull request is opened or changes state"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Resume here

Everything paid is done: the work queue from docs/plans/pr164-archaeology.md §6
is fully authored as validated initiative manifests. What remains is launching
free workers from a host that can reach the free endpoints, then reviewing
final diffs. No packet has produced a reviewable diff yet - nothing is claimed,
nothing is in publish.

## Launch order (on the Mac, canonical checkout)

```bash
./kitty builder initiative apply docs/initiatives/builder-test-hardening-v1.json
./kitty builder initiative apply docs/initiatives/packet-027-v1.json
./kitty builder initiative apply docs/initiatives/chat-recovery-v1.json
./kitty builder initiative apply docs/initiatives/reasoning-backend-v1.json

# 1. Standalone chores first (no feature risk)
./kitty builder initiative run-packet builder-test-hardening-v1 TH-01-fail-loud-sweep --free --watch
./kitty builder initiative run-packet builder-test-hardening-v1 TH-02-route-contract-tests --free --watch
# TH-03-ci-ratchet: DO NOT run until TH-02 is published AND merged to main.

# 2. Builder reliability
./kitty builder initiative run packet-027-builder-restart-recovery --free --watch

# 3. Chat recovery (each packet = one PR; CR-02/05/06 depend on earlier packets)
./kitty builder initiative run chat-recovery-v1 --free --watch

# 4. Reasoning engine backend
./kitty builder initiative run reasoning-backend-v1 --free --watch
```

Per-packet loop: on success read ONLY the final diff, then operator-gated
publish (draft PR). On failure read the attempt evidence, refine the packet
once, re-run. ADR 0016: if any life-first initiative is queued, it outranks
all of this.

## What happened in the remote container (2026-07-18)

- TH-01 ran twice on `--free`; every ladder model failed identically:
  the container egress proxy answers 403 CONNECT for opencode.ai,
  models.dev, and openrouter.ai (network policy, not auth). No model ever
  executed; no worktree was touched. Evidence:
  `data/kittybuilder/attempts/kb_mrpmm5qy_e78a/{1,2}/run-manifest.json` and
  `data/kittybuilder/runs/run_mrpmqaj1_2c64/combined.log` (container-local,
  gitignored - re-applying manifests on the Mac starts clean).
- Those two burned attempts are exactly the counts_toward_budget
  infrastructure-crash case P027-stale-attempt-reconciliation addresses.
- packet-027-v1.json on disk predated the manifest schema (forbidden_paths,
  forbidden_paths_note, policy.attempt_3_authorization are unknown keys and
  fail validation). Fixed by folding that intent into the objective text;
  the file now validates and applies cleanly.

## Decisions already encoded in the manifests (don't re-litigate)

- Goal sidebar (R9) is parked - deliberately absent from chat-recovery-v1.
- Thread-goals migration allocates the next free number verified at
  implementation time (highest today: 019_idea_mine.sql → expect 020).
- 028 Parts A/B (UI, needs live browser verify) are NOT in
  reasoning-backend-v1 - human/UI pass later.
- TH-03 sets --cov-fail-under to a measured number minus 3, never a guess,
  and un-ignores the two council tests only with passing evidence.
