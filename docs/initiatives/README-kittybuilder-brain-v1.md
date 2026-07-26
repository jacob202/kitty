# KittyBuilder Brain V1 — retained initiative inputs

Status: planning input. These manifests are **not** the current execution sequence and must not be applied blindly.

This directory preserves two substantial initiative drafts:

- `docs/initiatives/kittybuilder-brain-v1.json` — worker-session integration, runtime projection, live events, cockpit, operator controls, decision support, and bounded autonomy.
- `docs/initiatives/process-hardening-v1.json` — review freeze/scope, immutable receipts, live-versus-snapshot authority, state-write enforcement, and Builder transition hardening.

KittyBuilder remains the sole authority for packets, dependencies, worktrees, leases, validation, review, publishing, and state transitions. External coding agents remain replaceable worker backends.

## Validation

```bash
./kitty builder initiative validate docs/initiatives/kittybuilder-brain-v1.json
./kitty builder initiative validate docs/initiatives/process-hardening-v1.json
```

Validation proves schema and authoring checks only. It does not promote either initiative into the active roadmap or prove its packets are `free-exec`.

## Execution status

Do not apply or run these manifests until all of the following are true:

1. Python and frontend CI install from a clean checkout.
2. PRs #261, #262, and #263 are resolved coherently.
3. The exact remaining Phase 1 work has been recalculated from current code and evidence.
4. At least one tiny real JSON packet has passed the `docs/FREE_MODEL_PACKET_STANDARD.md` checks and a daylight unattended run has been inspected end to end.
5. `docs/ROADMAP.md` explicitly promotes the relevant delta.

`KB-BRAIN-00-source-harvest` must not repeat the broad ecosystem survey: its harvest output already exists in `docs/research/kittybuilder-brain-v1-harvest.md`. Before any downstream Brain packet is activated, reconcile it against current Kitty code and split only the still-missing behavior into bounded executable packets.

The Brain and process-hardening drafts both claim `gateway/builder_loop.py`. Run them sequentially unless cross-initiative path-collision enforcement lands first.

These files preserve researched ideas. They are not permission to create another queue, scheduler, state store, orchestrator, architecture survey, or duplicate runtime surface.
