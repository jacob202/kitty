# Disposition Ledger — Historical compatibility pointer

**Status:** Historical compatibility pointer.
**Archived snapshot:** [`archive/DISPOSITION_LEDGER_2026-08-08.md`](archive/DISPOSITION_LEDGER_2026-08-08.md)

The original ledger was a dated inventory of planning files and dispositions. It
was useful when the planning surface was small enough to enumerate, but it is no
longer exhaustive and is not an execution authority. This path remains so older
links fail safely instead of silently landing on stale instructions.

Current activation truth is intentionally narrower:

1. [`ROADMAP.md`](ROADMAP.md) owns the living delivery sequence.
2. [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md) records the current approved broad Mission.
3. A plan, packet, or initiative file is a candidate until explicitly approved;
   file existence, manifest validity, or historical ledger membership does not
   activate it.
4. Builder owns engineering execution state; `workspace_global` and GitHub issue
   #490 provide live interactive coordination/collision evidence.

Use the archived snapshot only for historical archaeology. Re-verify any row
against current Git, the authority map, roadmap/mission, Builder, GAR, and #490
before acting on it.
