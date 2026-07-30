# KTF Daylight Evidence v2 — Unified Capture

daylight-evidence-v2: captured
inspected-head: fbd69242cd7cd5437d8d65b09ad6dc9b287d5f8f
captured-at: 2026-07-30T16:23:40Z

## Runtime Contract Verification

ktf-runtime-on-main: passed
  - git merge-base --is-ancestor f9dfb6a HEAD: exit 0 (ancestor verified)

builder-doctor:
  ok: true
  pass: 13
  warn: 1
  fail: 0
  details:
    - queue:kill_switch: enabled (PASS)
    - db:open: builder_queue.db (PASS)
    - db:integrity_check: ok (PASS)
    - initiative:pause_state: no initiatives (PASS)
    - repo:identity: worker worktree; origin=kitty (PASS)
    - repo:default_branch: main (PASS)
    - tool:bash, git, false: all present (PASS)
    - runs:stale_leases: no expired leases (PASS)
    - runs:active: no active runs (PASS)
    - github:boundary: gh available (PASS)
    - runner:credential_isolation: 9 vars blocked (PASS)
    - worktree:root: does not exist yet — created on first run (WARN)

## DP-01 Worktree Evidence

dp01-worktree-evidence: present
dp01-worktree-path: kb_ms7ps19u_1f33
dp01-worktree-head: 817fbde

dp01-verification-content:
```
daylight-prerequisite-verification: passed
ktf-rp-01-report: present
ktf-rp-02-brief: present
builder-doctor: pass
inspected-head: fbd69242cd7cd5437d8d65b09ad6dc9b287d5f8f
prerequisites-verified-at: 2026-07-30T16:15:21Z
```

## Initiative Status

ktf-004-daylight-proof-v1-status: not_found (initiative not registered in builder)
ktf-004-daylight-evidence-v2-status: not_found (initiative not registered in builder)

Note: Both initiatives exist as packet/orchestration concepts but are not
registered as formal Builder initiatives. Evidence capture proceeds as a
free-exec packet.

## Queue Status

queue-status:
  active: 0
  queued: 0

## Git Snapshot

git-log:
  - fbd6924 docs(brain): authorize KB-BRAIN-05 operator controls
  - 5b4823a fix(builder): restore cockpit navigation
  - 2aaa5cb feat(builder): add cockpit operator controls
  - a3c2fc6 Merge pull request #300 from jacob202/docs/repository-navigation-refresh
  - 3f64cd7 fix(continuity): repair STATE.md blocked_by null for ready kb-brain-05, align head_sha
