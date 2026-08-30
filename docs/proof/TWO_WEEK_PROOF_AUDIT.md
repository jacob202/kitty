# Kitty Two-Week Proof — Preliminary Evidence Audit

**Audit date:** 2026-08-04  
**Repository baseline:** `b3f68aae84525f980d44db8d7b9e6d728457b0db`  
**Mission:** `KPROOF-001`  
**Current status:** source/history audit complete enough to choose the proving seam; live Mac runtime audit still required before implementation.

## Audit standard

- **VERIFIED** — directly inspected in current repository source, GitHub state, or recorded commit diff.
- **INFERENCE** — reasoned conclusion from verified evidence.
- **HYPOTHESIS** — must be tested in the running application.

Repository source and history can prove that an implementation exists. They cannot prove that Jacob's current local services, credentials, databases, providers, or UI journey work. Runtime behavior remains the acceptance authority.

## Executive finding

Kitty should not be rebuilt for this proof.

The repository already contains the core pieces needed for the proposed operator loop:

1. a Gateway product boundary;
2. a durable KittyBuilder queue and runtime projection;
3. action-queue-mediated Builder controls;
4. a custom client with a substantial Builder status surface;
5. model/provider routing and recent provider-failure repairs;
6. tests and browser infrastructure that can be narrowed into a real journey proof.

The smallest viable path is to **repair and compose the existing seams** into one conversation-plus-progress experience, then prove one real code change. Replacing the Gateway, Builder queue, or custom client would spend the proof window rebuilding machinery that already exists.

## What demonstrably exists

### VERIFIED — current architecture boundary

`README.md` at the baseline commit defines:

- Open WebUI as a replaceable daily-driver shell at port 3000;
- Gateway as product authority at port 8000;
- LiteLLM as model routing/fallback at port 8001;
- KittyBuilder as the durable engineering execution control plane;
- `kitty-chat` as the retained custom client, fallback, and development surface at port 4000.

The same authority states that Builder truth must come from its supported database/API/CLI, not comments or prose.

### VERIFIED — Builder is substantial existing code, not a placeholder

The repository contains dedicated Builder modules for queue storage, leases, runs, worker sessions, events, runtime projection, commands, reports, scope, contracts, recovery, and HTTP routes. High-value entry points include:

- `gateway/builder_queue_db.py`
- `gateway/builder_queue.py`
- `gateway/builder_queue_leases.py`
- `gateway/builder_queue_runs.py`
- `gateway/builder_runner.py`
- `gateway/builder_worker_session.py`
- `gateway/builder_runtime.py`
- `gateway/routes/builder.py`
- `gateway/routes/builder_control.py`

Recent commits also added detached durable execution (`287c1947`), cancellation/recovery semantics (`705fbc6d`), actionable PR/check/review state (`1d9338eb`), a shared runtime projection (`fb8630c8`), and a single subprocess adapter seam (`65adb7f9`). These commits are evidence of implemented code and review history, not live proof on Jacob's Mac.

### VERIFIED — the custom client already renders detailed Builder truth

`gateway/kitty-chat/src/components/BuilderSurface.tsx` reads the shared runtime manifest and renders:

- initiatives and packets;
- current task and run states;
- attempt history;
- retry-budget consumption;
- failure classification and errors;
- leases, branches, base SHAs, and worker identity;
- validation and second-model review evidence;
- pull-request, checks, and review state;
- stale/degraded-data warnings;
- polling every five seconds during active runs through TanStack Query.

This is already most of the progress model required by the prototype.

### VERIFIED — mutation endpoints exist

`gateway/routes/builder_control.py` accepts:

- `run_next`
- `pause`
- `resume`
- `cancel`
- `cleanup`
- `requeue`
- `recover_stale`

Each request is proposed and executed through the existing action queue. The frontend has a `useBuilderAction()` mutation and defines UI controls for resume, stale recovery, requeue, and cleanup.

### VERIFIED — the Build Work control seam is internally contradictory

Three directly inspected defects make this the best proving seam:

1. `BuilderSurface` tells the user: **“This surface is read-only.”**
2. `BuilderControls` defines real mutation controls but is not mounted anywhere in the component tree found by repository search.
3. `useBuilderAction()` invalidates the query key `['runtime']`, while the actual Builder projection is cached under `['runtime-manifest', projectId]`. A successful action therefore does not request the authoritative state immediately.

Additional trust defect: `/builder/action` returns an ordinary HTTP-success payload with `{ok: false, error: ...}` when execution fails. Unless the frontend explicitly rejects that payload, React Query may treat a failed Builder action as successful.

This is not a visual-polish problem. It is a broken product contract across UI affordance, mutation transport, durable state, and feedback.

### VERIFIED — the repository already knows this class of failure

Open issue #346 records live iPhone evidence from 2026-08-01 that Work exposed internal Builder machinery, dead-looking workflows, queue text, and backend errors instead of completing understandable tasks. Issues #349 and #352 require running-app task evidence and independent product review rather than accepting component tests as proof.

These issues support the proof's direction. They do not establish that the same failures remain unchanged on the current baseline.

## What only appears to work

### HYPOTHESIS — durable execution survives a real local failure

Commits and tests claim detached execution, lease recovery, provider exhaustion handling, and model switching. The current audit has not yet killed a live parent process, exhausted a provider, restarted Kitty, and observed the same job continue from supported Builder state.

### HYPOTHESIS — chat can create an approved Mission without manual translation

The repository contains chat, context, tools, Builder status, action queue, and Mission concepts. This audit has not yet identified and exercised one supported conversation-to-approved-durable-job path that avoids Jacob translating the conversation into a CLI command, packet, or agent prompt.

This is the largest product-risk unknown.

### HYPOTHESIS — the current application launches cleanly at the baseline SHA

Commit messages contain recent live measurements and successful local claims for Open WebUI, Gateway chat, tools, models, and image paths. This session has not launched Jacob's local checkout, inspected its databases, or exercised the current UI. Those claims remain historical evidence until repeated.

### HYPOTHESIS — provider failover preserves job context

Provider routing and failures have received recent fixes, but the proof requires context continuity across worker/model changes, not only chat fallback. That must be demonstrated with a live Builder job and recorded attempt history.

## Preserve, repair, replace

### Preserve

- Gateway as product authority.
- Builder's durable queue, attempts, leases, recovery, evidence, and publication state.
- The shared Builder runtime projection.
- The action queue as the approval/audit boundary.
- Existing model/provider adapters and policy.
- TanStack Query polling/staleness model.
- Existing Playwright/browser proof infrastructure.
- Open WebUI as a replaceable general chat shell, not the proof's product authority.

### Repair

- Conversation → outcome contract → approval → durable Builder job.
- Mount only the minimum safe Builder controls required for the proof.
- Correct query invalidation and mutation error handling.
- Present Builder state beside the conversation in user language while retaining inspectable evidence.
- Keep chat available during execution and expose now/why/next answers from durable state.
- Add an explicit hard budget envelope and approval boundary.
- Add one real launched-app journey test and one independent review pass.

### Replace or remove from the proof path

- Do not use the current full Builder inspector as the default product interaction.
- Do not expose packet IDs, leases, retry counters, or raw control-plane terminology in the primary conversation unless Jacob opens evidence details.
- Do not depend on historical mission prose or issue text for live state.
- Do not build another queue, dashboard application, orchestration framework, or model router.

## Chosen proving seam

**User-visible interaction:** From a Kitty conversation, approve a small repair to the Build Work experience and watch Builder carry it to a verified running result.

**First repair candidate:** Make the existing Builder recovery action truthful and usable:

- expose one contextual **Retry this work** action only when a failed/stale packet is selected;
- explain what retry will do before approval;
- send the action through the existing action queue;
- reject `{ok: false}` as an error;
- refresh `runtime-manifest` immediately;
- show accepted → queued → running → validation → review → complete states;
- never report completion from the mutation response alone.

This candidate is deliberately narrow. It proves the control seam before asking it to implement the larger conversation-to-feature loop.

**Feature-loop target after the seam works:** Use Kitty and Builder to repair one additional dead Build Work interaction in the running application, with the complete twelve-step acceptance contract in `docs/ACTIVE_MISSION.md`.

## Two-week sequence

### Days 1–2 — live audit and baseline

- Check out the proof branch on Jacob's Mac without disturbing uncommitted work.
- Run supported status/doctor commands and launch Gateway, LiteLLM, Open WebUI, and `kitty-chat`.
- Capture desktop and iPhone-class evidence for Chat and Build Work.
- Read Builder state only through supported CLI/API/database boundaries.
- Exercise the existing mutation endpoint against a disposable or already-failed packet; do not create paid work.
- Record exact blockers and select the final dead interaction.

**Exit gate:** one reproducible broken interaction with source, network, durable-state, and UI evidence.

### Days 2–3 — prototype decision

- Review the standalone prototype in `docs/proof/prototype/index.html`.
- Compare it directly with Open WebUI and current `kitty-chat` for the same project conversation.
- Record Jacob's verdict: prefer, revise once, or fail.

**Exit gate:** Jacob voluntarily chooses the proposed experience for the proof.

### Days 3–5 — repair the control seam

- Fix mutation error semantics and authoritative refresh.
- Mount one contextual, safe control with an approval preview.
- Add focused frontend/backend tests.
- Exercise it in the launched app with services available and unavailable.

**Exit gate:** the UI reflects durable truth after a real action and never shows false success.

### Days 5–7 — conversation-to-job contract

- Define the smallest Mission/result schema needed for one feature.
- Compile it from the conversation and require one meaningful approval.
- Persist it as a durable Builder job without Jacob coordinating a coding agent.
- Record budget, model policy, allowed paths, acceptance commands, and stop rules.

**Exit gate:** an approved conversation creates one inspectable durable job.

### Days 7–11 — execute the real feature

- Let Builder select an available capable worker.
- Make the code change in an isolated branch/worktree.
- Launch the real app and exercise the feature.
- Capture validation evidence and a second-model review.
- Repair findings through the same durable job.

**Exit gate:** the feature works end to end in the running product.

### Days 11–13 — interruption and failover proof

- Restart Kitty during the job or a controlled follow-up.
- Force one worker/provider failure without exceeding the budget.
- Confirm the job, context, evidence, and next action survive.

**Exit gate:** no manual reconstruction or hidden agent coordination.

### Day 14 — verdict

Score only:

- functioning result;
- Jacob intervention required;
- clarity and pleasantness;
- recovery/failover;
- total spend;
- whether Jacob would choose Kitty next time.

Continue or pause according to the mission's pass/failure conditions. Do not negotiate the standard downward because implementation work was substantial.

## Budget ledger

The proof starts at **$0.00 CAD recorded spend**. Source inspection, local deterministic tests, and repository changes do not authorize paid provider calls. Every paid action must record provider/model, purpose, estimated cost, actual cost when available, cumulative spend, and approving event.

## Immediate runtime evidence still required

This branch is intentionally an audit/prototype branch. Before runtime implementation begins, the Mac execution pass must supply:

- exact current checkout SHA and worktree state;
- `./kitty status` and `./kitty doctor --json` outputs;
- service ownership and ports;
- Builder queue summary and one candidate failed/stale packet;
- screenshots/network trace of the dead interaction;
- provider availability without exposing secrets;
- current test/build baseline;
- explicit confirmation that no paid job ran during the audit.
