# Packet Audit — 2026-07-26

Re-examination of every packet and planning artifact against
`docs/ALIGNMENT_MAP.md` and `docs/FREE_MODEL_PACKET_STANDARD.md`.

**Nothing is deleted.** Ideas are reclassified, not discarded. Where two
packets cover one idea, both are kept until Jacob picks the survivor.

**Evidence class:** classifications below are `inferred` from each packet's
declared status and intent line, not from a full read of all 26 documents.
Any packet promoted to `free-exec` must be fully read and gate-verified first
(checklist in the standard). Collisions and shipped/parked states are
`verified` by file inspection.

## 1. Numbering collisions — fix before anything else

Five collisions. Two packets share a number with a *different* packet; two
ideas exist twice under different numbers.

| Number | Files | Nature |
|---|---|---|
| 021 | `021-memory-taste-and-creative-continuity`, `021-project-registry-and-resume` | **Two different packets, same number** |
| 022 | `022-chat-log-idea-mine`, `022-magic-kitty` | **Two different packets, same number** |
| 026 | `026-audit-implement-low-risk`, `026-builder-reliability` | **Two different packets, same number** |
| 021 / 023 | `memory-taste-and-creative-continuity` | Same idea, two drafts, not byte-identical |
| 022 / 024 | `chat-log-idea-mine` | Same idea, two drafts, not byte-identical |

This matters more than it looks: packet numbers are referenced from
manifests, `docs/PLANS.md`, and session notes. An ambiguous number is a
citation that resolves to the wrong contract.

**Resolution:** renumber the later-authored member of each collision pair;
for the duplicate-idea pairs, diff the drafts and keep one, archiving the
other under `docs/archive/`. Neither is free-model work — it needs judgement
about which draft is current.

## 2. Inventory and classification

Classes are defined in `docs/FREE_MODEL_PACKET_STANDARD.md`.

### Shipped — close out, do not re-execute

| Packet | Note |
|---|---|
| `001-state-spine` | shipped |
| `002-inbox-triage` | shipped |
| `003-action-queue` | shipped, tier sheet signed 2026-07-02 |
| `008-knowledge-library-expert-retrieval` | partially shipped (PR #73); remainder gates `018` |

### Phase 1 — belongs in the current phase

| Packet | Class | Note |
|---|---|---|
| `014-make-the-gates-honest` | `free-exec-blocked` | The single most map-aligned packet in the repo. Largely executed by PR #262 (33 gates repaired). Remainder is mechanical but its own gates can't run until CI is green. |
| `026-builder-reliability` | `paid-exec` | Reliability rails; touches leases/identity/state. Phase 1, but needs judgement. |
| `026-audit-implement-low-risk` | `paid-author` | Authorized 2026-07-15. Good conversion candidate — "low risk" is exactly the free-exec shape once the edits are written out. |

### Ready, but not yet free-model-shaped

All of these are `paid-author`: the idea is sound and the work is largely
mechanical, but no one has written the patch-level detail a free model needs.

| Packet | Note |
|---|---|
| `004-state-home` | Ready; self-declares "do 014 first" |
| `006-project-resume` | Ready to build |
| `007-delegation-packet-generator` | Ready — and directly serves this standard: it generates packets |
| `015-phone-channel` | Executor-ready |
| `016-next-step-navigator` | Executor-ready |
| `021-project-registry-and-resume` | Executor-ready |

### Needs an authoring pass before it is a contract

| Packet | Class | Note |
|---|---|---|
| `018-expert-packs` | `idea` | Gated on `008` remainder |
| `020-github-connector` | `paid-author` | Self-declares "needs an executor-ready authoring pass" |
| `025-imagegen-pipeline-v2` | `paid-exec` | Jacob's verbatim spec; local-first, fal retired |
| `028-reasoning-engine` | `paid-exec` | Spec authored |
| `022-magic-kitty` | `idea` | Cross-project connection surfacing — judgement-heavy by nature |
| `021`/`023-memory-taste` | `idea` | Blocked on collision resolution |
| `022`/`024-chat-log-idea-mine` | `paid-exec` | Phase 1 partly built (offline); blocked on collision resolution |

### Human / parked — not Builder work

| Packet | Note |
|---|---|
| `019-job-search-scaffold` | Parked by Jacob 2026-07-04 ("plan it, don't build it"). **Life-first under ADR 0016** — the parking is Jacob's call, but this outranks every code packet here when he unparks it. |
| `005-mail-connector` | Ready, but Gmail OAuth is a human step |
| `017-benefits-rails-urgent-sweep` | Executor-ready spec; the *outcome* is life-first and urgent, the execution touches real accounts |

## 3. Free-model readiness — the honest verdict

**Zero packets currently qualify as `free-exec`.**

Not one of the 26 was authored against a standard that did not exist until
today. Every one that names an executor names Claude, Codex, or
"strongest-model prompt".

This is the finding that matters for the nightly drain: **the drain has
nothing safe to drain.** Scheduling it today would either exit immediately on
an empty queue, or hand a reasoning-shaped packet to a model that cannot
reason and accept whatever came back.

## 4. Conversion order

Highest leverage first. Each conversion permanently moves work onto the free
train, so paid tokens spent here compound.

1. **`007-delegation-packet-generator`** — it generates packets. Converting it
   first means subsequent conversions get cheaper. This is the only packet
   whose output is more packets.
2. **`026-audit-implement-low-risk`** — already authorized, already scoped to
   low-risk mechanical change. Closest to `free-exec` of anything here.
3. **`014` remainder** — Phase 1, mechanical, and unblocks trustworthy gates
   for everything after it.
4. **`004-state-home`**, **`006-project-resume`**, **`021-project-registry`** —
   ready specs, feature work, convertible once the pattern is proven.

Everything else waits. Converting a packet is not free — it costs the paid
tokens that are scarce — so the order above is deliberately short.

## 5. Nightly autonomy — plan and blocker

### What already exists (do not rebuild)

Per the map's non-goals, this is an extension job, not a construction job:

- `scripts/nightly_packet_drain.sh` — already written, already conservative:
  `--free` ladder, `--gate manual` (nothing auto-publishes or auto-merges),
  `MAX_RUNTIME` wall, atomic `mkdir` lock, per-run log, and a
  `LAST_DRAIN.md` breadcrumb.
- `docs/FREE_WORKERS.md` — the paid-thinks-once / free-types split, already
  documented, with the model ladder and the clean-failure hand-off rules.
- `gateway/cron.py` — existing scheduling surface.

### The blocker

**CI is dead, so validation proves nothing.** Reproduced at `b78215e`:

- `pip install -r requirements.txt` → `ResolutionImpossible`
  (`openai==2.48.0` vs `mem0ai`'s `openai<1.110.0`). No Python test in the
  repo can run.
- `npm ci` → lockfile desync (`package.json` next `16.2.11`, lockfile
  `16.2.6`). The frontend job dies at install.

A nightly drain runs packets whose acceptance is a validation command. With
both gates dark, every packet either fails at the gate or passes without
proving anything. The map's non-goal — *"do not introduce autonomy to
compensate for unreliable state"* — forbids scheduling until this is fixed.

Both fixes are one line each and are already verified, but they touch
dependencies, which needs Jacob's sign-off.

### Sequence to first unattended night

1. Restore CI — two one-line PRs against `main` (dependency sign-off required)
2. Merge #262 (gate repairs) and #261 (checker + review)
3. Convert `007` and `026-audit` to `free-exec` against the standard
4. Verify each converted gate **fails** on an unmodified tree (rule G2)
5. Run the drain **manually once**, in daylight, and read the log end to end
6. Only then schedule it

### When it is scheduled

- Keep `--gate manual`. Nothing auto-merges. The ADR 0018 auto-merge carve-out
  is for Builder campaign branches under the evidence gate, and that gate
  depends on the CI that is currently dark.
- `scripts/nightly_packet_drain.sh` hardcodes
  `REPO="/Users/jacobbrizinski/Projects/kitty"` — correct for Jacob's Mac,
  where the schedule will live. Scheduling is a `launchd` plist on macOS, not
  `crontab`; a machine asleep at the scheduled hour simply does not run, so
  pick an hour the Mac is awake or set the job to catch up on wake.
- Morning surface: `data/kittybuilder/LAST_DRAIN.md` already exists as the
  breadcrumb. It should be what Kitty reads back at session start.

## 6. Recommended changes to the plan as stated

Recorded as input, not as decisions taken.

**The map's Phase 1 and the free-model push are the same work, not two
tracks.** "Restore CI" and "repair impossible gates" are listed as Phase 1
items; they are also the exact preconditions for unattended free execution.
Treating the cron work as a parallel effort would duplicate it.

**"Really dumb packets" is right, but the dumbness has to land somewhere.**
It moves into the gate. A packet simple enough for a free model is a packet
whose correctness a script can decide — which is a *stronger* engineering
requirement than the current packets meet, not a weaker one. Expect
conversion to be real work.

**The narrative packet format is not what Builder runs.** `docs/packets/*.md`
are prose specs; `docs/initiatives/*.json` are what execute.
`docs/packets/TEMPLATE.md` says so itself. Any packet destined for the nightly
drain must end up as manifest packets. The audit above is of the idea
inventory; the conversion target is JSON.

**The scarce resource is authoring, not execution.** Free execution is
effectively unlimited; paid authoring is not. So the metric worth watching is
*packets converted to `free-exec` per paid session*, and `007` is first
precisely because it attacks that metric directly.

**Life-first still outranks this.** ADR 0016 and Jacob's 2026-07-11
preference put job search, benefits, education, health, and money ahead of
code work — including Kitty itself. `019` is parked and `017` is authored;
both are Jacob's calls, but a fully autonomous Builder that runs all night
while the benefits sweep sits unexecuted would be a local optimum.
