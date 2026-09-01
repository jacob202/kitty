# Packet Standard

**Status:** active. Every packet authored after 2026-08-30 follows this.
**Owner:** interactive packet master.
**Why it exists:** Builder has attempted 167 runs and completed 1. Every rule
below is derived from a run that actually failed, not from taste.

A packet is a bounded unit of work that a model who has never seen this
repository can pick up, finish, and prove — with no further conversation.

---

## 1. What ships with a packet

Two files, always both:

| File | Purpose | Read by |
| --- | --- | --- |
| `docs/initiatives/<initiative-id>.json` | The executable contract | Builder |
| `docs/packets/<packet-id>.md` | Plan, reasoning, verification, recovery | Humans and workers |

The JSON is machine-checked and schema-closed. Everything a validator cannot
hold goes in the Markdown. Never invent JSON keys — the validator rejects them
and the packet becomes unrunnable.

---

## 2. The failures this standard prevents

Each rule below traces to a dated, verifiable failure. Do not relax a rule
without new evidence that supersedes the old.

| # | What went wrong | Evidence | Rule it produced |
| --- | --- | --- | --- |
| F1 | A packet named "builder preflight" forbade touching `gateway/builder_preflight.py`. The worker wrote the file the objective demanded, Builder called it a scope violation, blocked the task `repairable: false`, and three attempts were burned. Six versions of the same initiative were authored instead of fixing one list. | `KITTY-RECOVERY-001-BUILDER-001-V6` / `BUILDER-PREFLIGHT-proto`, task `kb_mtgatvyi_340e`, attempts 193–195, run `run_mtgdhllo_ea71` | §5 — allowed_paths must cover files the packet will **create** |
| F2 | Workers spent their entire 600 s budget hunting for a Python that could run the packet's tests. `python3.12` was not on the worker PATH; `import pytest` failed; the run timed out with partial work discarded. | `run_mtg94vnm_2d12` at base `c6fdd108`, combined.log | §6 — validation commands must run in the **worker's** environment |
| F3 | Two tests inside one packet contradicted each other, and one contradicted the packet's own acceptance criterion. CI `kitty-chat` failed. | `LibraryView.test.tsx` before `8fa7da78`: one test required a PDF's "Use in chat" button enabled so a click could discover the refusal over the network; a sibling test required it disabled; criterion 2 required refusal *before* dispatch | §7 — acceptance criteria and tests must be mutually consistent |
| F4 | A user-facing PR could not merge because it had no product acceptance record. | `scripts/pr_policy.py:30-44,122-139`; PR #705 `policy-gate` failure | §8 — user-facing packets carry a running-app acceptance plan |
| F5 | Every gateway refusal reached the screen as `Gateway returned 415`, because the shared fetch helper throws before reading the response body. Jacob does not code; a status code is not an answer. | `gateway/kitty-chat/src/lib/gateway.ts` `gfetch`, fixed in `8fa7da78` | §7 — "no raw error" is an acceptance criterion, not a nicety |
| F6 | 178 queued and 34 blocked tasks sit selectable. Builder once ran a stale packet for nine attempts while the approved work was never materialised as a task. | queue status 2026-08-30; `artifacts/forensic-b8-wrong-assignment-2026-08-05.md` | §9 — a packet declares its own stop condition and stale-work guard |
| F7 | The manifest validator accepts exactly five top-level keys and eight packet keys. Metadata added to JSON makes a packet unrunnable. | `gateway/builder_initiative.py` | §4 — schema is closed |
| F8 | Builder durable identity is `(initiative_id, packet_id)`, but an older worker-identity verifier looked up its allowlist by `packet_id` alone. Reusing `BUILDER-PREFLIGHT-proto` across initiative versions then caused a false duplicate/identity rejection. | PR #699 / `52327705 fix(builder): scope worker identity by initiative and packet`; `initiative_packets` primary key | §4 — treat packet identity as the composite pair everywhere |
| F9 | A Builder worktree has no `node_modules` — it is a git worktree and the directory is gitignored — and the runner exposes a Python venv but no Node toolchain. Every `npx` gate is unrunnable there. | verified absent in `.worktrees/kittybuilder/kb_mtgatvyi_340e/gateway/kitty-chat`; no `node_modules` handling anywhere in `builder_runner.py` or `builder_execution_boundary.py` | §6 — frontend gates live in the companion doc for CI, never in `validation_commands` |

---

## 3. The one-sentence test

Before writing anything else, answer this in one sentence:

> After this packet lands, Jacob can **\_\_\_\_**, which he could not do before.

If the sentence needs a comma-spliced list, the packet is two packets. If it
describes an internal refactor with no visible change, it is not a packet —
it is a step inside one.

---

## 4. The manifest contract

Exactly these top-level keys, nothing else:

```json
{
  "manifest_version": 1,
  "initiative_id": "kebab-or-caps-id-vN",
  "title": "...",
  "description": "...",
  "packets": []
}
```

Exactly these packet keys, nothing else:

```json
{
  "id": "PACKET-ID-WITHIN-THIS-INITIATIVE",
  "title": "...",
  "objective": "...",
  "depends_on": [],
  "acceptance_criteria": [],
  "allowed_paths": [],
  "policy": { "max_attempts": 2, "priority": 0 },
  "validation_commands": []
}
```

**`policy.routing` is omitted for free work.** Writing
`"routing": {"model": null, "provider": null}` looks harmless and is rejected:
the validator requires every routing key that is *present* to be a non-empty
string. Omit the key entirely (or use `{}`) and the packet runs on the free
ladder. Only a packet that genuinely pins a paid route names both, and its
companion doc justifies the spend under §10.

Verified against `./kitty builder initiative validate`: omitted, `{}`, and
`null` all pass; `{"model": null, "provider": null}` fails.

**Expect one warning.** A packet whose `allowed_paths` span two or more
subsystems (backend plus frontend, say) draws
`manifest looks prototype-shaped ... but no packet id ends in '-proto'`. That is
a heuristic, not a defect, and most real packets trip it. Do not rename packets
to `-proto` to silence it.

**Identity rules.**

- Durable packet identity is **`(initiative_id, packet_id)`**. A packet ID must be
  unique inside its initiative/manifest, but the same `packet_id` may appear in
  a different initiative. Never key allowlists, receipts, reviews, or lookups by
  `packet_id` alone (F8).
- An initiative revision gets a new file and a new `initiative_id` ending `-vN`.
  The superseded one is recorded in the companion doc, never by silently
  editing the old JSON.
- `depends_on` names packet IDs inside the same manifest. Cross-manifest order
  belongs in the companion doc and in `docs/ROADMAP.md`.

---

## 5. `allowed_paths` — the rule that has cost the most

`allowed_paths` is a fence the worker cannot cross. A file outside it is a
scope violation, and a scope violation is **not repairable**: the task blocks
and the attempt is gone (F1).

Rules:

1. **If the packet can create a file, allow the directory that will hold it.**
   Naming the expected new file is good practice but is *not* sufficient: V6
   named a new path and still died, because the worker reasonably chose a
   different filename for the same module. Only a directory entry is a
   guarantee. Prefer the narrowest one that can hold the work
   (`gateway/kitty-chat/src/lib`, not `gateway/`).
2. **A fence of only existing files is a deliberate choice.** It is correct for
   a packet that edits and creates nothing — and the companion doc must say so
   in one line. Preflight flags every such fence so the choice is never an
   accident.
3. **Include the test files.** Workers must write tests. If `tests/` is not in
   the list, the packet forbids its own proof.
4. **Never include** `.claude/`, `data/`, `logs/`, `.env`, `config/*secret*`,
   `.github/workflows/` unless the packet is explicitly about CI and Jacob
   approved it. Builder workers never touch continuity files.
5. **Two packets that can run concurrently must not share a path.** The
   validator flags colliding paths between packets with no dependency edge;
   fix the dependency or split the paths.

Self-check: *read the objective, list the files a competent worker would touch,
and confirm every one appears in `allowed_paths`.* That check would have saved
F1 three times.

---

## 6. `validation_commands` — proof the worker can actually run

The commands run **inside the worker's isolated git worktree**, in a shell that
is not your shell (F2).

Rules:

1. **Use `python -m pytest`, never `python3.12 -m pytest`.** The runner exposes
   the repository venv to the worker; a hard-coded interpreter version is not on
   the worker's PATH and burns the entire time budget failing to be found.
2. **No Node tooling at all — no `npx`, no `npm`.** A Builder worktree is a git
   worktree and `node_modules/` is gitignored, so it is simply not there. The
   runner exposes the Python venv to workers (`builder_runner.py`
   `_validation_toolchain`) but has no equivalent for Node. Every `npx` gate
   therefore fails, or tries to reach the network from inside the sandbox with a
   ten-minute budget. Frontend proof is real and required — it just lives in the
   companion doc's Tier 2 and runs in CI, not in `validation_commands` (F9).
   `npm run` is doubly banned: it also exits 194 silently and reports a success
   it never proved (`docs/packets/014-make-the-gates-honest.md`).
3. **Name specific test files, not the whole suite.** A packet proves its own
   change. `python -m pytest tests/` is a 4,900-test wait, not a gate.
4. **Every path a command names must exist, or be inside `allowed_paths`.**
   pytest exits 4 on a missing target, which reads as "validation failed" rather
   than "the packet is wrong".
5. **The gate must fail before the change and pass after.** If it passes on
   current `main`, it proves nothing. Say in the companion doc which command
   fails today and what its current output is.

Historical manifests under `data/kittybuilder/manifests/` preserve the runtime
contracts they were authored with. Some still contain `python3.12` commands or
paid routes; they are evidence, **not templates for new packets**. New authoring
follows this standard and `scripts/packet_preflight.py`.

Every shape Builder can run today:

```
python -m pytest -q tests/test_<subject>.py
python -m pytest -q tests/test_<a>.py tests/test_<b>.py
python -m ruff check <paths>
```

That is the whole list. The frontend commands below are real and must appear in
the companion doc's Tier 2, where CI runs them — never in `validation_commands`:

```
cd gateway/kitty-chat && npx vitest run tests/<Subject>.test.tsx --reporter=dot
cd gateway/kitty-chat && npx tsc --noEmit
cd gateway/kitty-chat && npx playwright test tests/smoke/<subject>.spec.ts
```

**Consequence for ownership.** A packet with no Python surface cannot prove
itself inside Builder. Mark it `owner: interactive` in the companion doc and let
a person or an interactive session build it. A packet with both halves is
Builder-runnable: Builder proves the backend, CI proves the UI. Splitting a
UI change from its backend change along that line is usually the right call.

---

## 7. `acceptance_criteria` — what "done" means

Each criterion is one sentence, observable, and checkable by someone who did
not write the code. No criterion may contradict another (F3).

Every packet that changes something Jacob can see carries these four, in
addition to its own:

- Every visible primary control either completes its task or is disabled with
  one plain-language reason next to it. A read-only card is a defect.
- No raw server error, status code, stack trace, port, env var name, or Mac
  file path is ever the primary message a person reads (F5).
- Nothing lies about state: no client-only success, no "healthy" over a stale
  heartbeat, no count that was not measured.
- Desktop and iPhone-class widths show no horizontal overflow, clipped dialog,
  or off-screen primary control.

Criteria that name a command must name one from `validation_commands`.

---

## 8. Verification plan — where proof comes from

Every packet's companion doc has a **Verification** section with three tiers.
State which tiers apply and why any is absent.

**Tier 1 — Mechanical (always).** The `validation_commands`. Fails before,
passes after. Quote the current failing output in the plan.

**Tier 2 — Running app (any user-visible change).** A Playwright spec in
`gateway/kitty-chat/tests/smoke/`. The suite runs every spec at both the
`desktop` (1440×900) and `mobile` (iPhone 14) projects automatically, and CI
runs it as `browser-smoke`. This is the only repeatable running-app proof this
repository has — prose about clicking around is not evidence.

Route-stub the gateway calls the spec needs; `**/proxy/health` must answer or
the app never mounts, and `localStorage['kitty-onboarded'] = 'true'` must be set
before navigating. Scope `getByRole('alert')` to `main` — Next's route announcer
is also an alert.

**Tier 3 — Product acceptance (any user-facing change, required to merge).**
`scripts/pr_policy.py` blocks the PR without a filled
`## Product acceptance (required for user-facing changes)` section carrying six
checked boxes and four fields, one of which is a reviewer **who did not
implement the change** completing the task in the running app (F4). Plan for
that reviewer when you author the packet; do not discover it at merge time.

---

## 9. Safe for long unattended runs

Builder may run overnight on its own schedule under a hard ceiling of
**CAD 6.00 per week** (`config/compute_governor.json`). A packet is safe to
leave running only if all of this is true:

- **One stop condition, written down.** What makes the worker stop and say
  "this is not mine to decide" instead of guessing. Ambiguity plus autonomy is
  how B8 ran nine attempts of the wrong work.
- **Attempt budget is honest.** `policy.max_attempts` of 2 is the default. A
  packet that plausibly needs more says why in the doc rather than silently
  relying on operator grants.
- **No irreversible side effect.** Never push, open a PR, merge, send mail,
  spend money, or touch `data/`, secrets, or auth. Publication stays behind
  Jacob's explicit approval.
- **Restartable from its own contract.** If the machine dies mid-run, the next
  worker reads the same JSON and reaches the same place. Nothing depends on
  chat history, an operator's memory, or a file outside the repository.
- **Fails loud.** No swallowed exception, no invented default, no "assume it
  worked". An unknown stays unknown.

---

## 10. Free versus paid

Free is the default and the fence is enforced in code: the free lane rejects a
paid model override outright (`gateway/builder_loop.py`
`_sanitize_free_adapter_env`). The free ladder tries seven models in order
before giving up (`scripts/kittybuilder_dsh_worker.sh`).

For free work, **omit `policy.routing`**. `{}` or a `null` routing key also
validate, but omission is the canonical authoring shape. Never write explicit
null subkeys such as `{"model": null, "provider": null}`: Builder rejects them
because a present `model` or `provider` must be a non-empty string.

Ask for paid only when the packet's own text can justify it:

| Spend when | Because |
| --- | --- |
| The change is subtle enough that a wrong-but-plausible diff costs more than the tokens | Free models produce confident wrong code on ambiguous specs |
| Free models have already failed this exact packet twice with *clean* failures | Two clean failures is evidence, one is noise |
| The packet is on the critical path of something Jacob is waiting for today | Time has value; CAD 0.50 does not |

Never spend when the work is mechanical, when the packet is exploratory, when
the free lane has not been tried, or when the failure was infrastructure rather
than capability — a provider outage says nothing about model capability.

The compute governor refuses to pay twice for the same packet at the same base
SHA, and holds a reserve floor. It can also downgrade a request rather than
refuse it. Treat its decision as final.

---

## 11. Preflight — run this before applying any manifest

```bash
python scripts/packet_preflight.py docs/initiatives/<file>.json
./kitty builder initiative validate docs/initiatives/<file>.json --json
```

The preflight is read-only and mutates nothing. It fails on the defects that
have actually stopped runs; the Builder validator checks schema and dependency
integrity. Both must pass before `initiative apply`.

---

## 12. Companion doc template

```markdown
# <PACKET-ID> — <one line a person understands>

**Initiative:** <initiative-id>
**Owner:** builder | interactive
**Depends on:** <packet ids, or none>
**Free or paid:** free (default) | paid — <justification from §10>

## What Jacob can do after this
One sentence. The §3 test.

## Why this is the next thing
Two or three sentences. What is broken or missing today, with file:line or a
running-app observation. Not speculation.

## Plan
1. …
2. …
Numbered steps in order. Name the files. Name the risk in the step that carries it.

## Not in scope
The adjacent things a reasonable worker would drift into. Be explicit.

## Verification
**Tier 1 — mechanical.** The exact commands, and what they output *today*
(the failing state), and what they must output after.
**Tier 2 — running app.** The smoke spec path and the states it covers.
**Tier 3 — product acceptance.** Who reviews, and the task they must complete.

## Stop condition
The one situation where the worker stops and escalates instead of deciding.

## Recovery
If this fails halfway: what is safe to re-run, what must be undone, and where
the next worker resumes.
```

---

## 13. Authoring checklist

- [ ] One sentence of §3 written and it needs no comma splice
- [ ] Packet ID is unique within this initiative; all identity references use `(initiative_id, packet_id)`
- [ ] Every file the packet creates is in `allowed_paths` (§5)
- [ ] Test paths are in `allowed_paths`
- [ ] No `.claude/`, `data/`, secrets, or workflow paths
- [ ] `python -m pytest`, never a hard-coded interpreter (§6)
- [ ] No `npm run`
- [ ] Every command's target exists or is inside `allowed_paths`
- [ ] At least one gate fails today, and the doc quotes that failure
- [ ] Acceptance criteria do not contradict each other or the tests (§7)
- [ ] The four standing user-facing criteria are present if anything is visible
- [ ] Tier 2 smoke spec planned if anything is visible
- [ ] Tier 3 reviewer named if the change is user-facing
- [ ] Stop condition written
- [ ] Recovery written
- [ ] `scripts/packet_preflight.py` passes
- [ ] `./kitty builder initiative validate` passes
