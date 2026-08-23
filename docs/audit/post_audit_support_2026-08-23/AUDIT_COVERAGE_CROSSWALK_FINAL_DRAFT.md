# AUDIT COVERAGE CROSSWALK — FINAL DRAFT

Date: 2026-08-23
Chunk: 10 cross-pass reconciliation
Current-main authority: `95d62c5dabfa33ce36d52ff48c2c50393417a319`
Rule: current repository/GitHub/runtime truth wins; PR #600 is coverage support, not finding authority.

## A. Candidate disposition crosswalk

| Candidate | Final disposition | Finding IDs | Current ownership | Rationale/evidence | Remediation group |
|---|---|---|---|---|---|
| CAND-001 Legacy Gateway task execution | FIXED / CONFIRMED DELETE COMPLETED | C9 candidate reconciliation | PR #593 merged; #542/#544 stale-open | `task_runner.py`, `/task*` and canonical task UI are gone; do not resurrect | NO ACTION; close/reconcile stale issues |
| CAND-002 `ImageStudio.tsx` | CONFIRMED DELETE after caller-proof gate | C9-F03 | no deletion PR; #617 is mixed dead-surface work on sibling `AgentPanel` and is not accepted remediation | canonical Studio is `StudioView -> ImageLab`; no production import found | RC-01 |
| CAND-003 OpenWebUI authority residue | CONSOLIDATE / RETIRE ACTIVE AUTHORITY CLAIMS | DOC-001,DOC-002,C7-F01,C9-F01 | no implementation PR | ADR 0039/native launcher are canonical; active docs still contradict | RC-01 |
| CAND-004 Scheduler/background duplication | CONSOLIDATE / PARTLY IN FLIGHT | A6-01,A6-03,A6-04,A6-05,A6-08,A6-10,C9-F04 | issue #550 + active dirty `converge/automation-550-20260823`; A6-05 directly in flight | one Gateway timing owner plus durable Automation occurrence truth; delete private Brief clock after parity | RC-09 |
| CAND-005 Dependency ownership cleanup | DISPROVED | none | none | `requirements.txt` is sole Python dependency owner; tooling metadata is not competing authority | NO ACTION |
| CAND-006 Configuration-loading sprawl | DEFERRED WITH REASON | UQ-08 | none | differing dotenv precedence is partly deliberate; no general correctness defect proven | NO ACTION pending concrete failure |
| CAND-007 Legacy research wrapper | CONSOLIDATE / DELETE AFTER MIGRATION | C4-12,C4-13,C4-14,C4-15,C9-F05 | issue #547 | reachable `DeepResearcher` is legacy provider-specific execution beside intended durable Research Runs | RC-07 |
| CAND-008 HTTP/client duplication | DEFERRED WITH REASON | PERF-001,A6-16 are narrower defects | none | broad one-client convergence is unproven; fix blocking/lifecycle defects where measured | RC-14 only |
| CAND-009 Frontend size/dead-surface cleanup | DUPLICATE of CAND-002 | C9-F03 | #617 collision on dead AgentPanel; PR also bundles unrelated provider/ImageBench files and has red browser/merge evidence | size alone is not a defect; delete only independently proven dead surfaces | RC-01 |

Candidate rows resolved: **9/9**. No TBD remains.

## B. Acceptance coverage crosswalk
| ID | Disposition | Related findings | Existing proof | Missing proof/procedure | Remediation group |
|---|---|---|---|---|---|
| ACC-001 Cold Launch to Ready | APPLICABLE | COR-001,REL-001,COR-003,REL-004,A6-12,C7-F14,C9-F09,PERF-003 | launcher/runtime tests and live process inspection | controlled cold launch + stop→ensure + exact process/SHA ownership proof | RC-13 |
| ACC-002 Basic Chat Truth | APPLICABLE | C7-F02,C7-F03,C7-F12 | chat persistence/stream tests and durable turn ledger | browser→real Gateway outage/recovery/restart with no false sync claim | RC-10 |
| ACC-003 Tool Read Path | APPLICABLE | PAR-SEC-001..005,C9-F06 | native chat does not auto-execute tools; ToolCallCard exposes calls | retained MCP/tool contract after #545; prove read cannot mutate unrelated state | RC-11 |
| ACC-004 Explicit Side-Effect Path | APPLICABLE | REL-002,AUTH-001,AUTH-002,AUTH-003,AUTH-004,COR-004,C7-F07,C7-F08 | ActionQueue atomic claim + #554 exact fingerprints/grants | prove all consequential writes cross one gate; restart/unknown + visible terminal lifecycle | RC-02 |
| ACC-005 Work Creation and Resume | APPLICABLE / IN FLIGHT | BLD-005,C9-F08 | PR #619 current head `0bdfb3a9...` has green backend/frontend/browser/merge evidence | land/reclassify #619, then prove project-scoped create/restart/resume with one Work identity on main | RC-12 |
| ACC-006 Builder Execution | APPLICABLE | BLD-001,BLD-002,BLD-003,BLD-004 | 1121 focused Builder tests + lease/fencing coverage | containment, rebased-SHA rereview, residue recovery, MCP paid-launch contract | RC-03 / RC-11 |
| ACC-007 Approval Persistence | APPLICABLE | REL-002,COR-002,AUTH-002,C7-F07,C7-F08 | #554 call fingerprint + scoped grant persistence | approve→restart→execute; exact args and terminal outcome remain visible; no duplicate effect | RC-02 |
| ACC-008 Restart Recovery | APPLICABLE | REL-001,REL-002,BLD-004,F3,F5,A6-01,C7-F02,C9-F09 | Builder modern fencing; Image batch UNKNOWN; #609 autonomy reconcile | composed service restart with pending action/image/automation/chat and exact no-duplicate evidence | RC-02 / RC-03 / RC-08 / RC-09 / RC-10 / RC-13 |
| ACC-009 Notification Truth | APPLICABLE | AUTH-003,COR-004,A6-09,A6-10,C7-F11 | signal dedupe + durable expert signal handling in some paths | one event→one notification/attention item; restart/ack/partial-stage proof | RC-02 / RC-09 / RC-10 |
| ACC-010 Memory Correction Freshness | APPLICABLE; #552 CORE FIX MERGED | C4-03,C4-08,C9-F07 | PR #620 merged explicit-memory correction/provenance and Weave-subtraction proof; C4-08/C9-F07 fixed | remaining C4-03 cache freshness still requires production write→correct→same query→restart invalidation proof | RC-04 |
| ACC-011 Backup and Restore Fidelity | APPLICABLE RELEASE COVERAGE; NO DEFECT FINDING | none | no Chunk 0–9 finding established current restore defect | isolated round-trip, unsupported-key prevalidation, >default-limit parity, integrity checks | RELEASE ACCEPTANCE; code only if it fails |
| ACC-012 Paid Operation Accounting | APPLICABLE | F1,F3,F4,F5,F6,A6-07,COST-001,C9-F02 | Studio pre-reservation; no native paid fallback; fal reconciliation | canonical paid submission identity, ambiguous outcome recovery, reserve/settle truth, cost coverage | RC-08 / RC-09 / RC-15 |
| ACC-013 Image Lab Integration Seam | APPLICABLE | F1,F2,F3,F4,F5,F6,F7,F8,C9-F02 | 565 focused tests; durable Studio/session/batch/Artifact spine | browser reference→result→restart with provider receipt, character-consistent preflight, no duplicate billing | RC-08 |
| ACC-014 Canonical Authority Consistency | APPLICABLE | DOC-001,DOC-002,C7-F01,C9-F01,C9-F02,C9-F03,C9-F04,C9-F05,C9-F06 | ADR 0039/0040 + canonical launcher/Work/Studio paths | cold-agent authority check; legacy execution/surfaces removed or explicitly quarantined | RC-01 / RC-07 / RC-08 / RC-09 / RC-11 |

Acceptance rows resolved: **14/14**. No TBD remains.

## C. Failure-injection coverage crosswalk
| ID | Disposition | Related findings | Existing proof | Missing proof/procedure | Remediation group |
|---|---|---|---|---|---|
| FI-001 Gateway dies during read | APPLICABLE | C7-F02,C9-F09 | health/read failure paths exist | kill in-flight read in disposable Gateway; no fabricated success or durable mutation | RC-10 / RC-13 |
| FI-002 Gateway dies after local mutation | APPLICABLE | REL-002,AUTH-001,AUTH-003,AUTH-004,F5 | some domain idempotency exists | crash exactly after commit/side effect and before response; preserve committed/unknown distinction | RC-02 / RC-08 |
| FI-003 Stop then immediate ensure | APPLICABLE | REL-001 | issue #537 has deterministic reproduction | automated stop→ensure stabilization/final-health regression while leaving unrelated healthy listener alone | RC-13 |
| FI-004 Builder worker dies mid-attempt | APPLICABLE | BLD-004 | modern Builder lease/interruption/fencing tests substantially cover | retain modern proof; add residue doctor/recovery cases, no weakening of fencing | RC-03 |
| FI-005 Duplicate mission submission | APPLICABLE / ALREADY PROVEN FOR BUILDER IDENTITY | none current | immutable initiative identity + live-launch suppression verified in Chunk 3 | rerun after Builder lifecycle changes; no remediation unless regression appears | RC-03 acceptance |
| FI-006 Late worker response | APPLICABLE / ALREADY PROVEN | none current | lease token + claim-version fencing rejects stale completion | preserve regression whenever Builder state machine changes | RC-03 acceptance |
| FI-007 External success, local timeout | APPLICABLE | REL-002,F3,F5,A6-01 | Image batch can represent `unknown`; RunPod edit has action id | generic Action/Image/Automation timeout-after-acceptance must reconcile without blind retry | RC-02 / RC-08 / RC-09 |
| FI-008 Local success, external follow-up failure | APPLICABLE | A6-10,C7-F06,C7-F09 | some domain records distinguish stages | inject notification/GitHub/provider follow-up failure; retry failed stage only and surface partial truth | RC-09 / RC-10 |
| FI-009 Approval then argument mutation | APPLICABLE / BACKEND CORE ALREADY PROVEN | C7-F07 | #554 exact approval fingerprint rejects changed identity | keep exact-call regression; UI must show material arguments before approval | RC-02 |
| FI-010 Specific deny vs broad allow | APPLICABLE | AUTH-002 | failure reproduced: session-global allow beats narrower deny | policy precedence regression: narrower explicit deny must win | RC-02 |
| FI-011 Provider 5xx/transport failure | APPLICABLE | F3,F4,F6,A6-07,C4-15 | native Studio avoids cross-provider paid fallback | paid/non-idempotent paths distinguish no-submit vs ambiguous submit and prohibit blind retry | RC-07 / RC-08 / RC-09 |
| FI-012 Cache stale after correction | APPLICABLE | C4-03 | exact stale-cache reproduction exists | correction invalidates/bypasses cache; same query immediately returns corrected truth | RC-04 |
| FI-013 Unknown restore store | APPLICABLE RELEASE COVERAGE; NO DEFECT FINDING | none | no verified current defect from audit | isolated unsupported-store snapshot must fail before target mutation | RELEASE ACCEPTANCE |
| FI-014 Large backup dataset | APPLICABLE RELEASE COVERAGE; NO DEFECT FINDING | none | no verified current truncation finding from audit | export/restore above default list limits with exact count parity | RELEASE ACCEPTANCE |
| FI-015 Async route with slow sync dependency | APPLICABLE | PERF-001,A6-16 | both blocking paths independently reproduced | concurrent cheap request remains responsive while slow import/background dependency executes | RC-14 |
| FI-016 UI refresh during transition | APPLICABLE | C7-F02,C7-F08,C7-F09,C7-F12 | Work and expert signals already reconstruct well | refresh/reconnect tests for chat, actions, partial project refresh, retry branches | RC-10 |
| FI-017 Whole-machine restart | APPLICABLE | REL-001,BLD-004,F3,A6-01,A6-12,C9-F09 | per-domain restart primitives; #609 autonomy reconcile | controlled supported restart proving one canonical supervisor, durable truth and no duplicate paid/destructive work | RC-03 / RC-08 / RC-09 / RC-13 |
| FI-018 Log/history growth | APPLICABLE | C4-16,A6-14,PERF-002 | live prefetch history measured ~7.7 MB/30k+ rows | large synthetic histories keep hot-path reads bounded; explicit retention/rotation | RC-06 / RC-14 |

Failure-injection rows resolved: **18/18**. No TBD remains.

## D. External-reference crosswalk
| Upstream pattern | Verified Kitty finding(s) | Disposition | Why relevant / architecture guard | Remediation group |
|---|---|---|---|---|
| Official MCP Python SDK + standard Agent Skills lifecycle | PAR-SEC-001..005,BLD-003,C9-F06 | RECOMMENDED | replaces commodity hand-rolled protocol/package plumbing while Kitty keeps approvals, trust, credentials and provenance | RC-11 |
| SQLite Online Backup + integrity/foreign-key checks | no verified backup defect | TEST PATTERN ONLY, NOT REMEDIATION | useful for ACC-011/FI-013/FI-014 acceptance; does not justify a storage rewrite | RELEASE ACCEPTANCE |
| `asyncio.to_thread` / native async isolation for blocking I/O | PERF-001,A6-16 | RECOMMENDED | directly addresses measured event-loop blocking without changing Gateway architecture | RC-14 |
| HTTPX pooled-client lifecycle | CAND-008 deferred; no general client-lifecycle defect | NOT RECOMMENDED AS BROAD CONVERGENCE | adopt locally only if a measured repeated-connection/lifecycle defect later warrants it | NO ACTION |
| `npm audit --audit-level` as enforceable CI threshold | DEP-001 | RECOMMENDED | turns an observed production HIGH advisory into explicit policy without a package-manager rewrite | RC-15 |
| Replaceable upstream research engine pattern (benchmark first) | C4-12,C4-13,C4-14,C4-15,C9-F05 | RECOMMENDED AS ENGINE PATTERN, NOT FRAMEWORK COMMITMENT | Kitty keeps durable Research Run/Evidence/Artifact semantics and may benchmark at most two engines; no second research architecture | RC-07 |

Crosswalk unresolved/TBD rows: **0**.
