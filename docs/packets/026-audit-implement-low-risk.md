# Packet — Engineering Leverage Audit: Implement Low-Risk Recommendations

**Status:** Authorized 2026-07-15 by Jacob. Ready for a single focused worker.
**Source audit:** `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md` Section 10
**Builder queue ID:** `kb_mrm5ru85_9ea7`

---

## Purpose

Implement only the recommendations from the audit that are already marked
as low-risk and high-confidence. Do not perform new research. Do not add
new dependencies beyond those explicitly recommended. One branch, one
focused PR.

---

## Authorized scope (low-risk, high-confidence only)

- Fix stale documentation (`CLAUDE.md:97` honcho claim, `PROJECT_STATUS.md` branch claim — verified stale vs `feat/campaign-alpha-phase-2-integration` in STATE.md).
- Add vulture to CI (advisory if needed to avoid blocking on false positives).
- Add lychee link checking if the audit already vetted it.
- Wire `.codegraph` freshness validation.
- Consolidate the skills registry **if** it is purely structural.
- Create the initial KittyBench skeleton (not the full benchmark suite).

## Not authorized (do not touch)

- Large dependency additions.
- Builder architecture refactors.
- Documentation rewrites beyond the audited corrections.
- Deleting files that require owner judgment (root temp files,
  `scripts/curation/`, generic agent skills archive — these are
  HUMAN DECISION REQUIRED per audit rows H1–H6).
- New feature work.

---

## Execution discipline

**Every implemented recommendation must:**

1. Reference the audit section it came from (e.g., "Audit §10 DO NOW #4").
2. Include before/after evidence — diff excerpt, test output, or
   rendered file showing the change is real.

**If an audited recommendation turns out not to be worthwhile during
implementation, skip it and explain why in the PR description — do not
force it.** A skip-with-reason is a success signal; a silent drop is not.

---

## Recommended order

1. Fix the two known-stale doc claims — lowest risk, immediate truth
   correction.
2. Wire vulture into CI as advisory — surfaces dead code without gating.
3. Wire lychee link checker (advisory first cycle, gate later if clean).
4. Wire `.codegraph` freshness validation.
5. KittyBench skeleton with 2 stable fixtures — pick packets that have
   been validated by prior workers.
6. Skills registry consolidation **only if** the work is structural
   (consolidating metadata, freshness state) and does not delete skills
   in the audited H5 group.

---

## Verification before declaring done

Run before opening the PR:

- `cd gateway/kitty-chat && npm test` and `npm run build`
- `python3.12 -m pytest tests/ -q --tb=short` (or targeted slice if full
  suite is slow)
- `./kitty doctor --json` preflight clean
- Confirm no `git rm` of files outside the audited safe-deletion set
- Confirm no additions to `pyproject.toml` or `package.json` beyond the
  audited tools

---

## What "done" looks like

- One branch off `main`, one focused PR.
- PR description lists each implemented audit row with: source row,
  before evidence, after evidence, verification command output.
- Skipped rows are listed with the reason skipping turned out to be
  the right call during implementation.
- No silent scope creep into NEW / LATER / REJECT / HUMAN DECISION rows.
