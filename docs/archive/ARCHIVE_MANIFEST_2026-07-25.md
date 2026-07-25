# Archive Manifest — 2026-07-25 plan-folder cleanup

**Approved by:** Jacob, 2026-07-25 ("do the doc file folder cleanup").
**Method:** Checked `docs/PLANS.md`'s own "Stray Plans Consolidated" section
(which named disposition intent but never executed it), then verified each
candidate's actual status by reading it — two files PLANS.md called archive
candidates turned out to still say "Status: Ready to implement" and were
**not** archived (see below). Only moved what was confirmed stale.

## Moved to archive (this pass)

- `docs/plans/migration-health.md` — a single point-in-time health snapshot
  ("Status: PASS", dated 2026-06-22), not a living plan.
- `docs/plans/chore-workspace-cleanup-2026-07-12.md` — dated one-off chore,
  no longer actionable.
- `docs/plans/pr164-archaeology.md` — historical investigation doc ("what
  died, what survived, what to recover" from a specific PR), reference only.
- `docs/planning/brainstorm-kitty-evolution-2026-07-24.md` — `docs/PLANS.md`
  itself states this was "absorbed into this doc's future sections."
- `docs/initiatives/kitty-endgame-init-1-builder-closeout-v1.json` —
  superseded by `kitty-endgame-init-2-daily-driver-v1.json`'s v2 sibling
  (`kitty-endgame-init-1-builder-closeout-v2.json`, kept).

## Checked and explicitly NOT archived

`docs/PLANS.md` grouped these under "8 others are short/dated/single-purpose
→ archive candidates," but both are still open work:

- `docs/plans/image-runner-and-recipe-cleanup.md` — "Status: Ready to
  implement."
- `docs/plans/memory-graph-contract-enforcement.md` — "Status: Ready to
  implement."

`docs/plans/fix-kitty-ui-wiring.md` was left in place too — `PLANS.md`
already describes it as "partially done, partially stale," which isn't a
clean archive call without reconciling it line by line against what's
shipped.

## Untouched (still active, out of scope for this pass)

- `docs/planning/kitty-vision-gap-analysis-2026-07-24.md`,
  `kittybuilder-redesign-2026-07-24.md`, `image-studio-character-system-2026-07-24.md`
  — owned by a different tool session (see `docs/PLANS.md` Lane 3/4).
- `docs/planning/agent-prompts-2026-07-24.md`, `vision-horizons.md`,
  `kitty-next-evolution-working-notes.md`, `feature-reference-map.md` — live
  references.
- `docs/initiatives/kx-01` through `kx-06` manifests — active initiative
  history, never archived per the canonical-homes table below.
- `docs/plans/chore-master-fix-and-deepen.md`, `t1-upload-smoke-ci.md` —
  not short, not clearly done; left for a future pass with actual review
  rather than a guess.
