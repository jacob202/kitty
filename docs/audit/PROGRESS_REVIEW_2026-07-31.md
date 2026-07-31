# Progress review — planning horizon, checkpoints, and verified reality

**Written:** 2026-07-31
**Verified against:** `origin/main` @ `aae7577`, GitHub Actions runs on `main`,
`./kitty context --agent`
**Question answered:** how far ahead have we actually planned, what are the
checkpoints, where are we on them, and what is genuinely proven to work?

Evidence rule used throughout: a thing is **verified** only if a command ran and
its output was read. Repository prose is a claim, not evidence. Where the only
available evidence is prose, this document says so.

---

## 1. How far the plan actually reaches

Short answer: **one phase, roughly a week wide. Everything past it is a bullet
list.**

`docs/ROADMAP.md` is the sole planning authority (ADR 0020). It contains:

| Horizon | What exists | Depth |
|---|---|---|
| Phase 1 — trust foundation | 7 ordered outcomes, 7 exit criteria, a named restart sequence (KTF-001) | Fully specified, executable |
| Phase 2 | **Nothing.** No section, no outcomes, no exit criteria | Does not exist |
| Later phases | 6 bullet lines (worker contracts, runtime projections, autonomy, product deepening, Image Studio direction) | Named only. No order, no owner, no exit criteria |
| "Done" | `docs/NORTH_STAR.md` §6 — a morning ritual that holds | Qualitative, deliberately not a checklist |

So the planning horizon is: **detailed for one phase that is now claimed
complete, and undefined for everything after it.** That is the headline finding.

### The Phase 2 contradiction

`docs/ACTIVE_MISSION.md` declares mission `KLF-001`, titled *"Phase 2 Life-First
Home Truth"*, status `running`, approved by Jacob 2026-07-31T11:29Z.

`docs/ROADMAP.md` contains no Phase 2. Grep confirms the string appears nowhere
in the roadmap or the authority map.

Phase 1's own exit criteria require that *"no active authority files contradict
the roadmap or active mission."* An active mission naming a phase the roadmap
does not define is exactly that contradiction. The work KLF-001 did is good and
correct — the problem is that it has no sequence to sit inside.

---

## 2. The checkpoint ladder as actually written

These live in three different files and were written at three different times.
Collected here for the first time:

**Checkpoint 1 — Move-in day** (`docs/packets/README.md`, D12, decided
2026-07-04). Five conditions, all product-facing:

1. Morning brief lands on the iPhone unprompted, with real mail and deadlines
2. Every active project shows one concrete next step
3. Benefits/admin paper is watched — photograph a letter, deadline escalates
4. Capture resurfaces at the right moment
5. Everything Kitty did is an auditable queue row; nothing sent without approval

Marked **reached 2026-07-05** on the strength of Waves 0–4 completing.

**Checkpoint 2 — Phase 1 exit** (`docs/ROADMAP.md`). Seven criteria:

- Python and frontend CI green from a clean checkout
- No active authority file contradicts the roadmap or mission
- Builder has ≥2 verified `free-exec` packets
- One unattended daylight run crosses packet failure and provider exhaustion
- One low-risk packet completes the full approved delivery path
- One real project completes the resume-loop proof end to end
- Status reconstructable from evidence without chat history

Marked **exited 2026-07-31** by `.claude/STATE.md` ("KTF-001 succeeded: all 9
scope items independently verified; Phase 1 exits").

**Checkpoint 3 — Phase 2.** Undefined.

**Checkpoint 4 — Later phases.** Six unordered bullets.

**Checkpoint 5 — North Star "done."** Mornings Jacob *wants* to open Kitty.

### Where we actually stand on Checkpoint 2

Two of the seven exit criteria are false as of this writing:

| Criterion | Status | Evidence |
|---|---|---|
| CI green from a clean checkout | **FALSE** | `Tests` workflow red on `main` for 19 consecutive runs since `a3c2fc62` (2026-07-30 15:31Z). Current run 30629260871 on `aae7577`: 2 of 6 jobs failing |
| No authority file contradicts the roadmap | **FALSE** | Mission KLF-001 names a Phase 2 the roadmap does not define |
| ≥2 verified `free-exec` packets | Unknown here | Builder DB absent in this checkout; `./kitty context --agent` reports `builder.state = unavailable` |
| Daylight run crossing failure boundaries | Prose only | `docs/initiatives/ktf-004-*` manifests exist; no runtime evidence readable from the repo |
| One low-risk packet through full delivery | Plausible | PR #325 did commit → push → PR → review → merge |
| Resume-loop proof on a real project | Prose only | STATE claims verification against live project data; not reproducible from repo |
| Status reconstructable without chat history | Partial | This document was reconstructable — but only after reconciling four contradicting files |

**Phase 1 has not met its own exit criteria.** The declaration that it exited
was made in `.claude/STATE.md`, which is a session checkpoint, not the roadmap
authority. Nobody updated `docs/ROADMAP.md` to match.

---

## 3. What is verified working — three honest tiers

Using the states mandated by `docs/FEATURE_REALITY_2026-07-28.md` (Working /
Partial / Planned). That document set the rule on 2026-07-28 and it has never
been applied to an actual list. This is that list.

### Tier A — verified by a command whose output was read

Source: GitHub Actions run 30629260871 on `main` @ `aae7577`, 2026-07-31 12:04Z.

| Gate | Result |
|---|---|
| `pytest` | **3418 passed, 1 failed**, 78% coverage (73% floor met) |
| `lint` (ruff) | pass |
| `typecheck` (mypy) | pass |
| `kitty-chat` (frontend unit + build) | pass |
| `hygiene` (vulture, lychee, deptry, pip-audit) | pass |
| `browser-smoke` (Playwright) | **0 passed, 14 failed, 10 skipped** |

That 3,418-test backend suite is the strongest asset in this repo. It is real,
it is broad, and it passes. Treat it as the foundation, not as decoration.

The single pytest failure is
`tests/test_cold_start_acceptance.py::test_clean_reader_can_resolve_all_cold_start_questions`,
which asserts the literal string `"Trust Foundation and Resume-Loop Proof"` is
in `docs/ACTIVE_MISSION.md`. The mission was legitimately retitled. The test
hardcodes prose that changes by design every mission — it will break again next
mission unless its *shape* is fixed, not its string.

The browser-smoke failure is more serious and is covered in §4.

### Tier B — built and merged, but only prose says it works end to end

From `docs/packets/README.md` (registry last updated **2026-07-14** — 17 days
stale) plus `docs/PROJECT_STATUS.md`:

Shipped and merged: state spine (001), inbox triage (002), action queue (003),
state home (004), Gmail read-only connector (005), dev-session resume (006),
delegation generator (007), knowledge library + expert retrieval (008),
de-faked loops/insights (009), capture-to-knowledge (010), brief v2 + push
(011), privacy boundary (012, later retired by ADR 0022), nudges/web_monitor
(013), honest gates (014), phone channel (015), next-step navigator (016),
benefits/admin rails (017), expert packs (018), project registry + resume
(021), memory taste (023).

Backend surface is genuinely large: 50 route modules under `gateway/routes/`,
57 UI components under `gateway/kitty-chat/src/components/`.

The caveat from `FEATURE_REALITY` still holds and is the honest reading:
capabilities were built in parallel, surfaced inconsistently, and documented
through stale snapshots. Breadth is not the problem. Integration is.

**Two of these are marked shipped but were never independently closed out:**

- **016 (next-step navigator)** — the packet explicitly says it closes out
  "after a week of Jacob judging real Bs, not on merge alone." No record of
  that week exists.
- **Move-in bar (all 5 criteria)** — declared reached 2026-07-05 by inferring
  it from packet completion. No single run has ever exercised all five
  end to end.

### Tier C — spec authored, zero shipped code

| # | Packet | State |
|---|---|---|
| 019 | Job search scaffold | ⏸ parked by Jacob ("plan it, don't build it") |
| 020 | GitHub read-only connector | 🧭 planned, never authored |
| 022 | Magic Kitty cross-project insight | 🚧 partial — route/module/tests on main (#153); executor contract + privacy hardening remain |
| 024 | Chat log idea mine | 📋 spec only |
| 025 | Imagegen pipeline v2 | 📋 spec only |
| 026 | Builder reliability | ◐ rails landed, closeout runs as 027 |
| 027 | Builder restart/recovery proof | 🚧 in Builder queue, state unknown here |
| 028 | Reasoning engine | 📋 spec only |

### Tier D — unknown, and must stay unknown

Builder runtime state. `data/kittybuilder/builder_queue.db` does not exist in
this checkout, so initiatives, attempts, leases, provider exhaustion, and
publication state are **unknown**, not empty. Same for actual product usage:
`data/kitty/` is empty here, so nothing in this repo can tell you whether Jacob
opened Kitty this week.

---

## 4. What is actually broken right now

Independently confirmed, and consistent with the review already sitting in
PR #326 (`docs/research/pr-review-48h-2026-07-31.md`, which found the same
things and is worth merging).

**B1 — the browser gate is dead, and it died silently.**
All 14 Playwright smoke tests fail. `browser-smoke` in `.github/workflows/tests.yml`
starts only the Next.js server, with no Python gateway behind it. `HealthGate`
in `KittyRuntimeProvider.tsx` fetches `/proxy/health`, gets nothing, and renders
a "Gateway offline" panel *instead of its children*, so `<main>` never mounts
and every spec times out on `waiting for locator('main')`.

Last green: `8790c21` at 03:39Z. First red: after `8828019 feat(ui): health
gate, PWA dismiss, builder breakdown, model display names`.

This is a test-environment bug, not a product bug — gating the UI on a live
gateway is correct behaviour. But the consequence matters: North Star rule 4
says *"UI work isn't done until it's seen working in a browser. No exceptions."*
That rule currently has no enforcement. Any UI regression merged today ships
unnoticed. Fix the smoke suite (stub `/proxy/health` in a Playwright fixture),
not the gate.

**B2 — `main` has been red for over a day and the signal is buried.**
19 consecutive failing `Tests` runs. Lint and hygiene were the cause until
`d55a084` fixed them; browser-smoke and the cold-start test are the cause now.
The cost is visible in B1: the health-gate regression landed into already-red
CI, so nobody could see a new failure appear.

**B3 — the PR automation shipped in #301 is broken in three places.**
`pr-auto-label` uses labeler v4 config against `actions/labeler@v5` and has
never once worked; `pr-test-hints` declares `pull-requests: read` and 403s on
every run; `pr-risk-guardrails` hard-fails any PR whose body lacks
`Manual approval: YES`, which pins all 13 Dependabot PRs permanently red on a
gate no bot can satisfy. PR #327 is open against this.

**B4 — 13 Dependabot PRs are stuck**, including `anthropic` 0.92 → 0.120 and
`next` 16.2.11 → 16.2.12. Nothing owns dependency hygiene in the roadmap.

**B5 — Builder session residue is being committed.** `.gitignore` covers
`.opencode/` but not `.omo/` or `.ocx/`; 8 `.omo/run-continuation/ses_*.json`
files are tracked on `main`. PR #324 is pure residue and should be closed.

---

## 5. What is missing from the plan that should be there

The parts nobody wrote down, ordered by how much they'd hurt.

**M1 — There is no Phase 2.** The active mission cites it; the roadmap does not
define it. Until a Phase 2 section exists with outcomes and exit criteria, every
future session will re-derive priority from a session checkpoint, which is
precisely the failure mode ADR 0020 was written to end. **This is the single
highest-leverage missing artifact.**

**M2 — Nothing measures the only success metric the project has.** North Star
says the measure is "mornings Jacob *wants* to open Kitty — nothing else." No
roadmap outcome, no checkpoint, and no test tracks whether Kitty is opened,
whether a brief was read, or whether a suggested next step was ever done. The
repository can prove 3,418 tests pass and cannot prove the product was used
once. Everything in §3 Tier B is at risk of being permanently unfalsifiable
without this.

**M3 — The move-in bar was never re-verified as a whole.** It was declared
reached by inferring it from packet merges on 2026-07-05, and the five criteria
have never been exercised together in one run. With the browser gate dead
(B1), there is also nothing that would catch it silently breaking. A single
scripted end-to-end pass over all five would convert the project's most
important claim from inference to evidence.

**M4 — No feature has ever been labelled Working / Partial / Planned.** The
hard rule was written on 2026-07-28 and never applied. §3 of this document is
the first attempt. It belongs in a maintained file, not an audit snapshot.

**M5 — No data-durability checkpoint.** `scripts/kitty_backup.py` exists.
Nothing in the roadmap owns "Jacob's benefits deadlines, job-search state, and
journal survive a dead Mac." For a local-first single-user product holding
exactly the paperwork that caused a $600-class miss, an untested backup is a
liability, not a mitigation. No restore has ever been proven.

**M6 — Nothing owns "the brief arrives when the Mac is closed."** Move-in
criterion 1 says the brief lands on the iPhone unprompted.
`scripts/kitty_desktop_launchd.py` schedules the local runtime — and launchd
does not run on a sleeping or powered-off laptop. ADR 0002 (local-first,
single-user) and the unprompted-phone-delivery promise are in unresolved
tension. Either the promise needs a hosted delivery path or it needs to be
restated honestly as "when the Mac is awake."

**M7 — No spend ceiling with a checkpoint.** `gateway/token_spend_report.py`
and `scripts/spend_report.py` exist. Meanwhile the RunPod work in PR #306 rents
a GPU on every push to its branch and has failed 100% of the time (~$0.30–0.40
of nothing so far). North Star §3 makes cost a first-class design constraint;
the roadmap has no outcome for "monthly spend is visible and capped."

**M8 — No branch or PR retention policy.** 72 remote branches, including
near-duplicate pairs (`codex/review-and-plan` / `codex/eeview-and-plan`,
`feat/` vs `feature/runpod-image-studio-smoke`). Cheap to fix, gets worse
monthly.

**M9 — The packet registry is stale enough to mislead.** Last updated
2026-07-14. It is the file most likely to be read as "what's built," and it is
17 days behind. This is the same class of confusion as mistaking a spec for a
shipped feature — a mistake already made once in this project's history.

---

## 6. Recommended order

Grounded in the roadmap's own operating rule: *finish one trustworthy end-to-end
product loop before expanding feature scope.* No new features until 1–3 land.

1. **Get `main` green.** The executor prompt already exists and is ready to run:
   `docs/research/prompt-fix-main-2026-07-31.md` in PR #326. Seven scoped tasks,
   each with a verification command. Merge #326 and #327 first so the plan and
   the workflow repairs are on `main`.

2. **Close the Phase 1 / Phase 2 contradiction.** Either write the Phase 2
   section into `docs/ROADMAP.md` with real exit criteria, or amend Phase 1's
   exit to reflect that CI is not green. Do not leave a running mission pointing
   at a phase that does not exist. (M1)

3. **Re-verify the move-in bar end to end, once, and record it.** All five
   criteria in one run. This converts the project's most important claim from
   inference to evidence, and it is the natural first outcome of a Phase 2.
   (M3)

4. **Add the usage signal.** Even a crude one — last-opened, brief-read,
   next-step-completed. Without it, "does Kitty work" stays unanswerable and
   every future roadmap argues from vibes. (M2)

5. **Then** prove restore from backup (M5), settle the phone-delivery promise
   (M6), and put a spend ceiling behind a checkpoint (M7).

Feature work — 022, 024, 025, 028, Image Studio — stays behind all of it. That
is the roadmap's existing rule, not a new opinion.

---

## Appendix — what this review could not verify

- Builder runtime state (DB absent from this checkout)
- Actual product usage (`data/` is gitignored and empty here)
- Whether local provider credentials, quotas, or MLX/LiteLLM routing are healthy
- The local Python suite (this container lacks gateway dependencies; 82
  collection errors, environmental only — CI is the authority for §3 Tier A)
