# Campaign: kitty-campaign-cli

**Goal:** Wire 'campaign' into the ./kitty launcher so the harness is reachable without venv paths
**Branch:** fix/reconcile-run-finalize-and-status-20260817

A phase is `verified` only when `scripts/campaign.py verify` ran its
command to a pass AND recorded the commit below. Never hand-edit a
status to `verified`; `audit` will catch it.

## Phases

| # | Phase | Status | Verify command | Commit |
|---|-------|--------|----------------|--------|
| 1 | launcher dispatch | verified | `venv/bin/python3.12 -m pytest tests/test_campaign_cli.py -q` | d9dc5b0f |
| 2 | ledger tests still green | verified | `venv/bin/python3.12 -m pytest tests/test_campaign_ledger.py -q` | 465cc8c1 |
| 3 | launcher suite gate | verified | `venv/bin/python3.12 -m pytest tests/test_kitty_launcher.py tests/test_campaign_cli.py tests/test_campaign_ledger.py -q` | 040926e9 |

## Handoff

_Written by `campaign.py handoff` at 40cb8951._

**Single next action:** none, campaign complete

**Branches**

```
archive/prewipe-character-curation-wip-20260817 
archive/prewipe-local-git-state-20260817 
audit/builder-simplification-20260817 
audit/kittybuilder-real-agent-smoke-2026-08-01 [ahead 1]
audit/loose-thread-closure-20260817 
audit/test-builder-reliability-20260817 
audit/test-frontend-trust-20260817 
audit/test-gap-map-20260817 
audit/test-harness-isolation-20260817 
audit/test-knowledge-memory-20260817 
audit/test-trust-20260817 
heads/backup/gateway-packages-2026-07-25 
backup/openwebui-local-20260802-123047 
campaign/ci-parity 
campaign/production-paths 
campaign/production-runtime 
campaign/public-golden-path [ahead 1, behind 92]
campaign/readiness [ahead 1, behind 92]
chatgpt/b5-autonomy-20260817 [behind 21]
chatgpt/builder-cheap-packets-20260816 [gone]
chatgpt/interrupted-reconcile-local [gone]
chatgpt/pr508-update-20260817 [gone]
ci/product-acceptance-gate 
cleanup/slice-0c 
closer/KTL2-003-final 
codex/continuationOfJuly25 
contract-first 
design/gateway-work-spine-v1 [ahead 2, behind 124]
docs/architecture-ratification-governance [gone]
docs/kittybuilder-core-runtime-audit-2026-08-01 [ahead 1]
docs/ktf-001-resume-plan [gone]
docs/repository-navigation-refresh [gone]
draft/console-work-v2-deterministic 
feat/agent-council-relay 
feat/backup-restore-proof-2026-08-02 
feat/builder-action-retirement [gone]
feat/builder-queue-doctor 
feat/campaign-work-projection-v1 [ahead 2, behind 124]
feat/character-locked-proof-20260816 [behind 48]
feat/chat-ux-harvest-slice 
feat/console-work-v1 
feat/discord-command-center-phase0 [gone]
feat/discord-command-center-phase1 [gone]
feat/discord-command-center-phase2 [gone]
feat/discord-command-center-phase3 [gone]
feat/image-studio-james [behind 5]
feat/kittybuilder-brain-initiatives [behind 1]
feat/kittybuilder-mcp-v2-dogfood [gone]
feat/kittybuilder-reviewer-pro 
feat/openwebui-tomorrow-ready [behind 2]
feat/shared-agent-workspace-v1 [gone]
feat/work-spine-console-v1 [ahead 5, behind 116]
feat/workflow-hardening-20260815 [ahead 9, behind 95]
feat/workflow-hardening-final 
fix/acceptance-gate-loophole 
fix/b5-cheap-model-value-refresh-e6ddbaf [ahead 4, behind 1]
fix/builder-canonical-db [ahead 21, behind 172]
fix/builder-core-runtime-followup-2026-08-01 
fix/builder-identity-scope-source 
fix/builder-ignore-omo-artifacts 
fix/builder-publish-hook-env-isolation [ahead 1, behind 134]
fix/builder-publish-process-reap [ahead 1, behind 142]
fix/builder-publish-ready-state [ahead 1, behind 132]
fix/builder-runtime-data-root-20260817 
fix/builder-runtime-root-integration-20260817 
fix/builder-sanitize-branch [ahead 2, behind 189]
fix/builder-sanitize-branch-slash [ahead 8, behind 189]
fix/chat-hermetic-gateway-seam-20260817 [ahead 4]
fix/chat-truthful-recovery-slice 
fix/dogfood-provider-chat-shell-2026-07-28 
fix/frontend-trust-integration-20260817 [ahead 1]
fix/kittybuilder-publish-draft-pr 
fix/knowledge-memory-trust-integration-20260817 [ahead 2]
fix/ktl2-003-corrective-resolver-exercise 
fix/life-first-home-truth [gone]
fix/local-gate-baseline 
fix/memory-namespace-integrity-20260817 
fix/mission-routing-tool-server [ahead 1, behind 180]
fix/opencode-runtime-python-20260817 
fix/opencode-worker-stdin [ahead 1, behind 148]
fix/p0-airforce-aspect-ratio-20260817 [ahead 1]
fix/p0-backup-owner-data-20260817 [gone]
fix/p0-image-spend-ledger-20260817 [gone]
fix/p0-reviewed-sha-publish-20260817 
fix/p0-test-egress-deny-20260817 [gone]
fix/pr450-review-fixes [gone]
fix/pr458-continuity [ahead 23, behind 10]
fix/pr500-post-review-findings 
fix/prepush-hook-contract-regression-20260817 [ahead 1, behind 17]
fix/reconcile-run-finalize-and-status-20260817 [ahead 8]
fix/repairs-dismiss-signal-truthful [gone]
fix/review-gate-hardening-20260816 [ahead 1]
fix/reviewed-sha-publish-integration-20260817 [ahead 1]
fix/runware-pulid-input-images-20260817 [gone]
fix/supervisor-review-final 
fix/supervisor-review-findings-final [gone]
fix/test-gate-provenance-20260817 [ahead 1]
fix/test-trust-convergence-20260817 [ahead 10]
fix/trust-harness-auth 
fix/ux-trust-reset-slice-1 [behind 110]
fix/version-runtime-override [ahead 1, behind 124]
fix/work-hide-builder-machinery [ahead 2, behind 373]
hardening-sweep 
jacob202/builder-trust-repair 
jacob202/fix-description [ahead 1]
kittybuilder/kb_clean 
kittybuilder/kb_mry6m72e_9009 
kittybuilder/kb_mry6m73s_7050 
kittybuilder/kb_ms2eqymk_3e6c 
kittybuilder/kb_ms3rbu41_d782 
kittybuilder/kb_ms7ps19u_1f33 
kittybuilder/kb_msau8lll_4e3d 
kittybuilder/kb_msauan2z_473e 
kittybuilder/kb_msauc86k_6fc7 
kittybuilder/kb_msauh547_f065 
kittybuilder/kb_msauixxe_939f 
kittybuilder/kb_msaumzv4_bfae 
kittybuilder/kb_msaux1t9_e46f 
kittybuilder/kb_msav3d1s_3e6a 
kittybuilder/kb_msav48iz_c2bd 
kittybuilder/kb_msazu581_72ec 
kittybuilder/kb_msb4yx3l_caea 
kittybuilder/kb_msnx6fsm_6a42 
kittybuilder/kb_msny8g6i_1fbe 
kittybuilder/kb_msnydsom_fb4f 
kittybuilder/kb_msnz6hfw_fdba 
kittybuilder/kb_mso32b8k_3fec 
kittybuilder/kb_msog05jp_812f 
kittybuilder/kb_msogtkej_0791 
kittybuilder/kb_msplzy3g_9078 
kittybuilder/kb_mspn71i7_3680 
kittybuilder/kb_msru11zy_278f 
kittybuilder/kb_msrukojn_e66a 
kittybuilder/kb_msrvbwy7_6e63 
kittybuilder/kb_msrvynzs_2377 
kittybuilder/kb_msrw1xqw_a229 
kittybuilder/kb_msrwbr54_4463 
kittybuilder/kb_msrwwzx6_9828 
kittybuilder/kb_msrywbye_24cf 
kittybuilder/kb_msrzrsbn_19a5 
kittybuilder/kb_mss0fbka_530c 
kittybuilder/kb_mss0qpz0_1208 
kittybuilder/kb_mss0ri22_96e9 
kittybuilder/kb_mss1aor3_9859 
kittybuilder/kb_mss1npup_a28e 
kittybuilder/kb_mss2ogml_5613 
kittybuilder/kb_mstyw34s_2249 [gone]
kittybuilder/kb_msudvnes_9eaa 
kittybuilder/kb_mswr6l0k_9f3c 
kittybuilder/kb_mswri4p6_3bd5 
kittybuilder/kb_msww7xv3_9a3d [gone]
kittybuilder/kb_msxdik9h_317a 
kittybuilder/kb_test 
kproof/retry-fixed-base-0175488d 
main [behind 95]
mcp/planning/design-autonomous-campaign-supervisor-6e49a4e1-b94058be 
mcp/planning/design-autonomous-campaign-supervisor-rebase-8bd732f3-da52b4d7 
mcp/planning/design-autonomous-campaign-supervisor-v2-8bd732f3-87440292 
mcp/planning/design-autonomous-campaign-supervisor-v3-8bd732f3-cace5046 
mcp/planning/design-kproof-retry-this-work-68687b50-cbfc0b01 
mcp/planning/design-kproof-retry-this-work-6de35bde-2cc58b5a 
mcp/planning/plan-autonomous-campaign-supervisor-77d1eb17-dc9a398d 
mcp/planning/plan-autonomous-campaign-supervisor-rebase-da0f210f-6a9f8eb2 
mcp/planning/plan-autonomous-campaign-supervisor-v2-a9a51d15-450268a7 
mcp/planning/plan-autonomous-campaign-supervisor-v3-3bebe741-08bc9441 
mcp/planning/plan-kproof-retry-this-work-203a5e29-461b5547 
mcp/planning/plan-kproof-retry-this-work-d96e0181-04c31e5e 
mcp/planning/plan-kproof-retry-this-work-d96e0181-111cb244 
pr355-review 
proof/kproof-final-control [ahead 2, behind 173]
proof/live-current-20260804-212614 [ahead 4, behind 245]
recovery/open-session-audit-2026-08-01 [ahead 1, behind 383]
research/architecture-migration-analysis-cec062f 
research/chat-ux-harvest-2026-08-01 [ahead 1, behind 373]
research/mature-product-2026-07-25 
salvage/archive-hygiene-review-20260817 [behind 17]
salvage/builder-db-context-managers-20260817 
salvage/character-reference-curation-20260817 
salvage/final-archive-triage-20260817 [behind 17]
salvage/frontend-keyboard-accessibility-20260817 
salvage/frontend-skip-link-20260817 
salvage/make-ci-hygiene-parity-20260817 
salvage/mcp-diagnostics-proof-review-20260817 
salvage/offline-openapi-types-20260817 
salvage/openapi-contract-pipeline-20260817 
salvage/opencode-worker-stdin-20260817 
salvage/production-runtime-hardening-20260817 
salvage/publish-draft-ready-20260817 
salvage/publish-env-isolation-20260817 
salvage/runtime-version-override-20260817 
salvage/stash-review-2-20260817 [behind 17]
salvage/stash-review-20260817 [behind 17]
salvage/supervisor-merge-reconcile-20260817 
salvage/worker-sanitize-scope-20260817 
spike/chat-reuse-trust-slice 
heads/threadmaster/pr474-fix 
worktree-pr509-integration-20260817 
worktree-pr513-integration-20260817 [gone]
```

**Worktrees**

```
/Users/jacobbrizinski/Projects/kitty                                                    40cb8951 [fix/reconcile-run-finalize-and-status-20260817]
/Users/jacobbrizinski/orca/workspaces/kitty/kproof-sanitize-fix                         ba679485 [fix/builder-sanitize-branch-slash]
/Users/jacobbrizinski/orca/workspaces/kitty/p0-airforce-aspect-ratio                    f2b06584 [fix/p0-airforce-aspect-ratio-20260817]
/Users/jacobbrizinski/orca/workspaces/kitty/pr450-fix                                   89dc2966 [fix/pr450-review-fixes]
/Users/jacobbrizinski/orca/workspaces/kitty/test-trust-convergence                      eede7a3c [fix/test-trust-convergence-20260817]
/Users/jacobbrizinski/Projects/kitty/.claude/worktrees/fix-builder-ignore-omo-artifacts ec54d9b6 [fix/builder-ignore-omo-artifacts]
/Users/jacobbrizinski/Projects/kitty/.worktrees/pr458-continuity                        d21dadf2 [fix/pr458-continuity]
```

**Running processes**

```
1224 /opt/homebrew/Cellar/python@3.12/3.12.13/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python /Users/jacobbrizinski/Projects/kitty/venv/bin/uvicorn gateway.app:app --host 127.0.0.1 --port 8000
 1232 /bin/bash /Users/jacobbrizinski/Projects/kitty/gateway/start_litellm.sh
 1242 /opt/homebrew/Cellar/python@3.11/3.11.15_1/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python /Users/jacobbrizinski/kitty-services/openwebui/venv-0.10.2/bin/open-webui serve --host 127.0.0.1 --port 3000
 1329 next-server (v16.2.6)          
 1434 /opt/homebrew/Cellar/python@3.12/3.12.13/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python /Users/jacobbrizinski/kitty-services/venv-litellm/bin/litellm --config /Users/jacobbrizinski/Projects/kitty/gateway/litellm_config.yaml --port 8001 --host 127.0.0.1
46846 /bin/zsh -c source /Users/jacobbrizinski/.claude/shell-snapshots/snapshot-zsh-1786983448445-lmcfvr.sh 2>/dev/null || true && setopt NO_EXTENDED_GLOB NO_BARE_GLOB_QUAL 2>/dev/null || true && { \builtin unalias -- 'unsetenv'; \builtin unset -f -- 'unsetenv'; } >/dev/null 2>&1 || true && eval 'cd ~/Projects/kitty\012> /tmp/kitty-push-results.txt\012while read -r branch; do\012  b="${branch#heads/}"\012  out=$(timeout 30 git push --no-verify -u origin "refs/heads/${b}:refs/heads/${b}" 2>&1)\012  status=$?\012  echo "$status | $b | $(echo "$out" | tail -1)" >> /tmp/kitty-push-results.txt\012done < /tmp/kitty-push-list2.txt\012echo "loop done"\012wc -l /tmp/kitty-push-results.txt\012echo "=== status summary ==="\012awk -F'"'"' \\| '"'"' '"'"'{print $1}'"'"' /tmp/kitty-push-results.txt | sort | uniq -c\012' && pwd -P >| /tmp/claude-a707-cwd
65222 /bin/zsh -c source /Users/jacobbrizinski/.claude/shell-snapshots/snapshot-zsh-1786998488736-qb6jw4.sh 2>/dev/null || true && setopt NO_EXTENDED_GLOB NO_BARE_GLOB_QUAL 2>/dev/null || true && { \builtin unalias -- 'unsetenv'; \builtin unset -f -- 'unsetenv'; } >/dev/null 2>&1 || true && eval 'echo "=== audit ==="; ./kitty campaign --slug kitty-campaign-cli audit; echo "rc=$?"\012echo; echo "=== resume on a clean, honest ledger ==="; ./kitty campaign --slug kitty-campaign-cli resume; echo "rc=$?"\012echo; echo "=== handoff ==="; ./kitty campaign --slug kitty-campaign-cli handoff' < /dev/null && pwd -P >| /tmp/claude-f6e2-cwd
66127 bash ./kitty campaign --slug kitty-campaign-cli handoff
```

