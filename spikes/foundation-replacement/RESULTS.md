# Foundation spike results

Do not choose a foundation from feature lists. Run the same workflows and attach evidence.

## Candidate status

| Candidate | Reuse model | License gate | Prototype status | Initial observation |
|---|---|---:|---|---|
| Current Kitty + assistant-ui | package-based UI foundation | PASS — MIT | Existing baseline | Maximum product/UI control; Kitty still owns substantial application plumbing. |
| LibreChat | full application fork or thin upstream-tracking fork | PASS — MIT runtime-checked | **Boot verified in CI** against a Kitty-compatible Gateway | Broad multi-provider/agent surface, but brings MongoDB, MeiliSearch, RAG services, auth, and strong app assumptions. |
| AnythingLLM | full application fork or thin upstream-tracking fork | PASS — MIT runtime-checked | **Boot verified in CI** against a Kitty-compatible Gateway | Strong workspace, document, memory, routing, agent, and scheduled-task concepts; fit with Kitty's project model must be tested. |
| Open WebUI | none | FAIL for this project rule | Excluded | Current custom license is not accepted as a rebrandable Kitty foundation. No source is copied or fetched. |

## Prototype boot evidence

GitHub Actions run `30335640205` launched both pinned candidates through the checked-in bootstrap against a mock Gateway exposing Kitty's `/health` and `/v1/models` compatibility surface. Both application home pages returned successfully, container evidence was captured, and the stacks shut down cleanly.

The first AnythingLLM attempt exposed a real portability bug: its SQLite storage bind mount was not writable when the image's default UID differed from the host. The bootstrap now writes the host UID/GID into the disposable candidate environment and creates the required storage directories before launch. The corrected AnythingLLM boot then passed.

This proves that the launch/configuration path works. It does **not** yet prove product fit, personal continuity, real model calls, tool permissions, mobile UX, or upstream maintenance cost. Those require the shared workflows below against Jacob's real Kitty instance.

## Shared test contract

Use one real project and the same prompts/data in all candidates. Recommended first project: the Disability Tax Credit application.

### Workflow A — personal continuity

1. Start a new conversation with no manual context paste.
2. Ask: `What are we currently trying to accomplish with my disability tax credit application, where did we leave off, and what evidence supports that?`
3. Confirm that Kitty's injected context—not candidate-local memory—grounds the answer.
4. Close and reopen the candidate.
5. Resume the project and confirm the current state remains truthful.

Evidence:

- screenshot or recording;
- request/response headers showing Kitty Gateway was used;
- memory/context provenance shown to Jacob;
- any contradictions or missing facts.

### Workflow B — provider independence and zero-dollar survival

1. Continue one conversation through `kitty-default`.
2. Change the underlying provider through Kitty's routing controls without creating a new conversation.
3. Disable paid providers.
4. Confirm Kitty remains usable through an approved free route and visibly reports degraded capability when applicable.

Evidence:

- selected provider/model receipt;
- cost ledger entry;
- conversation continuity before and after switch;
- failure presentation when no route is available.

### Workflow C — project and documents

1. Attach one source document.
2. Associate the conversation and document with the same Kitty project.
3. Ask for a decision or next action grounded in both durable project state and the document.
4. Start another conversation in the same project and verify context is available without indiscriminate full-history injection.

### Workflow D — tool and permission boundary

1. Ask Kitty to research a factual question.
2. Ask it to prepare a calendar change.
3. Confirm reversible research may proceed automatically.
4. Confirm the consequential external change requires Jacob's approval before execution.
5. Confirm the candidate does not introduce a second conflicting permission system.

### Workflow E — mobile and interruption

1. Use a phone-sized viewport.
2. Resume the project in three interactions or fewer.
3. Trigger one earned proactive interruption.
4. Confirm the interruption explains why it appeared and can be dismissed or deferred.

### Workflow F — extension cost

For each candidate, identify the exact files/modules required to add:

- Kitty projects and durable project state;
- memory provenance and correction controls;
- permission receipts;
- proactive interventions;
- Image Lab;
- KittyBuilder status and dispatch;
- provider/cost routing visibility.

Count modifications to upstream files separately from new Kitty-owned extension modules. A smaller diff is not automatically better if the candidate's data model conflicts with Kitty.

## Scoring

Score each category from 0–5 and link evidence.

| Category | Weight | Current Kitty | LibreChat | AnythingLLM |
|---|---:|---:|---:|---:|
| Personal memory and continuity fit | 20 |  |  |  |
| Project/life-management fit | 20 |  |  |  |
| Tools and permission-bound automation | 15 |  |  |  |
| Multi-provider and zero-dollar routing | 15 |  |  |  |
| Image Lab extension path | 10 |  |  |  |
| KittyBuilder integration path | 10 |  |  |  |
| Mobile UX and visual redesign freedom | 5 |  |  |  |
| Upstream maintenance burden | 5 |  |  |  |

Weighted score is evidence, not authority. Record any hard disqualifier separately.

## Hard disqualifiers

- license does not permit Kitty's intended modification/rebranding/distribution;
- candidate requires bypassing Kitty's context, project, permission, or routing layer;
- candidate cannot operate when paid providers are unavailable;
- candidate makes consequential external actions without Kitty's approval boundary;
- acceptable mobile experience requires replacing most of the candidate UI;
- upstream updates cannot be consumed without repeatedly rewriting Kitty-owned behaviour.

## Decision record

**Selected foundation:** pending real-project execution evidence

**Why:** both external candidates now boot, but bootability is not product fit.

**What is retained from current Kitty:** pending

**What is deleted or migrated:** pending

**Rollback path:** the spike is isolated; no candidate replaces the current UI until the decision is accepted and a migration plan passes its own evidence gate.
