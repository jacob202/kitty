# Kitty Foundation Replacement Study — 2026-07-27

## Decision being tested

Kitty's product ambition remains intact. The question is whether its application shell and commodity infrastructure should continue on the current `assistant-ui`-based implementation or move to a mature full application foundation.

This is not a study of whether Kitty should become smaller. It is a study of how to stop rebuilding capabilities that already exist while preserving what is uniquely Kitty:

- provider-independent intelligence and zero-dollar survival;
- personal memory, history, corrections, preferences, and behavioural understanding;
- durable projects, decisions, obligations, evidence, blockers, and next actions;
- permission-aware tools and automation;
- proactive but earned intervention;
- Image Lab orchestration and identity-preserving workflows;
- KittyBuilder as the software-development control plane.

## Correction to the historical framing

Open WebUI previously served as the core shell with Kitty layered above it. That architectural direction was coherent: a mature commodity shell underneath, Kitty-owned intelligence above it. The project later drifted toward replacing more of the shell and infrastructure with custom code.

The current repository already partially returned to mature reuse: `gateway/kitty-chat` depends on the MIT-licensed `@assistant-ui/react` package and adapts Kitty's own message store into its runtime. The current UI is therefore the **custom Kitty application on a component foundation** baseline, not a completely from-scratch UI.

## Legal reuse boundary

Jacob's rule for a foundation is stricter than merely being source-available:

> Kitty must be legally able to modify, rebrand, and continue developing the foundation without preserving another product's identity as the product surface.

Eligible for this spike:

- **assistant-ui** — MIT;
- **LibreChat** — MIT;
- **AnythingLLM** — MIT.

Excluded:

- **Open WebUI** — current custom license is not accepted for this purpose. It may be discussed as prior history or a general product reference, but its source code is not copied, adapted, or fetched by the spike.

Every external checkout used by the prototype is pinned and its local license text is checked for `MIT License` before configuration is applied. License and copyright notices remain with the checkout. This is an engineering reuse gate, not legal advice.

## Verified existing seam

Kitty already exposes `POST /v1/chat/completions` in an OpenAI-compatible shape. Before the request reaches the provider, the gateway:

1. validates Kitty-specific project and conversation identifiers;
2. composes the runtime manifest;
3. classifies the request;
4. selects or respects a model;
5. assembles Kitty's personal/project context;
6. replaces client system prompts with Kitty's authoritative system context;
7. forwards the enriched request through Kitty's model layer;
8. records lifecycle and memory evidence.

This is the correct architectural boundary for the spike. Candidate shells are clients. Kitty remains the intelligence and policy layer.

The missing compatibility piece was standard model discovery. The spike adds:

- `GET /v1/models`;
- `GET /v1/models/kitty-default`.

Both expose only the stable virtual model `kitty-default`. Provider names remain hidden behind Kitty so a UI cannot become a second routing authority.

## Candidate 1 — Current Kitty on assistant-ui

### Reuse strategy

Keep the current Next.js application and continue consuming assistant-ui as a component/runtime library.

### Strengths

- maximum control over Kitty's visual language and non-chat surfaces;
- no foreign application data model to fight;
- Kitty projects, memory evidence, Image Lab, Builder, and proactive views can be first-class;
- upstream library updates are narrower than full-app merges;
- already integrated.

### Risks

- Kitty must continue implementing application-level features that LibreChat or AnythingLLM already ship;
- auth, files, branching, provider controls, agents, settings, admin surfaces, and conversation management may remain custom maintenance burdens;
- feature incompleteness is currently severe despite significant development time.

### Key question

Can the current shell become a complete daily-use application faster by importing more permissive libraries and modules, or has the amount of missing full-app plumbing already justified a foundation switch?

## Candidate 2 — LibreChat

### Reuse strategy

Maintain a thin Kitty fork tracking upstream. Connect its custom OpenAI-compatible endpoint to Kitty Gateway. Add Kitty features through new extension modules and minimized upstream patches.

### Strengths

- broad multi-provider chat foundation;
- model comparison, presets, agents, MCP, memory, file handling, code execution, artifacts, authentication, and web search already exist;
- strong OpenAI-compatible custom endpoint support;
- active project and MIT license.

### Risks

- substantial infrastructure footprint: API, MongoDB, MeiliSearch, RAG services, and its own auth/data assumptions;
- Apple Silicon requires a compatible MongoDB image for the local prototype;
- candidate memory, agents, endpoints, and permissions may duplicate Kitty authorities;
- visual and information architecture may still require extensive redesign;
- full-app fork creates recurring upstream merge work.

### Key question

Can LibreChat be reduced to a shell around Kitty without allowing its own memory, routing, agent, and conversation assumptions to become competing sources of truth?

## Candidate 3 — AnythingLLM

### Reuse strategy

Maintain a thin Kitty fork tracking upstream. Configure its Generic OpenAI provider to call Kitty Gateway. Evaluate its workspace, document, memory, agent, flow, model-router, and scheduled-task systems as replaceable commodity foundations or integration surfaces.

### Strengths

- workspace-centred document and project organization;
- automatic and user-managed memories;
- dynamic model routing;
- agents, MCP, flows, scheduled jobs, Gmail and calendar skills;
- generic OpenAI endpoint support;
- cloud-hostable and MIT licensed.

### Risks

- workspace model may be too document/RAG-centred for Kitty's broader life-project ontology;
- its routing, memory, agents, schedules, and permissions can duplicate Kitty's systems;
- UI and interaction model may still need significant replacement;
- source build may be heavy on Jacob's 8 GB Apple Silicon machine;
- full-app fork creates upstream merge work.

### Key question

Can Kitty adopt AnythingLLM's mature workspace and automation plumbing while keeping Kitty's project graph, memory provenance, authority boundary, and model policy canonical?

## Prototype implementation

The isolated spike branch contains:

- a standard Kitty `/v1/models` compatibility route and tests;
- a pinned LibreChat bootstrap with Kitty endpoint and Apple Silicon Docker overlay;
- a pinned AnythingLLM bootstrap with Generic OpenAI configuration targeting Kitty;
- a shared no-model-call gateway verification;
- an evidence matrix and hard disqualifiers.

External source is cloned to `~/.cache/kitty-foundation-spike` by default and never vendored into Kitty.

## Decision method

The same real workflows must run in all three candidates. Feature inventory is not enough. The first proof uses a real life project, preferably the Disability Tax Credit application, because it exercises:

- personal context;
- durable project state;
- source documents;
- evidence and provenance;
- interruption/resumption;
- consequential-action approval;
- mobile access.

The evaluation then tests provider switching and zero-dollar survival, tools, proactive intervention, Image Lab extension cost, KittyBuilder integration, and upstream maintenance burden.

## Preliminary conclusion

No foundation is selected yet.

However, the architecture boundary is now explicit:

> Mature shells may own generic interaction and infrastructure. Kitty owns personal intelligence, continuity, projects, permissions, routing policy, proactive judgment, creative orchestration, and Builder governance.

A candidate is disqualified if adopting it requires Kitty to surrender those authorities or maintain two competing versions of them.

## Official sources consulted

- LibreChat About, feature documentation, custom endpoints, compatibility matrix, and Docker setup.
- AnythingLLM repository, documentation, Docker configuration, Generic OpenAI provider variables, memories, router, agents, flows, and scheduled jobs.
- assistant-ui repository and MIT license.
- Current Kitty repository implementation and dependency declarations.
