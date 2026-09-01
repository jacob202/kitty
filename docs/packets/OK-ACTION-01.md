# OK-ACTION-01 — Canonical Object + Action Contract

## Mission

Define the smallest reusable product contract that lets Kitty render the same owned object with the same meaningful actions across Home, Chat, Work, Projects, Library, Automations, and Image Lab without introducing a new source of truth.

This packet is contract/inventory work plus the minimum implementation needed to prove the contract against real existing authorities. Do not redesign Home or Chat yet.

## Why now

Kitty already exposes actionable state in many surfaces, but each surface decides independently what an object is, what to call it, where it opens, and which action is available. That prevents Chat and Home from becoming coherent cross-product surfaces.

## Product acceptance moment

The same real Kitty object can be projected into two different surfaces and has:
- one canonical identity;
- one product-facing type/title;
- one canonical destination;
- the same available primary action where applicable;
- the same truthful lifecycle/status semantics.

## Constraints

- Do not create another Project, Artifact, Work, Automation, Deadline, Image, or Conversation store.
- Do not create a frontend workflow engine.
- Existing authorities remain authoritative.
- Prefer composition/projection over migration of underlying stores.
- Do not collapse approval into execution, queued into running, unknown into failed, or generated into durably stored.
- Preserve current behavior outside the explicit contract integration.

## First step — verify current repo truth

Before coding, inspect actual current implementations and write a compact inventory in the PR description or packet evidence covering at least:

1. Gateway action/approval/execute models and routes.
2. Project identity and destination semantics.
3. Work/Builder identity and status semantics.
4. ArtifactStore/Library identity and destination semantics.
5. Automation identity/status/action semantics.
6. Deadline identity/action semantics.
7. Image Lab job/result identity/status semantics.
8. Existing frontend types/hooks that already overlap this proposed contract.

If a suitable shared object/action contract already exists, extend/reuse it instead of inventing another.

## Proposed minimal product contract

Names are not sacred; preserve existing naming if a better equivalent already exists.

```ts
type KittyObjectType =
  | 'project'
  | 'artifact'
  | 'work'
  | 'automation'
  | 'deadline'
  | 'image'
  | 'conversation'
  | 'research'
  | 'action';

type KittyTruthState =
  | 'ready'
  | 'queued'
  | 'running'
  | 'waiting_for_user'
  | 'succeeded'
  | 'failed'
  | 'partial'
  | 'unknown';

interface KittyObjectRef {
  type: KittyObjectType;
  id: string;
  title: string;
  subtitle?: string;
  destination?: KittyDestination;
  truthState?: KittyTruthState;
  projectId?: string;
  owner: string;
}

interface KittyAvailableAction {
  id: string;
  label: string;
  kind: string;
  prominence: 'primary' | 'secondary' | 'destructive';
  enabled: boolean;
  unavailableReason?: string;
  requiresApproval?: boolean;
  destination?: KittyDestination;
  arguments?: Record<string, unknown>;
}
```

Do not force every authority into this exact shape if doing so loses domain truth. A projection may expose domain-specific detail alongside the shared shell.

## Backend approach

Prefer one of these in order:

1. Reuse existing per-authority responses and normalize only in the frontend when all required truth is already available.
2. Add small per-authority projection helpers if normalization belongs in Gateway.
3. Add a single read-only object/action projection only if it materially reduces duplicated frontend logic.

Do **not** build a generic mutation endpoint that bypasses existing action routes.

## Frontend approach

Target likely locations:
- `gateway/kitty-chat/src/lib/gateway.ts`
- `gateway/kitty-chat/src/lib/queries.ts`
- new small shared types/helpers under `gateway/kitty-chat/src/lib/` or `components/actions/`

The contract should be renderable without knowing the originating surface.

## Proof integration

Integrate two real domains only for this packet, selected after inspection to minimize collision. Recommended candidates:
- Project next step;
- Deadline;
- Artifact;
- Work item.

Do not migrate every surface in this packet.

## Tests

Add focused tests proving:
- stable identity across projections;
- canonical destination is deterministic;
- unavailable action carries a reason rather than silently disappearing when the user needs to understand it;
- lifecycle truth is not upgraded optimistically;
- two domain adapters conform to the shared contract.

## Non-goals

- Full Capability Launcher.
- Universal `@` search.
- Home redesign.
- Chat context injection.
- New action execution infrastructure.
- Visual polish campaign.
- Mascot work.

## Done when

1. Inventory of existing authorities is recorded.
2. One shared object/action contract exists or an existing equivalent is proven sufficient.
3. Two real domains produce that contract without changing their source of truth.
4. Tests pass.
5. Evidence explicitly names any domain that cannot safely fit the shared shell and why.
6. Follow-up packet `OK-ACTION-02` can consume the contract without re-deciding architecture.
