# Final Audit Coverage Crosswalk Template

The sequential auditor should complete this during Chunks 10–11.
Do not fill cells from package assumptions; use verified audit evidence.

## Candidate dispositions

| Candidate | Final disposition | Finding ID(s) | Current issue/PR/branch | Evidence | Plan chunk / No action |
|---|---|---|---|---|---|
| CAND-001 Legacy Gateway task execution | TBD | | | | |
| CAND-002 ImageStudio.tsx | TBD | | | | |
| CAND-003 OpenWebUI authority residue | TBD | | | | |
| CAND-004 Scheduler/background duplication | TBD | | | | |
| CAND-005 Dependency ownership cleanup | TBD | | | | |
| CAND-006 Configuration-loading sprawl | TBD | | | | |
| CAND-007 Legacy research wrapper | TBD | | | | |
| CAND-008 HTTP/client duplication | TBD | | | | |
| CAND-009 Frontend size/dead-surface cleanup | TBD | | | | |

Allowed dispositions should preserve the audit's own status vocabulary and clearly distinguish verified work from disproven/deferred material.

## Acceptance coverage

| ID | Applicable? | Finding ID(s) | Existing proof/test | Required proof/test | Plan chunk |
|---|---|---|---|---|---|
| ACC-001 | TBD | | | | |
| ACC-002 | TBD | | | | |
| ACC-003 | TBD | | | | |
| ACC-004 | TBD | | | | |
| ACC-005 | TBD | | | | |
| ACC-006 | TBD | | | | |
| ACC-007 | TBD | | | | |
| ACC-008 | TBD | | | | |
| ACC-009 | TBD | | | | |
| ACC-010 | TBD | | | | |
| ACC-011 | TBD | | | | |
| ACC-012 | TBD | | | | |
| ACC-013 | TBD | | | | |
| ACC-014 | TBD | | | | |

If an acceptance case is not applicable, record the reason. Do not delete the row.

## Failure-injection coverage

| ID | Applicable? | Finding ID(s) | Existing proof/test | Required proof/test | Plan chunk |
|---|---|---|---|---|---|
| FI-001 | TBD | | | | |
| FI-002 | TBD | | | | |
| FI-003 | TBD | | | | |
| FI-004 | TBD | | | | |
| FI-005 | TBD | | | | |
| FI-006 | TBD | | | | |
| FI-007 | TBD | | | | |
| FI-008 | TBD | | | | |
| FI-009 | TBD | | | | |
| FI-010 | TBD | | | | |
| FI-011 | TBD | | | | |
| FI-012 | TBD | | | | |
| FI-013 | TBD | | | | |
| FI-014 | TBD | | | | |
| FI-015 | TBD | | | | |
| FI-016 | TBD | | | | |
| FI-017 | TBD | | | | |
| FI-018 | TBD | | | | |

## Upstream-reference usage

| Reference topic | Verified Kitty finding that justified use | Recommended? | Plan chunk |
|---|---|---|---|
| MCP client lifecycle / SDK | | TBD | |
| SQLite backup/integrity | | TBD | |
| asyncio blocking I/O isolation | | TBD | |
| HTTP client lifecycle/pooling | | TBD | |
| dependency-audit CI gating | | TBD | |

## Completion gate

No row may remain `TBD` when Chunk 11 is declared complete.
A row may end `NOT APPLICABLE`, `DISPROVED`, `ALREADY PROVEN`, or another explicit disposition, but it must contain a reason/evidence reference.
This template is a coverage mechanism, not a source of findings.
