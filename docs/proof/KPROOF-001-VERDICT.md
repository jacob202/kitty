# KPROOF-001 — Verdict

**Mission:** KPROOF-001 — Two-Week Builder Proof (`docs/ACTIVE_MISSION.md`)
**Proof window:** 2026-08-04 → 2026-08-18
**Verdict rendered:** 2026-08-21
**Verdict:** **FAIL against the acceptance contract.**
**Evidence base:** repository history and GitHub PR state on `main` @ `5c96bc317fa004f9d438277fcb1d3dec85165dcf`.

The mission's own rule governs this document: *"Runtime behavior outranks
documentation, tests, commits, and agent claims,"* and *"If the proof fails by
2026-08-18, pause Kitty for several months and preserve the evidence rather
than negotiating the standard downward."* Nothing below is softened to reach a
kinder result, and nothing is called a failure without a citation.

## Pass condition, scored

The contract requires **all four**. Two are unmet on evidence, one is unmet for
lack of any evidence either way, and one is Jacob's to confirm.

| # | Pass requirement | Result | Basis |
|---|---|---|---|
| 1 | Builder completes one real feature loop | **NOT MET** | The only deliberate end-to-end run stopped at step 5 of 12. Four Builder PRs merged, none carrying a full loop. |
| 2 | The result works in the launched application | **NOT MET** | No Builder-merged change was user-facing, and none records a launched-app check. |
| 3 | The experience is pleasant, fast, clear, understandable | **UNSCORED** | Prototype exists; no record of Jacob's assessment. |
| 4 | Jacob would voluntarily choose Kitty over direct ChatGPT/Claude | **NOT MET on behaviour** | Every PR opened since the deadline came from a direct AI coding session, none from Builder. Jacob's confirmation still governs. |

## What Builder genuinely did

This is real and should not be lost in the failure.

Four pull requests merged in the window from Builder-owned
`kittybuilder/kb_*` branches, each showing a working chain of
packet → isolated worktree → worker writing code and tests → validation
commands → automated review → pre-push gate → published PR:

| PR | Date | Change | Size |
|---|---|---|---|
| [#484](https://github.com/jacob202/kitty/pull/484) | 2026-08-13 | `KVERSION-007` — truthful `GET /version` endpoint | +34, 3 files |
| [#499](https://github.com/jacob202/kitty/pull/499) | 2026-08-15 | Builder supervisor + Claude adapter | +1945, 8 files |
| [#500](https://github.com/jacob202/kitty/pull/500) | 2026-08-15 | Supervisor review-finding repairs | +282 −128, 6 files |
| [#516](https://github.com/jacob202/kitty/pull/516) | 2026-08-17 | `b5-paid-route-cost-source-fix` — price the configured models, fail closed | +74 −8, 2 files |

#484 is the cleanest: the KittyBuilder reviewer approved the diff, local
style/type/test gates passed, and it merged six minutes after opening. That
is a machine doing real engineering work, reviewed, on a real branch. It is
evidence the underlying execution plane exists and functions.

## Why it still fails

### F1 — No complete loop was ever run

`docs/session-notes/builder-cycle-proof-2026-08-17.md` is the one deliberate
attempt at the full Phase 3 cycle. Its own conclusion:

> The pipeline ran for real and stopped at a real, identifiable step. It did
> **not** complete a validated cycle.

It cleared six mechanics — queue, lease, worktree provisioning, brief
generation, worker dispatch, attempt exhaustion — then failed the worker
contract: *"worker did not write a implementation result to
.../implementation.json."* Validation never ran (`validation_json` is `null` on
both attempts). Independent review, recovery, and publication were never
reached. The run used a stub worker (`["true"]`) because the container held no
provider credentials.

Phase 3 requires twelve steps. The best-documented run reached five.

### F2 — Nothing was validated in the launched application

Pass-condition 2 and Phase 3 steps 8–9 require Builder to launch the real
application and exercise the requested behavior. No Builder-merged change did:

- #484 is a JSON version endpoint — no user-facing surface;
- #516 states it outright: *"Not user-facing... backend-only — KittyBuilder
  paid-route cost budgeting and tests; no UI or user workflow touched"*;
- #499/#500 modify Builder's own supervisor and adapter.

Every one carries passing tests. Under the mission's own precedence rule,
passing tests are not the application working.

### F3 — The loop never started from a conversation

Phase 3 steps 1–4 require a conversation with Kitty to produce an approved
result contract that becomes a durable job. The packets that shipped
(`KVERSION-007`, `b5-paid-route-cost-source-fix`) are engineering-named packets
authored as packets. No artifact records a conversation, a desired outcome
defined with Jacob, or an approval of a result contract. `docs/PROJECT_STATUS.md`
still lists as a known unknown *"that an approved conversation can currently
create a durable Builder job without manual translation."* Nothing in the window
closed it.

### F4 — Recovery was never proven

Roadmap step 6 requires demonstrating that an interruption or worker/provider
failure does not erase the job, context, evidence, or next action.
`docs/PROJECT_STATUS.md` lists *"that Builder context survives a real
worker/provider interruption end to end"* as unverified, and no later evidence
supersedes it. Supervisor recovery *dispatch* was repaired in code
(`5ad920f`, `13c9740`, 2026-08-15) and covered by tests; a repaired code path
with unit tests is not the demonstrated recovery the mission asks for.

### F5 — Supervision stayed constant

The mission states plainly: *"manual agent coordination counts as proof
failure,"* and the failure condition triggers if *"Builder still requires
constant supervision."*

- **53 pull requests merged in the proof window. 4 came from Builder** — 7.5%.
  The rest came from lanes a human opened and steered: 26 `fix/*`, 9 `claude/*`,
  6 `feat/*`, 4 `docs/*`, and 4 others.
- **Every Builder PR was merged by hand by Jacob.** None self-published.
- **#516 required a human to overrule its own reviewer.** The PR carries label
  `review/override-approved` and the body records the override.
- **#499 was merged with review findings still outstanding**, requiring #500 as
  a fix-forward PR the same day — Builder's own description.
- **12 abandoned `kittybuilder/kb_*` branches remain on `origin`**, two of them
  raised inside the window (2026-08-11, 2026-08-13), against 3 task IDs that
  landed.

### F6 — The proof's own scope boundary broke

The non-negotiables forbid adding image generation during the mission. Two
image PRs merged inside the window on 2026-08-17: #517 (Runware PuLID input
images) and #520 (image spend ledger). A proof that cannot hold its own fence
for two weeks is reporting something about the operating discipline around it,
not only about Builder.

### F7 — Post-deadline behaviour answers pass-condition 4

As of this verdict the repository has **10 open pull requests. Zero are
Builder's.** Every one was last touched between 2026-08-19 and 2026-08-21, and
every one comes from a direct AI coding session (`claude/*`, `feat/*`,
`fix/*`) — including the session that produced this document.

Pass-condition 4 asks whether Jacob would voluntarily choose Kitty over opening
ChatGPT or Claude directly for the next project task. For the three days after
the deadline, working on Kitty itself, the choice made was direct tools, every
time. That is behavioural evidence, not a substitute for his own answer, but it
points one way.

## What could not be verified

Stated as unknown rather than assumed, per the mission and `CLAUDE.md`:

- **Spend against the $25 CAD ceiling.** Builder's budget and attempt records
  live under `data/`, which is gitignored (`.gitignore:16`) and exists only on
  Jacob's Mac. Not reachable from a cloud container. Whether the proof stayed
  inside its ceiling is unknown, and unknown is not a pass.
- **Pass-condition 3** (the experience). The Phase 2 prototype exists at
  `docs/proof/prototype/index.html` (2026-08-04). No record shows Jacob
  assessing it against opening ChatGPT or Claude directly.
- **Live Mac runtime state** — services, credentials, provider availability,
  local Builder queue contents.

## The honest shape of this failure

Builder is not broken. It wrote real, tested, reviewed code that merged four
times. The execution plane exists.

What failed is that **the proof the mission actually specified was never run.**
No one carried a conversation through to an approved contract, through Builder,
into the running application, past an independent review, and through a
recovery test. The two weeks went to 49 other pull requests instead — including
image work the mission had explicitly fenced off.

That distinction matters for what happens next, and it is recorded here as
observation, not as an argument for a softer verdict. The contract is scored as
written: **FAIL.**

## Contract consequence

`docs/ACTIVE_MISSION.md` prescribes the outcome:

> Pause Kitty for several months if Builder still requires constant
> supervision, the interface remains frustrating, or Jacob still prefers direct
> tools.
>
> Preserve working integrations, repository history, the prototype, audit, and
> findings.

The first condition is met on evidence (F5). The third is met on behaviour
(F7), pending Jacob's own answer. The pause is Jacob's decision to execute or
override; this document renders the verdict and preserves the evidence.

Nothing in this repository is to be deleted on the strength of this verdict.
