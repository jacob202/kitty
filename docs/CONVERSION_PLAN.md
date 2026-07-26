# Conversion Plan

**Authored:** 2026-07-26. Sits under `docs/ALIGNMENT_MAP.md` Phase 1.

## Diagnosis

Kitty does not have a knowledge deficit. It has 191 markdown documents, 137 of
them archived, 26 packets, 4 shipped, and 0 currently executable by a free
model. Five packet numbers collide. Two ideas exist as competing drafts.

The bottleneck is **conversion**: analysis becomes documents, documents do not
become running work. Every additional audit, brainstorm, or external survey
worsens the ratio it is trying to improve.

This plan therefore adds no new analysis. It builds the conversion path and
proves it on one packet.

## Ordering constraint

Steps 1–3 are forced. Nothing downstream can be trusted until validation
works, because under free-model execution the gate *is* the acceptance
(`docs/FREE_MODEL_PACKET_STANDARD.md`).

## Steps

### 1. Restore CI — blocked on Jacob

Two one-line PRs against `main`, both verified, neither authored yet because
dependency changes need sign-off:

- remove the `openai==2.48.0` pin from `requirements.txt` (nothing imports the
  SDK; `mem0ai` already constrains it)
- regenerate `gateway/kitty-chat/package-lock.json`

Until this lands, no validation command in the repo proves anything.

**Cost:** paid, minutes. **Unblocks:** everything below.

### 2. Land the three open PRs

#261 (checker + harvest review), #262 (33 gate repairs), #263 (governance
docs). All three are Phase 1 work and all three are currently red only because
of step 1.

**Cost:** paid, small — review only.

### 3. Prove the free loop on exactly one packet

Pick the smallest real packet. Author it to the standard: exact files, exact
anchor text, verbatim test, a gate verified to **fail** on an unmodified tree
(rule G2). Run it through the existing drain manually, in daylight, and read
the log end to end.

The deliverable is not the packet. It is the answer to "does a free model
actually complete a packet written this way, and does the gate actually catch
it when it doesn't."

**Cost:** paid authoring, free execution. **Unblocks:** trust in every later
step.

### 4. Build the packet compiler — `007-delegation-packet-generator`

Already specced, already marked ready. Converts a goal + acceptance criteria +
file list into a manifest packet with `allowed_paths`, validation, dependencies
and escalation filled in.

This is the leverage point. Every packet authored by hand costs paid tokens
forever; the compiler pays that cost once. ChatGPT independently named a
"packet compiler" its favourite idea, and this audit independently ranked 007
first — two derivations, one conclusion.

**Cost:** paid, one focused session. **Unblocks:** conversion stops being
hand work.

### 5. Mine the archive — free-model work

137 archived documents represent audits already paid for. Extract recurring
findings that were never actioned, duplicate plans, and stale claims.

This is the cheap version of the "Engineering Librarian": detection is
mechanical, so it is one of the few genuine `free-exec` candidates in the repo.
It recovers knowledge Jacob already bought rather than buying it again.

**Cost:** free. **Unblocks:** stops the circling.

### 6. Fix the packet-number collisions

`021`, `022`, `026` each name two different packets; `021`/`023` and
`022`/`024` are duplicate drafts. Needs judgement about which draft is current,
so it is paid — but small.

### 7. Schedule the drain

Only after 1–3. `scripts/nightly_packet_drain.sh` already exists and is already
conservative; scheduling is a `launchd` plist on Jacob's Mac. Keep
`--gate manual`. Morning surface is `data/kittybuilder/LAST_DRAIN.md`.

## On learning from other repositories

Worth doing, but not now, and not as another survey.

`docs/research/kittybuilder-brain-v1-harvest.md` already surveyed OpenCode,
oh-my-opencode-slim, oh-my-pi and architect. Its conclusion was sound — adopt
the `WorkerSession` pattern, keep KittyBuilder as sole orchestrator — and
review still found three bad citations and one recommendation resting on an
untested assumption.

That is the lesson worth generalising: **external surveys are cheap to produce
and expensive to verify.** The marginal value of a second survey is low while
the first one's adopt-list is unexecuted. Revisit after Phase 2, when
`WorkerSession` exists and there is something concrete to compare against.

The transferable practice from mature projects is not architectural. It is
that they can prove what passes. That is step 1.

## Token strategy

The scarce resource is paid authoring, not execution.

- Paid model: judgement, verification, packet authoring, review. Nothing else.
- Free ladder: implementation, archive mining, classification, detection.
- Metric worth watching: **packets converted to `free-exec` per paid session.**
- Working detail goes in files; chat gets outcomes and decisions only.
- Do not re-derive what an existing audit already found — read it first.
