# KittyBuilder Brain V1 — launch

This branch contains two independent Builder manifests:

- `docs/initiatives/kittybuilder-brain-v1.json` — source harvest, worker-session integration, runtime snapshot, live events, native Kitty cockpit, operator controls, decision engine, and bounded autopilot.
- `docs/initiatives/process-hardening-v1.json` — review freeze/scope, immutable receipts, live-vs-snapshot authority, state-write enforcement, and Builder transition hardening.

The Brain initiative runs inside Kitty. External coding agents remain worker backends; they do not become a second queue, worktree manager, or source of truth.

## Fetch and validate

```bash
git fetch origin feat/kittybuilder-brain-initiatives
git switch feat/kittybuilder-brain-initiatives

./kitty builder initiative validate docs/initiatives/kittybuilder-brain-v1.json
./kitty builder initiative validate docs/initiatives/process-hardening-v1.json
```

## Apply only the Brain initiative

```bash
./kitty builder initiative apply docs/initiatives/kittybuilder-brain-v1.json
./kitty builder initiative status kittybuilder-brain-v1
```

Start with the source harvest using the free worker path:

```bash
./kitty builder initiative run-packet \
  kittybuilder-brain-v1 \
  KB-BRAIN-00-source-harvest \
  --free \
  --watch
```

Do not launch later Brain packets until the harvest packet is reviewed. It may refine integration choices, allowed paths, or packet sequencing based on pinned source inspection.

## Apply the hardening initiative separately

```bash
./kitty builder initiative apply docs/initiatives/process-hardening-v1.json
./kitty builder initiative status process-hardening-v1
```

Safe independent starting packets are:

```bash
./kitty builder initiative run-packet process-hardening-v1 PH-01-review-freeze --free --watch
./kitty builder initiative run-packet process-hardening-v1 PH-03-session-receipts --free --watch
./kitty builder initiative run-packet process-hardening-v1 PH-06-builder-transitions --free --watch
```

Do not run those three simultaneously unless their generated worktrees and actual allowed-path sets remain non-overlapping after validation. Prefer the Brain harvest first; it is documentation-only and should inform what code is actually worth porting.

## Recommended immediate sequence

1. Apply `kittybuilder-brain-v1`.
2. Run only `KB-BRAIN-00-source-harvest`.
3. Review the pinned adopt/adapt/reimplement register.
4. Adjust downstream packets only where the evidence requires it.
5. Launch `KB-BRAIN-01-worker-session-adapter`.
6. Apply `process-hardening-v1` when you are ready to run it independently.
