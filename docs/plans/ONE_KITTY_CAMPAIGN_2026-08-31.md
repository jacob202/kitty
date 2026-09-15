# ONE KITTY — Cohesion, Actionability, and Brand Campaign

## Transformation

Today Kitty can feel like a collection of capable surfaces. After this campaign, Kitty should feel like one intelligent, carefully designed product: Chat understands the rest of Kitty and can guide or act across it; Home shows only things that matter and every visible action has a real outcome; objects stay coherent across surfaces; and the visual system feels precise, deliberate, and unmistakably Kitty.

## Product moments

1. Open Home and see the single best continuation, things that genuinely need attention, and current work — with actions that immediately do something useful.
2. Ask Chat about another part of Kitty and have it understand the relevant project, work, artifact, deadline, automation, or image without making the user manually shuttle context around.
3. Start or complete work from one surface and see the same underlying object reflected everywhere else instead of creating an orphaned representation.
4. Put two unrelated Kitty screens side by side and immediately recognize the same visual grammar: alignment, spacing, typography, controls, state treatment, and interaction density.
5. Encounter Kitty’s mascot/illustration language at a few meaningful moments — greeting, thinking, waiting, success, empty/offline — as restrained brand punctuation rather than decoration everywhere.

## Campaign invariants

1. No wave introduces a new source of truth when Kitty already owns the underlying thing.
2. No visible object without a purpose.
3. No visible action without a real outcome or a truthful disabled/unavailable state.
4. No Kitty-owned object becomes conceptually invisible merely because the user changed surfaces.
5. Chat is the product center, not a replacement source of truth for Projects, Work, Library, Automations, Image Lab, or Builder.
6. Product truth outranks animation, optimism, or visual polish.
7. Mascot/personality is sparse and functional.

## Shared primitives

### Action grammar
A shared projection describing what can be done with a Kitty-owned object without moving authority into the frontend.

Minimum shape:
- canonical object identity
- product-facing type
- title/summary
- canonical destination
- available actions
- action preconditions
- status/truth state where relevant
- owning authority
- optional project/context relationship

This primitive powers Home cards, Chat typed objects, context insertion, and cross-surface continuity.

### Object reference
A stable, product-facing way to refer to a Project, Artifact, Work item, Automation, Image, Deadline, Conversation, Research Run, etc. without exposing implementation IDs as the primary UX.

### Action lifecycle
A normalized presentation layer for user-visible action state:
`ready -> queued -> running -> waiting-for-you -> succeeded | failed | partial | unknown`

This is a projection, not a replacement execution engine.

### Design grammar
Shared typography, spacing, control sizing, card/list anatomy, hierarchy, icon rules, motion rules, and state treatment enforced across the product.

### Kitty illustration language
A small canonical set of mascot states with one drawing language and explicit usage rules.

---

# Wave 1 — Action Grammar

## Transformation

Anything Kitty shows as actionable behaves consistently and routes to the real owning system.

## Demo moment

Home shows “School deadline Thursday.” The object exposes `Plan`, `Open project`, and `Ask Kitty`; each action invokes a real existing authority rather than a bespoke dead-end click handler.

## Kitty already has

- Gateway actions and approval/execution flows.
- Projects and next-step projections.
- Work/Builder durable state.
- ArtifactStore and Library.
- Automations.
- Deadlines.
- Image Lab jobs/results.
- Existing shared Gateway client/query layer.

## Gap

Actions are currently shaped per surface. Similar objects can expose different controls, labels, navigation, and lifecycle feedback depending on where they render. The frontend has no single product-level answer to “what can the user do with this object now?”

## Put it here

- `gateway/routes/` — add a read-oriented object/action projection only if existing contracts cannot supply the required information without duplicating authority.
- `gateway/kitty-chat/src/lib/gateway.ts` — shared object/action contracts.
- `gateway/kitty-chat/src/lib/queries.ts` — shared hooks/query keys.
- `gateway/kitty-chat/src/components/actions/` — shared action rendering and execution components.
- Existing Home, Chat, Work, Projects, Library, Automations, and Image Lab surfaces consume the projection incrementally.

## Steal specifically

From command/action systems in mature IDE and AI products:
- capability labels use user language rather than route names;
- actions declare preconditions;
- primary versus secondary actions are explicit;
- status updates in place;
- canonical “open/show” destination is predictable;
- unavailable actions explain why when that matters.

## Do not steal

- another registry of Projects, Work, Artifacts, Automations, or Images;
- a frontend-owned workflow engine;
- a generic command bus that bypasses Gateway authority;
- optimistic success where execution has not been proven.

## Truth requirements

Do not collapse:
- approval into execution;
- queued into running;
- accepted into succeeded;
- reserved into spent;
- generated into durably registered;
- unknown into failed.

## Dependencies

None. This is the first shared primitive.

## Unlocks

Waves 2, 3, 4, 7.

## Packet split

- `OK-ACTION-01` — inventory object types/actions and define the shared contract. SEQUENTIAL foundation.
- `OK-ACTION-02` — shared frontend action renderer/executor over existing authorities. SEQUENTIAL after 01.
- `OK-ACTION-03` — migrate Home’s actionable items to the grammar. PARALLEL after 02.
- `OK-ACTION-04` — migrate one non-Home surface (Projects/Work) as proof the grammar is genuinely reusable. PARALLEL after 02.

## Acceptance

A user can encounter the same underlying object in two surfaces and receive the same meaningful primary action, same truth state, and same canonical destination. No migrated action is a decorative button or prose-only promise.

---

# Wave 2 — Chat as Kitty Concierge

## Transformation

Chat can see the relevant state of the rest of Kitty and help the user act on it without becoming the owner of that state.

## Demo moment

Ask: “What should I deal with next?” Chat can cite the active project, a finished Builder run that needs review, and an approaching deadline, then offer real actions such as `Open work`, `Review`, `Plan`, or `Use artifact`.

## Kitty already has

- project context and resume endpoints;
- Work/Builder state;
- ArtifactStore/Library;
- deadlines;
- Automations state;
- Image Lab results;
- current-session/context machinery;
- typed UI beginnings such as tool/action cards.

## Gap

The information exists but is fragmented across projections. Chat does not yet have one bounded, truthful “Kitty state around this conversation” projection suitable for reasoning and action rendering.

## Put it here

- Gateway: add/extend a read-only concierge/context projection that composes existing authorities.
- Chat request/context assembly: include only relevant, bounded product context.
- `ChatMessage`/typed message rendering: render referenced Kitty objects and actions as first-class objects rather than prose descriptions.
- `InputBar`: preserve active-project/object context without clutter.

## Steal specifically

From strong assistant/IDE products:
- the assistant can see current workspace state;
- references resolve to canonical objects;
- suggested actions are attached to the referenced object;
- execution status updates the same object/card;
- technical evidence remains available behind disclosure rather than dominating the reply.

## Do not steal

- global context dumping;
- a second memory store;
- hidden cross-surface mutations;
- automatic actions that should require explicit approval.

## Truth requirements

Chat must distinguish what it knows from what it infers. It must not claim an Automation ran, Builder completed, Artifact saved, or Image persisted unless the owning authority says so.

## Dependencies

Wave 1 Action Grammar.

## Unlocks

Home/Chat continuity, project-aware guidance, richer context insertion, research/image integration.

## Packet split

- `OK-CHAT-01` — bounded concierge context projection over existing authorities.
- `OK-CHAT-02` — wire projection into chat context with explicit token/size limits and provenance.
- `OK-CHAT-03` — render cross-Kitty object references/actions in chat.
- `OK-CHAT-04` — acceptance scenarios for Project + Work + Deadline + Artifact continuity.

## Acceptance

Chat can truthfully answer questions about at least Projects, Work, Artifacts, and Deadlines using current Kitty state, and at least one suggested action per domain invokes the real owning workflow.

---

# Wave 3 — Home as Action Board

## Transformation

Home stops being a collection of informational sections and becomes a prioritized control surface for the user’s day.

## Demo moment

Open Home and immediately see: one best continuation, two things needing attention, one upcoming deadline, and meaningful running work. Every primary control either completes an action, starts a real workflow, or opens the canonical destination.

## Principles

Default order:
1. Continue
2. Needs you
3. Today / Upcoming
4. Active
5. Kitty noticed

Everything else is subordinate or disclosed.

## Put it here

- `HomeState.tsx` / `HomeView.tsx` — simplify composition and migrate to shared action/object primitives.
- Reuse existing next-step, deadline, approval, activity, project, and insight projections.
- Remove equal-weight card sections that do not justify first-screen space.

## Do not steal

A generic analytics/dashboard pattern. Home is not an operator console and is not a wall of metrics.

## Dependencies

Wave 1 required. Wave 2 improves `Ask Kitty` and continuation actions.

## Acceptance

Every first-screen Home card answers “why is this here?” and exposes a working next step. Decorative or non-actionable information cannot crowd out actionable state.

---

# Wave 4 — Cross-Surface Continuity

## Transformation

The same Kitty-owned object remains recognizably the same object everywhere.

## Demo moment

Start Builder work from Chat, observe it in Work/Home, finish it, open the produced Artifact, attach that Artifact to a Project, and ask Chat about it without copying an internal ID.

## Work

- canonical object references and destinations;
- shared status/action presentation;
- result relationships;
- project ownership/context;
- “open result/open work/open project” semantics;
- no orphan result when a secondary registration step fails.

## Dependencies

Waves 1–2.

## Acceptance

At least one end-to-end workflow crosses four surfaces while preserving identity, truth state, and result relationships.

---

# Wave 5 — Precision System

## Transformation

Kitty looks deliberately designed at every scale rather than merely token-compliant.

## Scope

Lock and enforce:
- typography roles and line heights;
- text/baseline alignment;
- spacing rhythm;
- content-width rules;
- control heights;
- icon sizing/alignment;
- radius vocabulary;
- surface/list/card anatomy;
- heading hierarchy;
- button hierarchy;
- loading/empty/error geometry;
- desktop/mobile composition rules.

## Important distinction

Token compliance is table stakes. Existing audits already show that a surface can technically use shared tokens while retaining bespoke local styling and inconsistent composition. This wave is a running-product visual convergence pass, not a grep exercise.

## Packet split

Divide by shared primitive/system first, then by collision-safe surface clusters. Require visual acceptance at desktop and phone widths.

## Acceptance

Unrelated screens share obvious alignment, spacing, typography, controls, and state grammar. No document-level horizontal scroll. No accidental tiny type. No component-specific “almost the same” button/card variants without a domain reason.

---

# Wave 6 — Kitty Brand Character

## Transformation

Kitty gains a memorable but restrained personality system.

## Direction

Create one canonical illustration language and a small state set, approximately:
- hello;
- thinking;
- working;
- waiting;
- found something;
- success;
- empty;
- sleeping/offline;
- creative/Image Lab;
- Builder/working.

Use in high-value moments only: greeting, onboarding, empty states, meaningful waits, success, offline/degraded, creative context.

## Reference principle

Study Anthropic/Claude’s use of small character/illustration moments as brand punctuation, but do not copy Claude’s mascot, palette, layouts, or illustrations. Adapt the principle into Kitty’s own visual language.

## Do not steal

- mascot everywhere;
- ornamental animation around routine controls;
- brand elements that compete with user content;
- literal Claude assets/style imitation.

## Acceptance

A user can remove the word “Kitty” from a few selected screens and still recognize a consistent Kitty visual identity, while normal work surfaces remain calm.

---

# Wave 7 — Everything Responds

## Transformation

No interaction leaves the user wondering whether anything happened.

## Scope

- immediate pressed/selected feedback;
- truthful queued/running/waiting/completed states;
- stable skeleton geometry;
- in-place result/status updates;
- recoverable failure states;
- deliberate state-change motion;
- reduced-motion support;
- navigation feedback;
- focus restore and keyboard/touch parity.

## Acceptance

Exercise all primary actions on Home, Chat, Work, Projects, Library, Automations, and Image Lab. Every action either visibly progresses, completes, fails with recovery, or truthfully explains why it cannot run.

---

# Wave 8 — Ruthless Product Pass

## Transformation

Remove the remaining roughness that makes Kitty feel assembled instead of authored.

## Review questions

For every primary surface on desktop and phone:
- Does it align?
- Does this element deserve its space?
- Is hierarchy obvious?
- Is information duplicated?
- Is the copy product-facing?
- Does every action work?
- Does reload preserve what it claims to preserve?
- Is the mobile layout intentionally composed?
- Is anything visually generic, noisy, or over-carded?
- Can something be removed?

## Acceptance evidence

- running product, not screenshots alone;
- desktop and iPhone-class viewport;
- degraded states where applicable;
- reload/restart for persistence claims;
- before/after captures for major visual changes;
- explicit deletion/simplification ledger.

---

# Dependency spine

`Action Grammar`
→ Chat Concierge
→ Home Action Board
→ Cross-Surface Continuity
→ Everything Responds

`Canonical Object Reference`
→ Chat
→ Home
→ Projects/Work/Library continuity
→ future universal @ insertion

`Design Grammar`
→ every surface
→ brand character placement
→ final product pass

`Action Lifecycle`
→ Home cards
→ Chat cards
→ Work
→ Automations
→ Image Lab

# Recommended order

1. Wave 1 — Action Grammar
2. Wave 2 — Chat as Kitty Concierge
3. Wave 3 — Home as Action Board
4. Wave 4 — Cross-Surface Continuity
5. Wave 5 — Precision System
6. Wave 7 — Everything Responds
7. Wave 6 — Kitty Brand Character
8. Wave 8 — Ruthless Product Pass

Brand comes after precision so illustration does not become camouflage for inconsistent UI.

# Immediate implementation packets

Start with:

1. `OK-ACTION-01` — object/action contract inventory and canonical projection design.
2. `OK-ACTION-02` — shared action renderer/executor.
3. `OK-CHAT-01` — bounded concierge context projection.

Do not start broad Home visual redesign before Action Grammar exists. Otherwise Home will gain another generation of bespoke buttons and cards that must be migrated again.
