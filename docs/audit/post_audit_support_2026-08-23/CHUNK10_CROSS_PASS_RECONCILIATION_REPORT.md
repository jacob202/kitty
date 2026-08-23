# CHUNK 10 — CROSS-PASS RECONCILIATION REPORT

Date: 2026-08-23
Mode: STRICT READ-ONLY RECONCILIATION. No implementation. No authoritative Chunk 11 work is part of this report.
Repository: `jacob202/kitty`
Current `origin/main`: `95d62c5dabfa33ce36d52ff48c2c50393417a319`

## 1. Prerequisite and current truth

`CHUNK9_HANDOFF.md` exists and explicitly states `CHUNK9_STATE: COMPLETE`; Chunk 10 therefore proceeded without reconstructing Chunk 9.

All durable Chunk 0–9 reports/available handoffs and the full PR #600 companion package were read. The companion package was used as reconciliation/coverage infrastructure only; repository, runtime, GitHub and accepted architecture evidence remained authoritative.

Final reconciliation refresh before report drafting:
- `origin/main` = `95d62c5dabfa33ce36d52ff48c2c50393417a319`.
- Project↔Builder linkage remains IN FLIGHT as open PR #619, `feat/project-resume-work-linkage-20260823`, current head `0bdfb3a9e185f0ce25ba21fc0fe3be17a2b56ddc`. Its follow-up now tolerates partial Project Resume responses that omit `work`; pytest/lint/typecheck/kitty-chat/browser-smoke/merge-gate evidence is green on that head. It is still not authoritative main until merged.
- **PR #620 MERGED** as `95d62c5dabfa33ce36d52ff48c2c50393417a319`; issue #552 is CLOSED. Current main now adds governed explicit memory/project projection, removes `WeaveAdapter` from default fan-in, keeps semantic Mem0 optional, and preserves the broader MemoryGraph fan-in architecture. C4-08 and C9-F07 are therefore FIXED SINCE AUDIT. The local memory worktree remains only as a clean historical checkout of the merged head and is no longer implementation authority.
- Open PRs at final reconciliation: **#619, #618 (draft), #617, #616, #600**. Issue #490's current five-PR header matches that set after #620 merged; GitHub remains authoritative if it drifts again.
- The shared checkout currently has unrelated dirty `scripts/pr_policy.py` / `scripts/pr_scope.py` from an interrupted merge-queue/`merge_group` experiment. They are not #619 work and were preserved at `/Users/jacobbrizinnski/Kitty-Control-Center/recovery/uncommitted-merge-queue-20260823.patch` with verified SHA-256 `9806c90f4df8e28a6dcc03adbf278a9266b77a1cacb1ba3ea1574e4d504c836c`. The experiment is neither implemented nor accepted.
- Issue #592 is CLOSED and PR #609 is merged; autonomy restart finding is fixed on current main.
- PR #615 is merged; the Chunk 8 clock-flake finding is fixed.
- #542/#544 remain open even though PR #593 already removed the legacy task execution subsystem.
- PR #619 remains IN FLIGHT at head `0bdfb3a9...`: the earlier `ProjectsPanel.tsx` absent-`work` compatibility failure is now repaired and the current deterministic test/browser/merge evidence is green. #591 remains OPEN and is not fixed until the PR lands.
- PR #617 is not accepted remediation for #610/C9-F03: `AgentPanel.tsx` is not the canonical agent surface, the PR bundles unrelated `config/providers.json` and ImageBench baseline evidence, and its browser seam/merge gate are red. Treat it as mixed dead-surface work pending retain/delete disposition.
- PR #616 owns the 2026-08-23 `.claude/STATE.md`/`.claude/HANDOFF.md` session-continuity checkpoint and has successful required docs evidence. Draft #618 yielded those files to #616; its remaining `docs/session-notes/kb-effectiveness.jsonl` append intentionally shares the same prior chain head. If both survive, **#616 must land first and #618 must regenerate its record against the new chain head; never hand-merge the JSONL**.
- PR #600 remains open and its local worktree is two committed changes ahead of the GitHub PR head (`12c2badc`, `61ead50c`). Those unpublished commits are preserved at `/Users/jacobbrizinnski/Kitty-Control-Center/recovery/pr600-unpushed-audit-commits-20260823.patch`; #600 is not disposable until that evidence and final audit disposition are reconciled.
- `/Users/jacobbrizinnski/Projects/kitty/.worktrees/test-suite-hardening-20260823` is an active protected lane at `a620f03d...`, now behind current main by the merged memory commit and with active dirty `tests/test_resume_script.py` work in addition to its committed hardening plan/spec. Do not duplicate or absorb its test-suite-hardening scope.
- `/Users/jacobbrizinnski/Projects/kitty-automation-550-20260823` is now an active dirty #550 implementation lane at current main, touching `gateway/app.py`, `gateway/cron.py`, `tests/test_app_lifespan_hermetic.py`, and `tests/test_cron.py`. The current diff moves Morning Brief timing under cron, adds stable schedule identity and explicit daily timezone handling. A6-05 is therefore IN FLIGHT; A6-04/A6-08 remain CURRENT VERIFIED because the active patch only addresses part of their broader stale-execution/time semantics. Do not duplicate this lane.
- Current canonical Gateway/UI/LiteLLM were restarted around 06:04–06:05 local from the shared checkout, while old acceptance listeners remain on 18100/18807/18808 and OpenWebUI remains on 3000.
- `data/web_monitors.db` still contains 245 enabled watches over only 4 distinct URLs, preserving A6-02 current evidence.

No source, config, Git state, GitHub state, runtime process, canonical database, provider or automation was mutated.
## 2. Every-finding current disposition

Classification totals across **97 finding IDs**: CURRENT VERIFIED 70; FIXED SINCE AUDIT 7; IN FLIGHT 3; DUPLICATE SYMPTOM 14; DESIGN QUESTION 3; SUPERSEDED 0; STALE / NOT REPRODUCIBLE 0; UNKNOWN 0.

### Chunks 0–2

| Finding | Final classification | Reconciliation note |
|---|---|---|
| COR-001 | CURRENT VERIFIED | freshness diagnostic semantics unchanged since original proof |
| DOC-001 | DUPLICATE SYMPTOM | fold into C9-F01 / RC-01 canonical authority |
| DOC-002 | DUPLICATE SYMPTOM | same authority-document drift root as C9-F01 |
| REL-001 | CURRENT VERIFIED | #537 remains open; owning supervisor path unchanged |
| REL-002 | CURRENT VERIFIED | ActionQueue still has executing claim but no startup external-effect reconciliation |
| AUTH-001 | CURRENT VERIFIED | `/calendar/create` still calls Calendar mutation directly |
| COR-002 | CURRENT VERIFIED | no current-main change to owning approval path established |
| REL-003 | FIXED SINCE AUDIT | PR #609 merged; #592 closed; startup interrupts orphan active autonomy sessions |
| COR-003 | CURRENT VERIFIED | launcher semantics unchanged in current-main delta |
| REL-004 | DESIGN QUESTION | port-owner kill behavior exists; desired ownership semantics still need explicit decision |
| AUTH-002 | CURRENT VERIFIED | `_specificity()` still adds +10 for session grants, allowing broad session allow to outrank narrow deny |
| AUTH-003 | CURRENT VERIFIED | `/imessage/send` still directly invokes sender outside ActionQueue |
| SEC-001 | DUPLICATE SYMPTOM | Builder proof promoted the exploitability into BLD-001 containment root |
| AUTH-004 | CURRENT VERIFIED | `/deploy` remains direct filesystem mutation route |
| COR-004 | CURRENT VERIFIED | `GET /notify/test` still sends external notification |
| PAR-SEC-001 | DUPLICATE SYMPTOM | current capability/MCP convergence root C9-F06/#545 |
| PAR-SEC-002 | DUPLICATE SYMPTOM | current capability/MCP convergence root C9-F06/#545 |
| PAR-SEC-003 | DUPLICATE SYMPTOM | current capability/MCP convergence root C9-F06/#545 |
| PAR-SEC-004 | DUPLICATE SYMPTOM | proprietary plugin trust is part of C9-F06/#545 |
| PAR-SEC-005 | DUPLICATE SYMPTOM | Skill metadata/trust belongs under C9-F06/#545 |
| PAR-SEC-006 | FIXED SINCE AUDIT | archived Skill exposure remains fixed; do not reopen |
### Chunk 3

| Finding | Final classification | Reconciliation note |
|---|---|---|
| BLD-001 | CURRENT VERIFIED | no current-main containment fix; Builder child/proxy boundary remains root-critical |
| BLD-002 | CURRENT VERIFIED | reviewed-SHA-after-rebase seam unchanged on current main |
| BLD-003 | CURRENT VERIFIED | narrow MCP Builder paid-launch defect; coordinate under #545 |
| BLD-004 | CURRENT VERIFIED | recovery/doctor consistency gap remains; no authoritative main fix landed |
| BLD-005 | IN FLIGHT | open PR #619 implements the explicit durable `project_id` direction under #591/#557 |

### Chunk 4

| Finding | Final classification | Reconciliation note |
|---|---|---|
| C4-01 | CURRENT VERIFIED | sensitivity metadata boundary remains current-main defect |
| C4-02 | CURRENT VERIFIED | active Project scope still does not constrain all request-time retrieval |
| C4-03 | CURRENT VERIFIED | 300s unified prefetch cache invalidation defect remains on main |
| C4-04 | CURRENT VERIFIED | whole model-visible system prompt remains outside one enforceable tier budget |
| C4-05 | CURRENT VERIFIED | cross-store budget/ranking + Knowledge score-field mismatch remain |
| C4-06 | CURRENT VERIFIED | context-source degradation still not surfaced on normal answer paths |
| C4-07 | CURRENT VERIFIED | non-stream memory evidence parity remains missing |
| C4-08 | FIXED SINCE AUDIT | merged PR #620 / closed #552 removes `WeaveAdapter` from default fan-in and adds governed explicit memory/project projection |
| C4-09 | CURRENT VERIFIED | Knowledge replacement remains delete-before-success |
| C4-10 | CURRENT VERIFIED | capture still overstates non-failed Knowledge results as ready |
| C4-11 | CURRENT VERIFIED | no current-main rebuildable Artifact↔Knowledge lineage repair landed |
| C4-12 | CURRENT VERIFIED | production `/research/deep` still uses legacy DeepResearcher; #547 owns |
| C4-13 | CURRENT VERIFIED | Research promotion still requires truthful Knowledge status handling under #547 |
| C4-14 | CURRENT VERIFIED | source-URL identity/provenance requirement remains under #547 |
| C4-15 | CURRENT VERIFIED | Research failure/partial lifecycle truth remains under #547 |
| C4-16 | CURRENT VERIFIED | unbounded prefetch/session history behavior remains; PERF-002 is duplicate evidence |
### Chunk 5

| Finding | Final classification | Reconciliation note |
|---|---|---|
| F1 | CURRENT VERIFIED | legacy `/image/generate` still bypasses Studio session spend authority |
| F2 | CURRENT VERIFIED | frontend estimate and batch request bodies still omit `character_id`; backend contract uses it |
| F3 | CURRENT VERIFIED | hosted accepted-but-lost submission recovery remains incomplete; #336 overlaps |
| F4 | CURRENT VERIFIED | session spend still conflates conservative reservation with settled cost after failure |
| F5 | CURRENT VERIFIED | provider-success→artifact-finalization failure still lacks generic same-result recovery |
| F6 | CURRENT VERIFIED | `mcp/imagen` remains a separate paid/retry architecture outside Studio ledger |
| F7 | CURRENT VERIFIED | arbitrary-path direct MCP cloud-reference code remains; live mount remains an acceptance reachability question |
| F8 | CURRENT VERIFIED | cross-session anchor can still be persisted before dispatch rejects it |
| F9 | FIXED SINCE AUDIT | the specific 36-commit-behind Gateway is gone; broader runtime identity weakness remains C9-F09/PERF-003 |

### Chunk 6

| Finding | Final classification | Reconciliation note |
|---|---|---|
| A6-01 | CURRENT VERIFIED | cron still lacks durable occurrence/claim/lease/idempotency identity; #550 owns |
| A6-02 | CURRENT VERIFIED | immutable read rechecked 245 enabled watches / 4 distinct URLs |
| A6-03 | CURRENT VERIFIED | failure/missing-action consumption semantics remain under #550 |
| A6-04 | CURRENT VERIFIED | stale snapshot + reseed ownership semantics remain under #550 |
| A6-05 | IN FLIGHT | active dirty #550 worktree removes the private Brief timer and registers `brief.deliver` under cron; not fixed until reviewed/merged |
| A6-06 | CURRENT VERIFIED | `github.poll` remains sync wrapper registered into always-awaited cron action contract |
| A6-07 | CURRENT VERIFIED | scheduler still has no run-level approval/grant/spend identity; exact policy is a dependency decision |
| A6-08 | CURRENT VERIFIED | generic cron timing still lacks explicit per-trigger timezone semantics |
| A6-09 | CURRENT VERIFIED | persistent keyword-match repeat semantics remain |
| A6-10 | CURRENT VERIFIED | action/execution/signal/notification stages remain fragmented |
| A6-11 | DESIGN QUESTION | automatic deadline watch is not wired; product must decide wire-vs-remove |
| A6-12 | DESIGN QUESTION | no proved canonical machine-restart supervisor owner; host policy decision needed |
| A6-13 | CURRENT VERIFIED | fractional interval projection defect remains low-risk UI truth gap |
| A6-14 | CURRENT VERIFIED | push dedupe retains full append-log scan; currently latent |
| A6-15 | FIXED SINCE AUDIT | PR #609 merged and startup reconciliation is now wired |
| A6-16 | CURRENT VERIFIED | scheduled life actions and monitor notifications still contain sync blocking I/O on event loop |
### Chunk 7

| Finding | Final classification | Reconciliation note |
|---|---|---|
| C7-F01 | DUPLICATE SYMPTOM | canonical authority conflict represented by C9-F01/RC-01 |
| C7-F02 | CURRENT VERIFIED | chat bootstrap still not tied to recovered Gateway health |
| C7-F03 | CURRENT VERIFIED | unconditional sidebar sync claim still conflicts with save/offline truth |
| C7-F04 | CURRENT VERIFIED | authoritative empty model list can still be replaced by static capability aliases |
| C7-F05 | CURRENT VERIFIED | configured provider state still over-presented as operational readiness |
| C7-F06 | CURRENT VERIFIED | HTTP-200 `{ok:false}` repair result still follows generic frontend success semantics |
| C7-F07 | CURRENT VERIFIED | backend exact action identity exists but native approval UI still omits material payload/target arguments |
| C7-F08 | CURRENT VERIFIED | proposed-only approval surface still drops action before durable terminal outcome is shown |
| C7-F09 | CURRENT VERIFIED | project refresh partial-success result still can leave stale next-step truth |
| C7-F10 | CURRENT VERIFIED | generated API types still are not the effective frontend wire authority |
| C7-F11 | CURRENT VERIFIED | native attention/notification projection remains fragmented/mobile-incomplete |
| C7-F12 | CURRENT VERIFIED | retry-branch presentation remains client-only across reload |
| C7-F13 | CURRENT VERIFIED | shared Dialog focus entry/trap/restore remains incomplete |
| C7-F14 | CURRENT VERIFIED | status logic remains checkout-relative and can label a behind checkout `current` |

### Chunk 8

| Finding | Final classification | Reconciliation note |
|---|---|---|
| COST-001 | CURRENT VERIFIED | no pricing/alias coverage change landed after Chunk 8 |
| PERF-001 | CURRENT VERIFIED | blocking ChatGPT import route unchanged |
| PERF-002 | DUPLICATE SYMPTOM | same unbounded prefetch-history root as C4-16 |
| DEP-001 | CURRENT VERIFIED | no package/lock remediation landed; production HIGH remains audit-policy input |
| BUILD-001 | FIXED SINCE AUDIT | PR #615 merged clock-stable fixture |
| BUILD-002 | CURRENT VERIFIED | non-executable ESLint config/tooling contract remains |
| PERF-003 | CURRENT VERIFIED | old acceptance Gateways/LiteLLM remain resident on 18100/18807/18808 |
### Chunk 9

| Finding | Final classification | Reconciliation note |
|---|---|---|
| C9-F01 | CURRENT VERIFIED | canonical native authority still conflicts with active-looking OpenWebUI documentation/runtime residue |
| C9-F02 | DUPLICATE SYMPTOM | architectural consolidation of current Image Lab F1/F3/F4/F5/F6/F7 |
| C9-F03 | CURRENT VERIFIED | dead native components remain; #617 is an active collision that repairs dead AgentPanel rather than deleting it |
| C9-F04 | DUPLICATE SYMPTOM | consolidated architecture statement for A6-01/A6-03/A6-04/A6-05/A6-08/A6-10 under #550 |
| C9-F05 | DUPLICATE SYMPTOM | consolidated architecture statement for C4-12..15 under #547 |
| C9-F06 | CURRENT VERIFIED | #545 still owns standards convergence; hand-rolled MCP/custom plugin capability plumbing remains current |
| C9-F07 | FIXED SINCE AUDIT | merged PR #620 / closed #552 converges explicit/semantic memory truth and removes unsupported default Weave retrieval |
| C9-F08 | IN FLIGHT | open PR #619 owns #591/#557 linkage but remains red on Project Resume compatibility |
| C9-F09 | DUPLICATE SYMPTOM | runtime identity root is represented concretely by COR-001/REL-001/COR-003/C7-F14/PERF-003 under RC-13 |

### Fixed/stale summary

Fixed since original audit pass: **REL-003, PAR-SEC-006, F9, A6-15, BUILD-001, C4-08, C9-F07** = **7**. No finding was classified STALE / NOT REPRODUCIBLE or SUPERSEDED at Chunk 10 close.

IN FLIGHT findings: **BLD-005, A6-05, C9-F08** = **3**. BLD-005/C9-F08 are owned by open PR #619 (#591/#557); A6-05 is owned by the active dirty #550 Automation worktree. Do not duplicate either lane.

The reconciled current HIGH/CRITICAL count is **30** after excluding fixed, in-flight and duplicate-only symptom rows. This count treats severity labels containing HIGH (including MEDIUM/HIGH) as high-risk and counts each surviving finding ID once.
## 3. Reconciled root-cause ledger

The 71 current verified findings are not 71 independent implementation lanes. They collapse into **15 finite root causes**. Four current items are already IN FLIGHT and must be consumed/reclassified before any overlapping implementation begins.
### RC-01 — Canonical product authority and residue retirement
**Severity:** HIGH. **Findings:** C9-F01, C9-F03; duplicates DOC-001, DOC-002, C7-F01; historical #542/#544 residue. **Impact:** agents/operators can change or test the wrong surface; dead code attracts fixes. **Owner:** no production PR; PR #617 is a collision on dead `AgentPanel`. **Converge/delete:** make native Kitty authority unambiguous, then delete proven-dead components and close stale task issues. **Evidence:** cold-start authority + build/router reachability. **Ordering:** can run in parallel with non-frontend state-machine work after active PR collision check.

### RC-02 — Consequential mutations do not share one durable action/approval/result boundary
**Severity:** HIGH. **Findings:** REL-002, AUTH-001, COR-002, AUTH-002, AUTH-003, AUTH-004, COR-004, C7-F07, C7-F08. **Impact:** direct side effects can bypass approval/receipts; crash-after-claim can be outcome-ambiguous; UI hides exact approval identity and terminal result. **Owner:** existing ActionQueue/Grant architecture; #554 is closed but does not cover these residuals. **Converge/delete:** route or delete direct mutating endpoints, preserve deny precedence, project one durable lifecycle. **Evidence:** ACC-004/007, FI-002/007/008/009/010. **Ordering:** ordered before unattended Automation mutating actions rely on the same policy seam.

### RC-03 — Builder model-execution and publication evidence cross trust boundaries
**Severity:** CRITICAL. **Findings:** BLD-001, BLD-002, BLD-004; SEC-001 duplicate evidence. **Impact:** model-controlled subprocesses can inherit host authority/use the authenticated loopback proxy; reviewed SHA can differ from merged SHA; stale durable ownership can block work. **Owner:** Builder execution/publish/recovery; no open PR owns BLD-001/002/004. **Converge:** explicit worker boundary, exact-SHA re-review after rebase, bounded recovery consistency checks. **Evidence:** ACC-006/008, FI-004/006/017 plus real-child containment tests. **Ordering:** BLD-001 first; BLD-002 and BLD-004 can then proceed independently.

### RC-04 — Memory fan-in lacks one truthful scope/correction/evidence contract
**Severity:** HIGH. **Findings:** C4-02, C4-03, C4-05, C4-06, C4-07; C4-08/C9-F07 are FIXED by merged #620. **Impact:** stale correction cache, cross-project retrieval, source-order ranking and hidden normal-answer degradation can still make context wrong while appearing healthy. **Owner:** #552 is CLOSED after #620; remaining gaps now belong to bounded context/memory follow-up, not a new memory engine. **Converge/delete:** preserve the merged explicit-memory/Project/Weave-subtraction work, then fix active-project scoping, cache invalidation, ranking and evidence/degradation truth without reopening #552 architecture. **Evidence:** ACC-010, FI-012 plus project-scope/evidence parity tests. **Ordering:** no longer blocked on #620, but rebase/collision-check against current main before touching MemoryGraph.

### RC-05 — Artifact/Knowledge boundary is not rebuildable or transactionally truthful
**Severity:** HIGH. **Findings:** C4-01, C4-09, C4-10, C4-11. **Impact:** sensitive metadata can escape prompt filtering; index refresh can destroy old searchable truth; indexing can be reported ready when skipped; current projection cannot be rebuilt from canonical source bytes. **Owner:** #553. **Converge:** Artifact remains source identity; Knowledge replacement/status must be atomic, derived, provenance-linked and rebuildable. **Evidence:** ACC-011 plus failure before/after index replacement and sensitivity propagation. **Ordering:** independent of #552 except shared context-policy tests; coordinate boundary fields, not stores.
### RC-06 — Context budgeting is partial and derived-history work is unbounded
**Severity:** HIGH. **Findings:** C4-04, C4-16; PERF-002 duplicate. **Impact:** a trivial-tier request can still produce an enormous model-visible prompt; prediction history grows forever and rereads the full file. **Owner:** Context/MemoryGraph + prefetcher; no dedicated issue. **Converge:** enforce a whole-system-prompt budget and bounded tail/retention semantics; do not add a new database by default. **Evidence:** oversized-context contract test + FI-018. **Ordering:** can run independently after #552 avoids conflicting edits in `memory_graph.py`.

### RC-07 — Production Research lacks one durable provider-neutral run/evidence contract
**Severity:** HIGH. **Findings:** C4-12, C4-13, C4-14, C4-15; C9-F05 duplicate. **Impact:** research can return false-success prose, misattribute sources, overstate Knowledge promotion, and cannot truthfully resume/represent partial failure. **Owner:** #547. **Converge/delete:** introduce Kitty-owned Research Run/Artifact/evidence semantics, migrate reachable callers, then remove the legacy general `DeepResearcher` path. **Evidence:** durable status/source/citation/cost/promotion acceptance. **Ordering:** self-contained; can run parallel to #552/#553 if shared Knowledge promotion contract is coordinated.

### RC-08 — Image Lab has multiple paid submission/recovery authorities around one otherwise-strong Studio spine
**Severity:** HIGH. **Findings:** F1, F2, F3, F4, F5, F6, F7, F8; C9-F02 duplicate. **Impact:** paid work can bypass Studio budget, ambiguous accepted work can be resubmitted, settled cost can be unclear, paid outputs can be stranded, direct MCP references can bypass privacy ownership, and preflight can disagree with dispatch. **Owner:** Image Lab; #336 covers recovery/idempotency portion but not full authority subtraction. **Converge/delete:** one authorization→reservation→submission receipt→provider outcome→artifact commit→settlement seam; constrain/delete parallel paid execution. **Evidence:** ACC-012/013, FI-007/011/017 plus exact character/anchor/privacy tests. **Ordering:** keep within one Image Lab lane; verify supported legacy/MCP callers before deletion.

### RC-09 — Automation timing exists without a durable occurrence/run/authority lifecycle
**Severity:** HIGH. **Findings:** A6-01..A6-10, A6-13, C9-F04 duplicate; A6-11/A6-12 remain design dependencies. **Impact:** duplicate/missed autonomous actions, stale disable/delete execution, starvation from contaminated watches, implicit timezone semantics, repeated condition notifications and unbounded unattended spend authority. **Owner:** #550. **Converge/delete:** cron remains temporary time-trigger owner; add bounded occurrence/evidence/authority semantics, move Brief timing under it, fair-share monitor sweeps, remove private duplicate timing. **Evidence:** restart/overlap/disable/unknown-side-effect/authority/timezone tests under ACC-008/009 and FI-002/007/017. **Ordering:** depends on RC-02 policy boundary for consequential actions; monitor fairness sub-slice can proceed independently after state-cleanup authority is explicit.

### RC-10 — Native frontend does not consistently project durable backend truth
**Severity:** HIGH. **Findings:** C7-F02, F03, F04, F05, F06, F09, F10, F11, F12, F13; C7-F07/F08 are owned by RC-02. **Impact:** chats can appear missing/“synced,” empty capability can be fabricated, configured providers can look ready, body-level/partial failures can look successful, stale project advice can appear current, attention/retry state is inconsistent across refresh/mobile. **Owner:** native Kitty frontend/Gateway wire contracts; #551 overlaps model evidence but not all truth gaps. **Converge:** validated wire/view-model contracts and reconnect-driven durable rehydration; preserve strong Work/SSE patterns. **Evidence:** ACC-002/003/008/009 plus FI-016 and real-Gateway browser seams. **Ordering:** can be divided into non-overlapping chat, contract, and attention sub-slices after authority cleanup defines canonical surface.
### RC-11 — Capability hosting overlaps standards with Kitty-specific protocol/package plumbing
**Severity:** MEDIUM-HIGH. **Findings:** C9-F06, BLD-003; PAR-SEC-001..005 duplicate evidence. **Impact:** dormant/custom MCP semantics can become a trust/reliability liability if activated, while proprietary plugin state increases maintenance without a protected ecosystem. **Owner:** #545. **Converge/delete:** keep Kitty approval/install/provenance policy, replace commodity protocol lifecycle with official MCP client semantics, keep Agent Skills format, retire custom bundle fields when callers migrate. **Evidence:** stdio + Streamable HTTP discovery/call, timeout cleanup, exact action identity, secret visibility. **Ordering:** can run parallel to most roots but must coordinate BLD-003 and Image MCP callers.

### RC-12 — Project↔Builder Work composition lacks durable identity
**Severity:** MEDIUM-HIGH. **Findings:** BLD-005, C9-F08. **Impact:** Project Resume cannot truthfully show only its delegated Builder Work without heuristics. **Owner:** #591/#557; open PR #619 current head `0bdfb3a9...` implements the explicit `project_id` direction and now has green compatibility/browser/merge evidence. **Converge:** review/land #619 rather than create another lane; no second Work/Project store. **Evidence:** compatibility-safe Project Resume projection + two-project isolation + restart/resume test. **Ordering:** remains blocked on actual merge/reclassification, not on the earlier test failure.

### RC-13 — Runtime identity and lifecycle ownership are insufficient for trustworthy acceptance
**Severity:** HIGH. **Findings:** COR-001, REL-001, COR-003, C7-F14, PERF-003; C9-F09 duplicate; REL-004/A6-12 design dependencies. **Impact:** status/acceptance can exercise the wrong SHA/process; stop→ensure can leave Gateway down; stale acceptance services consume resources and confuse ownership. **Owner:** desktop runtime/launcher; #537 owns stop→ensure only. **Converge/delete:** expose exact source/build/worktree role, distinguish checkout-current from authority-current, identity-check disposable cleanup, choose one machine-restart supervisor. **Evidence:** ACC-001/008, FI-003/017 and exact-SHA acceptance packet. **Ordering:** should precede final product acceptance for every other root; cleanup waits until active process ownership is proven.

### RC-14 — Blocking synchronous I/O and growing append logs violate bounded Gateway hot-path behavior
**Severity:** MEDIUM-HIGH. **Findings:** PERF-001, A6-14, A6-16; C4-16/PERF-002 overlap handled in RC-06. **Impact:** imports/background notifications/LLM work can stall unrelated requests; notification-history lookup can grow without bound. **Owner:** route/action owners. **Converge:** async subprocess or bounded thread isolation for verified blocking I/O; bounded tail/index for dedupe logs. **Evidence:** FI-015 and FI-018 concurrency/growth tests. **Ordering:** independent targeted slices; do not create a global HTTP-client rewrite.

### RC-15 — Operational telemetry/build gates can present incomplete or non-executable truth
**Severity:** MEDIUM. **Findings:** COST-001, DEP-001, BUILD-002. **Impact:** spend can look precise while most model aliases are unpriced; a production HIGH npm vulnerability is advisory; checked-in ESLint policy cannot execute from declared deps. **Owner:** usage telemetry + frontend build/CI. **Converge/delete:** expose price coverage/unknown cost explicitly; patch production dependency and choose explicit HIGH/CRITICAL gate policy; either make lint deterministic or delete dead config. **Evidence:** mixed priced/unpriced cost fixture, `npm audit` policy proof, runnable lint/build gate. **Ordering:** independent and parallelizable after current-main refresh.

### Root-cause ordering summary
RC-13 runtime identity is a prerequisite for trustworthy final acceptance. RC-02 must precede RC-09 wherever Automation can mutate or spend. RC-04 and RC-12 are currently blocked by active implementation lanes. RC-08 stays isolated as one Image Lab authority/recovery lane. RC-01, RC-06, RC-07, RC-10, RC-11, RC-14 and RC-15 can otherwise be split into non-overlapping implementation slices after Chunk 11 defines exact order and collision gates.

## 4. Current ownership / collision map

- **PR #620 MERGED / #552 CLOSED** — C4-08/C9-F07 are FIXED SINCE AUDIT. Preserve the landed memory convergence and do not reopen its architecture.
- **PR #619 OPEN / green current deterministic evidence** — owns BLD-005/C9-F08 under #591/#557 at head `0bdfb3a9...`; do not duplicate and do not mark #591 fixed before merge.
- **PR #617 OPEN / mixed dead-surface work** — changes non-canonical `AgentPanel` plus unrelated provider/ImageBench files; browser seam and merge gate fail. It collides with RC-01's delete/retain decision and is not accepted canonical remediation.
- **#545 OPEN** — owns RC-11 Skills/MCP/plugin convergence and should absorb BLD-003 rather than spawn a second MCP architecture lane.
- **#547 OPEN** — owns RC-07 Research convergence.
- **#550 OPEN** — owns RC-09 Automation lifecycle convergence.
- **#553 OPEN** — owns RC-05 Artifact/Knowledge convergence.
- **#537 OPEN** — owns the stop→ensure portion of RC-13.
- **#336 OPEN** — owns part of RC-08 hosted Image recovery/idempotency, not all paid-authority/accounting convergence.
- **#542/#544 OPEN but stale in premise** — legacy task execution code is already removed by PR #593; reconcile/close rather than reimplement.
- **PR #616 OPEN** — owns today's `.claude` session checkpoint. **PR #618 DRAFT** yielded `.claude` ownership but still collides on the hash-chained `kb-effectiveness.jsonl`; if both survive, #616 first, then regenerate #618's append. Never hand-merge that log.
- **PR #600 OPEN** — audit-support evidence, not implementation authority. Its local worktree is two commits ahead of GitHub head and the unpublished pair is externally preserved; reconcile before any disposable/merge/close decision.
- **Active test-suite-hardening worktree** — protected separate test architecture lane; currently plan/spec only. Do not absorb its work into implementation slices.
- **Interrupted merge-queue experiment** — only uncommitted `scripts/pr_policy.py`/`scripts/pr_scope.py` changes in the shared checkout, externally preserved. It is not accepted CI policy and must not be mistaken for #619.
- **#550 active dirty worktree** — now owns the Morning Brief→cron/stable schedule/timezone slice. A6-05 is IN FLIGHT; A6-04/A6-08 remain current outside the partial patch. Protect this lane and do not create a competing scheduler patch.

## 5. Mandatory crosswalk completion

The filled working crosswalk is `/Users/jacobbrizinnski/Kitty-Audit-Sidecars/AUDIT_COVERAGE_CROSSWALK_FINAL_DRAFT.md`.

Coverage status: candidate dispositions **9/9**; acceptance cases **14/14**; failure-injection cases **18/18**; upstream-reference rows explicitly dispositioned; **0 TBD/unresolved crosswalk rows**. ACC-011 and FI-013/FI-014 remain applicable release acceptance even though no current defect finding justifies implementation before a failure is reproduced.
## 6. Reconciliation counts and residual decisions

- Finding IDs reconciled: **97**.
- CURRENT VERIFIED: **71**.
- FIXED SINCE AUDIT: **5** — REL-003, PAR-SEC-006, F9's specific stale-Gateway instance, A6-15, BUILD-001.
- IN FLIGHT: **4** — BLD-005, C4-08, C9-F07, C9-F08.
- DUPLICATE SYMPTOM: **14**.
- DESIGN QUESTION finding IDs: **3** — REL-004, A6-11, A6-12.
- STALE / NOT REPRODUCIBLE: **0**; SUPERSEDED: **0**; UNKNOWN finding IDs: **0**.
- Current unresolved findings strictly labeled **HIGH or CRITICAL: 30**, counting CURRENT VERIFIED plus IN FLIGHT and excluding duplicate/fixed rows and MEDIUM-HIGH/MEDIUM-HIGH-style labels.
- Root causes: **15**; HIGH/CRITICAL root causes: **11**.
- Crosswalk unresolved/TBD count: **0**.

The three remaining design-question finding IDs do not block Chunk 10: they are explicit dependencies for Chunk 11 sequencing, not unclassified evidence. No rewrite of Python, Next/React, Gateway, Builder, Image Lab, MemoryGraph or cron is supported by the reconciled evidence.

## 7. Chunk 10 completion state

Chunk 10 is **COMPLETE** at `origin/main` `95d62c5dabfa33ce36d52ff48c2c50393417a319`. The current checkout is an active shared implementation surface and is not audit authority. No implementation or repository/runtime/GitHub mutation was performed by this audit.

Chunk 11 must consume this report, the final-draft crosswalk, current GitHub/main truth, the PR #600 execution/runbook materials, and active-lane ownership. It must produce the ordered final execution plan rather than reopening investigation. Any pre-existing `CHUNK11_*` or `AUDIT_COVERAGE_CROSSWALK_FINAL.md` sidecars created before the final Chunk 10 handoff are premature/incomplete and non-authoritative; Chunk 11 must start from the finalized Chunk 10 artifacts instead.

`CHUNK10_STATE: COMPLETE`
