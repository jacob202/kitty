# Kitty Two-Week Proof — Live Mac Audit

**Captured:** 2026-08-04 20:26–20:27 America/Regina  
**Mission:** `KPROOF-001`  
**Evidence archive:** owner-local `artifacts/proof/live-audit/20260804-202624.zip`  
**Spend:** **$0.00 CAD**  
**Verdict:** the system is healthy enough to repair; the next run must use a current isolated checkout before any product defect is patched.

## Evidence standard

- **VERIFIED** — directly observed in the captured terminal, HTTP, database, browser, or repository evidence.
- **INFERENCE** — the narrowest explanation supported by the verified evidence.
- **HYPOTHESIS** — requires another running-app test.

The archive remains owner-local because it contains runtime state and screenshots. This report records the evidence needed for the repository decision without committing personal chats, credentials, databases, or raw logs.

## 1. Checkout and baseline

### VERIFIED

The running checkout was:

- path: `/Users/jacobbrizinski/Projects/kitty`;
- branch: `main`;
- HEAD: `cec062f7f12e48b8d15bab6361b6c61839d6e2eb`;
- remote state: **72 commits behind `origin/main`**;
- dirty state: four entries (`docs/memory-stale.md`, `docs/plans/migration-health.md`, `docs/skill-improvement-queue.md`, and untracked `artifacts/`).

The audit did not reset, stash, checkout, merge, delete, or overwrite this work.

Many historical worktrees are still registered, including Builder packet worktrees and one locked `initializing` worktree. Their existence is evidence of accumulated operating debris, not authorization to remove them.

### Decision

Do not implement from, update, or clean the dirty `main` checkout. Create a separate proof worktree from current `origin/main`, bring the proof branch onto that baseline, and run Kitty from that isolated checkout.

The current `./kitty status` label `freshness: current` means the running build matches the **local** source SHA. It did not warn that the local source was 72 commits behind the remote authority. That distinction may later deserve a trust repair, but it is not the first Builder-loop feature.

## 2. Runtime health

### VERIFIED

All required local surfaces were running:

| Surface | Result |
|---|---:|
| Gateway `/health` | HTTP 200 |
| LiteLLM readiness | HTTP 200 |
| LiteLLM liveliness | HTTP 200 |
| Open WebUI root | HTTP 200 |
| Kitty custom UI root | HTTP 200 |

Gateway `/openapi.json` returned HTTP 401, consistent with the authenticated Gateway boundary rather than an outage.

Open WebUI reported:

- version `0.10.2`;
- healthy process and open port 3000;
- Gateway ready with five models;
- `kitty-auto` present.

The audit did not send a chat turn, model request, image request, hosted-provider request, or GPU request.

### VERIFIED — deterministic baseline

- focused backend tests: **16 passed**, one dependency deprecation warning;
- `BuilderSurface` frontend tests: **19 passed**;
- Builder SQLite `PRAGMA integrity_check`: **ok**;
- browser capture completed on desktop and 393×852 phone viewports;
- no horizontal overflow was observed on either captured viewport.

## 3. Builder state

### VERIFIED

The authoritative queue contained 107 tasks:

| State | Count |
|---|---:|
| queued | 3 |
| claimed | 0 |
| running | 0 |
| blocked | 9 |
| PR opened | 0 |
| awaiting review | 0 |
| done | 51 |
| failed | 1 |
| cancelled | 43 |

The runtime projection contained 31 initiatives and was marked `degraded` because it included **two partial packet records**.

The newest queue backup was approximately 3.2 days old. A backup is required before the proof mutates queue state.

The three queued high-value packets were:

1. `B10-ui-cli-agreement` — prove UI/CLI agreement;
2. `B9-restart-recovery` — prove restart recovery;
3. `B8-clean-checkout-mission` — prove one clean-checkout queue → worker → validation → independent review → draft PR loop.

`B8-clean-checkout-mission` is the closest existing packet to the final proof contract. It is not the first disposable control-seam exercise because it creates branches, commits, review evidence, checks, and a draft PR.

The smallest existing recovery candidate is `P1S-hello`, a blocked smoke packet whose only allowed output is `data/smoke/hello.txt`. It remains historical Builder evidence and must not be requeued until the current-baseline UI and action semantics are verified.

### Decision

Preserve the queue and its history. Do not bulk-delete, reset, or rewrite old records during the proof. Filter historical machinery out of the primary experience rather than destroying evidence.

## 4. Running interface evidence

### VERIFIED — navigation and layout

The desktop and phone interfaces both loaded, and the browser could navigate from Home to Work through the visible `Work` control. The mobile shell remained usable at 393×852 with its primary navigation visible.

### VERIFIED — the primary experience is not trustworthy yet

The Home screen led with internal system warnings, including:

- Telegram configuration;
- Mem0 initialization;
- a stale codegraph daemon;
- incomplete Builder transition history;
- a Builder card labelled `partial data`.

The Work screen mixed ordinary personal work with Builder internals. It prominently reported **“55 builder packets need attention”**, then exposed old packet titles, failure classes, attempt counts, packet identifiers, budget exhaustion, and test/recovery fixtures.

That presentation does not answer the user-level questions required by the proof:

- What is Kitty doing for me now?
- Why is it doing that?
- What happens next?
- What decision, if any, do you need from me?
- What working result has actually been verified?

No contextual primary recovery action was visible on the captured failed Work items. The current product therefore acts mainly as an inspector of accumulated machinery, not an operator carrying one approved request to completion.

### INFERENCE

The queue itself is not the central product problem. The primary problem is projection and control: historical and control-plane detail is promoted into the default user surface while the next safe action is absent or unclear.

This supports the original repair direction: keep durable Builder truth, but place a narrow user-language control and progress contract in front of it.

## 5. Browser/network errors

### VERIFIED

Both desktop and phone captures recorded three HTTP 404 responses:

- `/proxy/projects/3/next`;
- `/proxy/projects/4/next`;
- `/proxy/projects/5/next`.

They also recorded one aborted request to `/proxy/health`.

### VERIFIED — newer repository source differs

Current remote `main` contains a project-next route at `/projects/{project_id}/next`, while the running local checkout was 72 commits behind current remote `main`.

### Primary hypothesis

The project-next 404s are caused by version skew between the old running Gateway and newer UI expectations or by a route that landed after local HEAD. This is more likely than three independently broken project records.

### Required falsification test

Run the same browser capture from a current isolated `origin/main` baseline. Only if the same 404s reproduce there should production code be changed.

The aborted `/proxy/health` request is not yet a proven product defect. The supported unauthenticated health boundary is Gateway `/health`; earlier repository work already corrected a separate trust-harness assumption that `/proxy/health` existed.

## 6. Doctor result

### VERIFIED

`./kitty doctor --json` returned:

- 32 pass;
- 10 warn;
- 2 fail.

The two failures were continuity/checkpoint claims that still treated merged PR #384 as active. Optional integrations such as Telegram, push, mail, and Mem0 appeared as warnings and are not blockers for the Builder proof.

### INFERENCE

The doctor result does not indicate that Gateway, routing, Open WebUI, Kitty Chat, or the Builder database is down. It indicates stale operating metadata plus optional integration gaps.

## 7. Root-cause decision

The live audit changes the implementation order.

Do **not** begin by patching the three 404s, mounting every dormant Builder control, cleaning the queue, or redesigning Work. The audit was run against an old dirty checkout, so those would be symptom-first changes.

The next sequence is:

1. back up the Builder queue;
2. create an isolated worktree from current `origin/main` without touching dirty `main`;
3. integrate the proof branch into that worktree;
4. launch Gateway, LiteLLM, and Kitty Chat from the isolated current baseline;
5. repeat the desktop/phone/browser-network capture;
6. confirm which defects survive the current baseline;
7. write a failing focused test for the first surviving control-seam defect;
8. make one minimal repair;
9. verify it in the running app before creating a durable job.

## 8. First repair boundary after baseline refresh

The current candidate remains one truthful contextual recovery action, but its exact implementation is gated by the current-baseline rerun.

The action must:

- be shown only for a selected recoverable failed/stale item;
- explain the intended state transition before approval;
- use the existing action queue;
- reject application payloads with `ok: false` as errors even when HTTP transport succeeded;
- invalidate the authoritative `runtime-manifest` cache immediately;
- derive accepted, queued, running, validation, review, and completion state from durable Builder truth;
- never claim completion from the mutation response alone;
- keep packet IDs, leases, provider mechanics, and attempt accounting behind optional evidence details.

## 9. Proof packet order

After the control seam works on a disposable bounded packet:

1. **B8** is the real end-to-end feature-loop proof: clean checkout, worker, validation, independent review, draft PR, checks, honest terminal state, and no manual coordination after initial approval.
2. **B9** is the interruption/recovery proof.
3. **B10** is the UI/CLI agreement proof.

This order maps directly to the two-week mission and avoids inventing a second orchestration system.

## 10. Gate status

The live Mac audit gate is **complete**.

What is proven:

- the core services run;
- the custom interface is reachable on desktop and phone;
- the Builder database is intact and inspectable;
- focused tests pass;
- the current user experience exposes operational debris instead of carrying one request forward;
- the running checkout is too stale and dirty to serve as the implementation baseline;
- no paid work occurred.

What is not yet proven:

- that the same network errors survive current `main`;
- that a UI recovery action mutates durable state truthfully;
- that conversation can compile one approved durable job;
- that Builder can finish B8 without Jacob coordinating agents;
- that restart/provider failure preserves the job;
- that Jacob prefers the resulting experience to using ChatGPT or Claude directly.
