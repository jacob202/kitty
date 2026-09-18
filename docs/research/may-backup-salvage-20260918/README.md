# Kitty May-backup salvage package

Status: **integrated research reference — implementation remains separately owned**

Created from the read-only archaeology of:

- restored tree: `/Users/jacobbrizinnski/Projects (from backup)`
- restored Kitty checkout: `/Users/jacobbrizinnski/Projects (from backup)/kitty`
- restored Kitty HEAD: `d8f05fc73d23ff52302700e54fe4df19428f7c15` (2026-05-22)
- current Kitty main used for comparison: `72ccb20b74484a7dc9f1c829322b8c841daf62dd`

## Integration provenance

The archaeology was originally staged outside the repository because `docs:roadmap` had an active owner. Integration was revalidated on 2026-09-18 after that claim cleared, against current GitHub main `99a9153a551f46dc077ba8c858e6eb1cd02d7702`.

The original staging archive remains evidence only; this directory is the repository reference copy.

This package is intentionally **not** another roadmap, backlog, queue, authority, prompt database, or control plane. It preserves four narrow mechanisms that survived scrutiny after comparing May-era material with current Kitty.

## Salvage decisions

| Item | Historical evidence | Current state | Decision |
|---|---|---|---|
| Local identity conditioning | `imagegen/gen_face_final.py`, `generate_my_face_auto.py` | Kitty now has character locks, InsightFace scoring, Nano Banana references, and cloud PuLID through Runware/Fal; local ComfyUI ignores `identity_images` | **ADAPT** only as a local/offline ComfyUI identity backend |
| Governed prompt experiments | `6a7900a^:src/utils/meta_prompt_optimizer.py` | Current session learning has evidence, recurrence and paired capability evaluation, but no explicit prompt candidate/version/rollback loop | **ADAPT** using Git + existing learning/eval authority, no new DB |
| Physical-reality evidence invariant | `ff62251^:src/core/physical_reality_router.py` | Current evidence rules are strong generally; no dedicated physical/sensory invariant was found | **ADAPT invariant only**, not the regex router |
| Human preference pairs | `ba10080^:src/eval/rlhf_collection.py` | Current paired evaluation is numeric/task-matched; no direct chosen-vs-rejected human evidence primitive was found | **ADAPT** as bounded evaluation evidence, never automatic training/routing |

## Explicit non-salvage

Do **not** restore the old `builder.py`, `task_runner.py`, `task_delegator.py`, councils, secondary context plane, correction DB, self-healer, safe-patch loop, or `skill_refinery.py`. Modern Kitty owns those responsibilities more safely.

In particular, the historical skill refinery auto-approved when its reviewer was unavailable. That is incompatible with current fail-closed review requirements.

## Files

- `01-local-comfyui-identity-backend.md`
- `02-governed-prompt-experiments.md`
- `03-physical-reality-evidence-invariant.md`
- `04-human-preference-evidence.md`
- `MANIFEST.json`

## Integration rule

When the `docs:roadmap` lane is genuinely free, copy/adapt these documents into one narrow Kitty research location, re-check current main first, and treat every implementation as a separate explicitly owned packet. Do not turn this staging directory into an authority.
