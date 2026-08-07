# Architecture Verdict — 2026-08-07

**Scope:** final hostile review of the proposed clean-sheet architecture against the current repository.
**Mission context:** KPROOF-001, approved 2026-08-04, deadline 2026-08-18, budget $25 CAD. Today is day 3 of 14.
**This file dies with the mission.** It is scoped to `docs/proof/` deliberately. Delete it on verdict day. It is not a roadmap and holds no authority over `docs/ROADMAP.md`.

Evidence labels: **VERIFIED** (directly inspected), **INFERENCE** (strongest conclusion from that evidence), **HYPOTHESIS** (needs measurement).

---

## 0. The reason the problem exists

Everything in sections 1–7 is a symptom. This section is the cause. Read it first; the rest is supporting detail.

### The structural fact

**Production is unbounded. Evaluation is one person who cannot read code.**

Agents can generate work faster than Jacob can inspect it, and the one inspection he can perform reliably is *reading prose*. He cannot look at a diff and tell whether it is correct. He can look at a document and tell whether it is coherent.

Any system with unlimited production and a single fixed evaluator fills up with whatever that evaluator is able to accept. Not by anyone's intent — by gradient. Documents always succeed. Documents never fail a test. Documents always look like progress. Working software can fail, and failing is expensive.

So the project produces documents. 443 markdown files, 81,281 lines, against 66,301 lines of Python. That ratio is not a discipline problem. **It is the shape of the incentive.**

### The consequence: nothing in this system can say "no"

Every recurring failure on Jacob's list is the same missing capability — the ability to reject work without him.

| Failure | The rejection that does not exist |
|---|---|
| Architecture churn | Nothing rejects a new architecture document |
| Reviews of reviews | Nothing rejects a review that changes no decision |
| Duplicate work across agents | Nothing rejects a second branch for work already done |
| Trusting persuasive reports | Nothing rejects a confident claim with no evidence |
| Stale state believed | Nothing rejects a handoff whose facts have expired |
| Token overspend | Nothing rejects re-reading 20,000 lines of prose |

And at the code level, the identical pathology: **VERIFIED** — `/builder/action` returns HTTP 200 carrying `{ok: false}` when the action failed. The software cannot reject its own failure either. This is the same disease one layer down.

### The proof: even the enforcement is prose

**VERIFIED.** `gateway/context_receipt.py:1045` runs a check named `docs:duplicate_authority_claims` — built specifically to stop competing authority documents. It scans `_CLAIM_SCAN_PATHS`, which is exactly four files: `AGENTS.md`, `CLAUDE.md`, `START_HERE.md`, `docs/PROJECT_STATUS.md`. It reads their **text** for phrases matching `_DUPLICATE_AUTHORITY_PATTERNS`.

It never inspects the filesystem. It cannot see `ROADMAP_V2.md`. It cannot see `KITTY_MASTER_PROGRAM.md`. It cannot see that two ADRs are numbered 0028 or that two share the title `open-webui-shell-boundary`. All of those landed while this check reported **PASS**.

**The guard against document sprawl is a document-reader.** It validates the map and never looks at the territory. When prose is the only thing anyone can evaluate, even the enforcement mechanism becomes prose-inspection.

### Why every previous fix failed

Every response to every failure has been to **write a rule**: 37 ADRs, a 418-line Constitution, a 224-line `AGENTS.md`, 10 non-negotiables in `CLAUDE.md`, an Authority Map, a Capability Manifest.

Check them against reality:

- ADR 0020 requires one canonical roadmap. Four roadmap-class documents exist.
- Non-negotiable #1 is "Fail loud. No swallowed exceptions, fake defaults." The action endpoint returns success on failure.
- ADR 0035 requires browser-verified evidence. The mission's Days 1–2 evidence gate has no commits.

**A rule that is not executable is a wish.** The project's entire immune response has been to write wishes, which is itself the disease: writing is the only move the evaluator can score, so the system writes even when the correct move is to build.

**VERIFIED — the single hardest piece of evidence:** the `main` branch reports `protected: false`. Branch protection is the one mechanism in this entire stack that can reject work without Jacob reading anything, and it is switched off. It has been sitting on the open-decisions list as "Gate 0 prevention mechanisms — defined, not enforced — needs Jacob's GitHub admin." Meanwhile nine more ADRs were ratified.

The project wrote 37 rules and turned off the one enforcer.

### What actually has to change

Not "fewer documents." Not "more discipline." Not another guardrail on a symptom.

**Build the ability to reject, and make the rejection test one Jacob can confirm himself in five seconds.**

The only judgment a non-coder can make with total confidence is *did the thing do the thing*. So that becomes the sole definition of done. Documents are not banned — they are made **worthless**, because they cannot produce that evidence. That inverts the gradient. Writing stops being the cheapest path to "done."

This reframes the product. **KittyBuilder is not valuable because it runs workers** — workers are a commodity, Claude Code already runs. It is valuable if and only if it can *reject its own output*. Delegation without rejection does not reduce Jacob's load; it multiplies unverified work, which is precisely what 150 branches, 22 open pull requests and 45 initiative files already are.

The product is not conversation-to-code. **The product is a machine that can tell Jacob no.**

Three consequences, in order of cost:

1. **Turn on branch protection.** Two minutes in GitHub settings. Every other control is theatre until the merge boundary can reject. Cheapest possible fix, longest outstanding.
2. **Change the definition of done to a working demonstration.** Nothing merges on the strength of a description. This is what the first slice tests.
3. **Cut to one lane.** Unbounded production against fixed evaluation produces inventory, not output. Parallelism is only valuable up to the rate work can be verified, and that rate is currently one human who cannot read code.

One thing here is not solvable in software, and it should be named plainly: **no mechanism can stop Jacob from opening a chat window and asking for another architecture review.** That is the one behaviour only he can end.

---

## 1. Verdict

### A — the foundation is sound enough. Stop planning. Build.

It has been sound enough since 2026-08-04. The proof audit written that day already picked the proving seam, the exit gates, the preserve/repair/replace lists, and the budget ledger. It is a good document. It was not executed.

Nothing in the proposed clean-sheet review changes the first implementation step. That is the test for whether a review was worth running, and it fails it.

The binding constraint is not architecture quality. It is that planning output keeps replacing execution.

**VERIFIED — what happened during days 1–3 of an approved 14-day proof:**

| Measure | Value |
|---|---|
| Commits toward the Days 1–2 exit gate ("one reproducible broken interaction with evidence") | 0 |
| New files under `docs/` since 2026-08-01 | 286 |
| Markdown lines added since 2026-08-01 | ~19,957 |
| Python lines added since 2026-08-01 | ~7,371 |
| ADRs ratified 2026-08-05 | 9 (0028–0036) |
| New planning documents committed 2026-08-05 | `ROADMAP_V2.md` (16 KB), `KITTY_MASTER_PROGRAM.md` (59 KB), `CONSTITUTION.md` (18 KB), `CAPABILITY_MANIFEST.md`, `BUILDER_V2.md`, `BUILDER_ORGANIZATION.md` |
| Open PR opened 2026-08-07 06:14 UTC | #434 "docs: ratify architecture governance (12 adjudicated decisions)" |

**VERIFIED — ratified decisions violated within days of ratification:**

- ADR 0020 (2026-07-26) establishes one canonical roadmap. `CLAUDE.md` repeats it: "`docs/ROADMAP.md` is the only active roadmap." `docs/ROADMAP_V2.md` was committed 2026-08-05.
- Two ADRs are numbered **0028** (`commodity-software-precedence`, `paa-reference-profile`).
- Two ADRs share the title **`open-webui-shell-boundary`** (0027 and 0033).

**INFERENCE:** the ADR set has stopped being a decision record and become an artifact stream. A decision record that duplicates its own numbers is no longer arbitrating anything.

**VERIFIED — the whole repository:** 66,301 lines of Python in `gateway/`, against 81,281 lines of markdown across 443 files, 414 of them under `docs/`. There is more prose than code.

**Why not verdict B:** issuing "correct these three things first" would itself become another week of planning. The one correction below is a deletion and a wiring job, not a design decision.

---

## 2. What the previous review got right

Only the load-bearing ones.

1. **Do not build a primary frontend.** Correct, and already proven the expensive way — `gateway/kitty-chat/` is 22,312 lines of TypeScript across 61 components and is not the product.
2. **Builder should be deterministic; workers ephemeral.** Correct, and already true in code: `gateway/builder_adapters.py` is a subprocess seam over replaceable backends.
3. **SQLite + Git + files, not an infrastructure stack.** Correct and already the case.
4. **Budget must be enforced before dispatch.** Correct — it is the only enforcement point that exists.
5. **Do not migrate to Open Brain / Ringer / Open Engine.** Correct, and already settled in ADR 0031 on 2026-08-05.

**INFERENCE — and this is the finding:** five of the review's main conclusions were already decided in the repository before the review ran. Re-deriving settled decisions is the churn mechanism itself. The review is a symptom of the disease it diagnoses.

---

## 3. What it got wrong, or failed to challenge hard enough

### 3.1 It proposed Mission as the Kitty→Builder boundary without checking whether Mission exists. It does not.

**VERIFIED.** The word `mission` appears 32 times in `gateway/**/*.py` (excluding *permission/submission/commission*). Every occurrence is either an unrelated comment (`paths.py`, `personality.py`) or lives in `gateway/context_receipt.py`, which parses the JSON comment inside `docs/ACTIVE_MISSION.md` and checks that its `base_sha` is an ancestor of HEAD.

That is a **document linter**. There is no `gateway/mission.py`, no `gateway/routes/mission.py`, no mission table.

ADR 0017 declares the Kitty → Mission → KittyBuilder boundary, and the 2026-08-05 decision summary lists it under "Immutable Decisions — do not reopen without extraordinary evidence."

**INFERENCE:** the architecture's central boundary is a markdown file with a JSON comment in it, protected by an immutability clause. Both the current architecture and the proposed one are built on top of a document.

### 3.2 It never asked how work actually enters Builder. That omission hides the entire problem.

**VERIFIED.** `apply_manifest()` in `gateway/builder_initiative.py:689` is the sole ingestion path into the Builder queue. Its only non-test caller in the repository is `gateway/builder_cli.py:1131`. There are 45 hand-authored files in `docs/initiatives/`.

So the real chain today is:

```
Jacob → talks to ChatGPT/Claude/Codex → that chat writes a JSON manifest into docs/initiatives/
      → Jacob opens a terminal → Jacob runs the CLI → Builder queue
```

**19,607 lines of Builder control plane, and its only input is Jacob at a terminal holding a file another chat wrote.**

Jacob is the message bus *by construction*, not by bad habit. No component in the proposed architecture removes that step — it renames it "Mission compilation" and leaves the authoring outside the system. This is the one thing worth building, and the review walked past it.

### 3.3 "Simplify Mission/Initiative/Packet/Task/Attempt/Run" understates the risk — the proposal adds levels.

**VERIFIED.** `gateway/builder_queue_db.py` already defines `tasks`, `events`, `pr_links`, `runs`, `branch_leases`; `builder_initiative.py` adds initiatives and packets. Adding *Mission* and *Job* as new concepts makes seven levels, not five.

**Decision:** Mission maps onto the existing `initiatives` row. Job maps onto the existing `tasks` row. No new nouns, no new tables.

### 3.4 It treated the shell question as open. It has been decided twice and contradicts itself.

See the duplicate ADR titles in §1. The proposal re-litigates Open WebUI vs. custom frontend as though it were undecided. It is decided; what is missing is deletion of the losing branch, not another decision.

**The real question the review should have asked is not React vs. Open WebUI.** It is: *who maintains it.* React is not the problem. Owning 22,312 lines of frontend alone for five years is the problem.

### 3.5 "Deterministic verification separated from semantic model review" — right principle, wrong worry, and the repo is already over-supplied.

**VERIFIED — five review mechanisms already exist:** `gateway/self_review.py`, `scripts/pr_review.py`, `scripts/ops/reviewer.py`, `scripts/kittybuilder_opencode_reviewer.sh`, `gateway/kitty-chat/scripts/swarm-review.ts`.

Adding a sixth reviewer does not solve "one model certifies another model's plausible mistake." Nothing model-shaped solves that. The only verification Jacob can personally audit is **did the running application do the thing** — a launched app and a screenshot. That is already ADR 0035. Use it; do not build another reviewer.

### 3.6 It did not challenge whether Builder should exist at this scope. Here is that challenge.

**VERIFIED.** 17 `kittybuilder/kb_*` branches exist on GitHub. Exactly one produced a merged pull request (#407). **HYPOTHESIS:** Builder dispatches reliably but rarely lands — needs measurement across the proof window, not assertion.

**Keep:** the queue, leases, attempts, runner, adapters. That machinery is what makes work survive a restart without chat history, which is the actual product claim and the one thing a plain agent loop cannot do.

**Freeze — do not extend during the proof:** `builder_status.py` (1,470 lines), `builder_report.py`, `builder_brief.py`, `builder_doctor.py` — roughly 2,700 lines of operator-facing reporting built for an operator role Jacob has explicitly said he does not want to occupy.

---

## 4. Jacob as an architectural constraint

| # | Constraint (all VERIFIED unless noted) | Answer |
|---|---|---|
| 1 | **He is the message bus because the software makes him one.** The only path into Builder is a CLI command against a hand-written JSON file (§3.2). | **Architecture.** Kitty writes the job row itself, in code, from the conversation. This is the single change that matters. |
| 2 | **Documents multiply faster than code and outrank it in practice.** 443 markdown files / 81,281 lines vs 66,301 lines of Python; 286 new doc files in six days. | **Stop doing it + guardrail.** During an approved mission window, no new file under `docs/` except evidence. A CI check, not willpower. |
| 3 | **Architecture reviews interrupt approved missions.** This review is the fourth planning artifact inside three days of a fourteen-day proof. | **Stop doing it.** A mission with a deadline cannot be interrupted by a review. Reviews wait for verdict day. |
| 4 | **Parallel agents duplicate work silently.** `codex/review-and-plan`, `codex/eeview-and-plan` and `jacob202/fix-gi` all point at the same SHA `fbd69242`; `codex/review-ans-pla` is a fourth variant. Also `feat/` + `feature/runpod-image-studio-smoke`, `spike/foundation-replacement-2026-07-27` + `-clean-2026-07-27`, `docs/repository-navigation-refresh` + `-2026-07-28`, and a branch named `mai` beside `main`. | **Guardrail.** One queue is the only place work starts. No queue row, no branch. |
| 5 | **He cannot audit AI-written code, so the system must never require it.** | **Architecture.** He verifies product behaviour, never diffs. A completion claim without a run ID and a journey result is not a completion claim. |
| 6 | **Two files hold one truth.** `.claude/STATE.md` and `.claude/HANDOFF.md` carry byte-identical JSON payloads (verified equal). | **Guardrail.** Delete one. Two copies of one fact always drift; that drift is what makes handoffs lie. |
| 7 | **Typos become durable artifacts because nothing rejects them.** A zero-byte file named `main` is committed at the repository root — a shell redirect typo, tracked in git since PR #311. | **Guardrail.** Cheap CI check for junk at root. Trivial in itself; it is the visible tip of item 4. |

**Note on item 3:** the honest reading is that architecture work has become the more comfortable activity. It always produces something that looks like progress and never produces a failure. Shipping produces failures. That asymmetry is the actual engine of the loop, and no software fixes it — only the rule fixes it.

---

## 5. Simplest architecture I would actually maintain

```
Jacob
  │  talks
  ▼
Open WebUI ─────────────── bought. replaceable. Jacob maintains none of it.
  │
  ▼
Kitty  (gateway/)  ─────── conversation, judgment, continuity.
  │                        WRITES THE JOB ROW IN CODE. ← the only new work
  ▼
SQLite: initiatives + tasks ── existing tables. Mission = initiative row.
  │                                              Job = task row. No new nouns.
  ▼
builder_loop  ──────────── existing. leases, attempts, retries, recovery.
  │
  ▼
worker (subprocess) ────── existing builder_adapters.py. ephemeral.
  │                        Claude Code / Codex / OpenCode / local — swappable.
  ▼
verification ───────────── narrow tests + launch the app + exercise the feature.
  │                        deterministic. no model certifies anything.
  ▼
evidence row + run ID
  │
  ▼
Kitty reports in plain language, citing the run ID.
```

**Removed from the proposal, and why:**

| Proposed component | Verdict |
|---|---|
| Mission as a document/artifact | **Delete.** It becomes a database row. A document cannot be a control-plane boundary. |
| Job as a new concept | **Delete.** It is the existing `tasks` row. |
| Per-job context compilation | **Park.** Solves a problem Jacob does not have at one user and one repo. |
| Repo indexing | **Park.** Same. |
| Spend reservation subsystem | **Delete as new work.** `gateway/compute_governor.py` already exists (696 lines). Wire it at dispatch; do not rebuild it. |
| Second-model reviewer as a component | **Delete.** Five already exist (§3.5). |
| kitty-chat as the product surface | **Delete from the product path.** Keep as a debug tool. |

Net new code required by this architecture: **one path from conversation to a queue row.** Everything else already exists.

---

## 6. Decisions

### DECIDED — do not reopen without new runtime evidence

1. Open WebUI is the shell. `kitty-chat` is a debug tool, not the product. (ADR 0027/0033)
2. Gateway is the product. (ADR 0003)
3. Builder's queue / lease / attempt / runner core stays. Do not rewrite, do not migrate. (ADR 0031, and the 2026-08-04 Preserve list)
4. SQLite + Git + files. No infrastructure stack.
5. No migration to Open Brain / Ringer / Open Engine. (ADR 0031)
6. **Mission and Job introduce no new tables.** Mission = `initiatives` row. Job = `tasks` row.
7. The verification that counts is the running application, not code review. (ADR 0035)
8. KPROOF-001 stands as approved. Its scope, deadline and $25 ceiling are not renegotiated because a review had opinions.

### MUST DECIDE BEFORE BUILDING — one

**Where does the first slice's conversation happen: Open WebUI, or `kitty-chat`?**

They conflict today. The 2026-08-04 audit's chosen seam is a button inside `kitty-chat`'s Builder inspector. ADR 0027/0033 say Open WebUI is the shell. This decides which file gets opened first, so it cannot be parked.

**My pick: Open WebUI, through the existing bounded tool server.**

Reason: mounting a control in a client already decided not to be the product is wasted motion, and a button does not test the architecture — Jacob still has to find the packet himself. The conversational path is the only thing that removes him as the message bus. Veto it if you disagree, but decide today, not after another investigation.

### CAN WAIT — parked, explicitly

- Vector store choice (SQLite-vec vs Chroma); mem0 removal path.
- Which of the 61 `kitty-chat` components survive as a console.
- Builder reporting surfaces (~2,700 lines) — frozen, revisit after the proof.
- The eight "suspicious wired modules" audit (`prefetcher`, `inbox_watcher`, `insight_loop`, `life_awareness`, `telegram_bot`, `antigravity_tools`, `web_tracker`, `self_review`).
- Repo indexing and per-job context compilation.
- Collapsing initiative / packet / task / run / attempt into fewer levels.
- Doc consolidation from 443 files. **Do this on verdict day, not now** — it is the most seductive available substitute for shipping.

---

## 7. First build slice

Already chosen on 2026-08-04. Confirmed here with one change: **make it spoken, not clicked.**

### "Retry that failed work"

1. Jacob, in Open WebUI: *"that thing that failed last night — try it again."*
2. Kitty resolves which packet, then states in plain English what it will do, what it will cost, and what it will not touch.
3. Jacob says yes in the chat. That approval is the only gate.
4. **Kitty writes the action through the existing action queue — in code.** No JSON file. No terminal.
5. Builder executes it using the existing lease / attempt / retry path.
6. Deterministic verification: the narrow tests covering that packet, plus the app launches and the interaction works.
7. Kitty reports back: passed or failed, with the run ID and the actual spend.

**Defects this slice must fix — all VERIFIED on 2026-08-04 and still present:**

- `/builder/action` returns HTTP 200 carrying `{ok: false, error: ...}` on failure. A failed action currently reads as a success. This is the fail-loud violation that matters most, because it is the exact mechanism by which Jacob would be told something worked when it did not.
- `useBuilderAction()` invalidates the query key `['runtime']`; the authoritative projection is cached under `['runtime-manifest', projectId]`. The screen does not refresh from durable state after an action.
- No conversational path into the action queue exists. **This is the new code, and it is small.**

**Requires:** no new platform, no new tables, no new nouns, no new reviewer.

### Test the "no" path first

Per §0, the thing under test is not delegation. It is **rejection**. So the acceptance order is inverted from the usual:

1. **Break it on purpose first.** Point the retry at work that cannot succeed. Kitty must come back and say *it failed, here is why, here is the run ID*. If it reports success, or reports nothing, the architecture is dead and no amount of happy-path polish redeems it.
2. **Only then run the passing case.**

A system that cannot report its own failure is worse than no system, because it converts Jacob's remaining ability to verify — noticing something is broken — into false confidence. That is the `{ok: false}` bug generalised, and it is the single defect most worth fixing in the entire repository.

**Passes only if:** Jacob never opens a terminal, never edits a JSON file, sees an honest failure before he sees a success, and can tell from the chat alone which one he got — then confirms it in the running app.

### Before any of this: turn on branch protection

Two minutes of GitHub settings, and it is the only change here that Jacob must make himself. Require the existing checks on `main`. Until the merge boundary can reject work, every other control in this document is advisory, and the project keeps merging descriptions of software.

---

## Final hostile check on this review

- **Am I adding complexity because it sounds sophisticated?** No. Net new components: zero. Net new code: one conversation-to-queue path.
- **Am I protecting work already built?** Partly, and I should name it. Keeping 19,607 lines of Builder is a real bet. The honest defence is narrow: the queue/lease/attempt core is what lets work survive a restart with no chat history, and that is the product claim. The reporting layer has no such defence, which is why I froze it rather than praised it.
- **Am I assuming Jacob can supervise what he cannot audit?** No. Verification is product behaviour, never diffs.
- **Am I solving a human problem with software?** Checked twice. Items 2, 3 and 7 in §4 are rules and deletions, not systems.
- **Am I asking him to remember a rule software could enforce?** Items 2, 4, 6 and 7 get cheap CI checks so they do not depend on memory.
- **Am I proposing another planning phase?** No. Verdict A, one decision, one slice, already-approved mission.
- **What would I delete if I maintained Kitty alone for five years?** 400+ of the 443 markdown files; `ROADMAP_V2`, `KITTY_MASTER_PROGRAM`, `CONSTITUTION`, `BUILDER_V2`; the ~2,700-line Builder reporting layer; four of the five review mechanisms; `kitty-chat` as a product surface; one of `STATE.md`/`HANDOFF.md`; and this file.

**Revision made after that check:** the first draft of §7 kept the audit's original UI-button seam as a safer preliminary step. I removed it. It is a subset of the same action-queue call, it lives in a client already ruled out of the product path, and it would consume days of the proof window without testing the thing under test.
