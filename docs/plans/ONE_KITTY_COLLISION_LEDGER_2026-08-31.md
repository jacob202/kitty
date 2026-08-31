# ONE KITTY — Collision Ledger

## Purpose

Prevent the ONE KITTY cohesion campaign from reimplementing or trampling the prior WOW campaign while those branches are still being integrated.

Observed locally on 2026-08-31 after a fresh `git fetch origin main`:

- `origin/main`: `05caf4a8`
- canonical checkout is intentionally not safe to modify directly; it has local divergence/untracked coordination content.
- prior WOW implementation lanes remain in dedicated worktrees.

## Existing WOW lanes to treat as incoming foundations

### Capability Launcher
Branch: `feat/wow-capability-launcher-20260831`
Head: `55ffbc11`

Introduces/changes:
- `gateway/routes/capabilities.py`
- `gateway/context_assembler.py`
- `CommandPalette.tsx`
- Gateway client/tests

ONE KITTY interaction:
- Do not build another capability registry.
- Action Grammar may eventually supply contextual object actions to the launcher, but must not replace capability authority.

### Artifact Canvas
Branch: `feat/wow-artifact-canvas-20260831`
Head: `920fc089`

Introduces/changes:
- artifact preview route
- `ArtifactCanvas.tsx`
- `LibraryView.tsx`
- Artifact/Gateway tests

ONE KITTY interaction:
- Artifact is already becoming a cross-surface object.
- Reuse its identity/content contract for Action Grammar and continuity.

### Activity Center
Branch: `feat/wow-activity-center-20260831`
Head: `883f5ce7`

Introduces/changes:
- `gateway/activity_projection.py`
- `gateway/routes/activity.py`
- `ActivityCenter.tsx`
- `TopBar.tsx`
- activity tests

ONE KITTY interaction:
- This is the likely source for normalized execution/activity truth.
- Do not create a second lifecycle/activity projection in ONE KITTY.
- Action lifecycle presentation should adapt this where applicable.

### Project Workspace
Branch: `feat/wow-project-workspace-20260831`
Head: `b8f7dec1`

Introduces/changes:
- `ProjectWorkspace.tsx`
- Projects views/panels
- Project tests

ONE KITTY interaction:
- Project destination and context semantics should come from this implementation once integrated.
- Chat Concierge should consume project context, not create a parallel project shell.

### Rich Chat
Branch: `feat/wow-rich-chat-20260831`
Head: `d7954d47`

Introduces/changes:
- `gateway/routes/actions.py`
- authoritative action read route
- `ActionCard.tsx`
- `ArtifactChatCard.tsx`
- `ChatMessage.tsx`
- action/artifact card tests

ONE KITTY interaction:
- Highest collision risk with `OK-ACTION-01/02`.
- Treat the existing authoritative action read route and ActionCard as candidates to extend into the canonical object/action grammar.
- Do not start a separate action system until this branch is reconciled.

### Context Picker
Branch: `feat/wow-context-picker-20260831`
Head: `4c37d0ad`

Introduces/changes:
- `gateway/context_references.py`
- frontend `context-references.ts`
- `InputBar.tsx`
- `KittyContext.tsx`
- Chat message/context tests

ONE KITTY interaction:
- Canonical object references likely already have a partial implementation here.
- `OK-CHAT-01` must reuse this rather than inventing another mention/reference contract.

### Personal Intelligence
Branch: `feat/wow-personal-intelligence-20260831`
Head: `558b4b0a`

Introduces/changes:
- `gateway/intelligence_projection.py`
- `HomeIntelligence.tsx`
- `HomeState.tsx`
- `HomeView.tsx`

ONE KITTY interaction:
- Direct collision with Home Action Board.
- Do not redesign Home until this branch is integrated or explicitly superseded.
- Preserve its selective-intelligence ranking as input to the `Kitty noticed` slot rather than restoring section sprawl.

### Research Workspace
Branch: `feat/wow-research-run-20260831`
Head: `e25dc400`

Introduces/changes:
- durable Research workspace/routes/components
- builds on all prior WOW branches in the stack

ONE KITTY interaction:
- Research Run should become another canonical Kitty object after integration, not a special ONE KITTY subsystem.

### Image Studio
Branch: `feat/wow-image-studio-20260831`
Head: `71edecce`

Status observed: worktree contains local modifications in `gateway/image_recipes.py` and `tests/test_image_recipes.py`; treat as actively owned.

ONE KITTY interaction:
- Do not touch Image Lab implementation until that owner is clear.
- Later Action Grammar should adapt image result/job actions only after the branch settles.

## Structural discovery

The WOW branches are not independent peers anymore; they form a cumulative stack. For example, Rich Chat includes Project Workspace, Activity Center, Artifact Canvas, and Capability Launcher ancestors, and later Context Picker / Personal Intelligence / Research / Image Studio build on Rich Chat.

Therefore the ONE KITTY campaign should not cherry-pick random files from these branches. First establish the accepted/integrated WOW tip or compiler result, then base ONE KITTY implementation on that coherent state.

## Safe work now

Safe before WOW integration:

- planning and packet refinement;
- competitor/theft research;
- design-language specification that does not modify live product files;
- running-product acceptance rubric;
- inventory of canonical object/action concepts against the settled WOW branch stack.

Hold until WOW integration:

- `HomeState.tsx` / `HomeView.tsx` edits;
- `ChatMessage.tsx` / `InputBar.tsx` edits;
- `gateway.ts` / `queries.ts` broad changes;
- action route redesign;
- Project/Artifact/Activity projection rewrites;
- Image Lab changes.

## Execution rule

When WOW integration finishes, rerun this ledger against fresh `origin/main`. Delete assumptions that are no longer true, then start `OK-ACTION-01` from a fresh isolated worktree based on the verified integrated commit.
