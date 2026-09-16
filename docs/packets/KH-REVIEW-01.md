# KH-REVIEW-01 — give the local reviewer a way to graduate or die

**Initiative:** kitty-hardening-v1
**Owner:** builder
**Depends on:** none
**Free or paid:** free

## What Jacob can do after this

Find out whether the local reviewer is good enough to replace a paid review, from
a number, rather than from how long it has been running.

## Why this is the next thing

The architecture review of 2026-09-15 named this directly: the local reviewer is
sound as a shadow, but it *currently cannot save strong-review cost because
authoritative review still always runs*, and it needs graduation and kill
criteria.

So today it is pure cost. Every dispatch pays for it, the authoritative review
runs regardless, and nothing accumulates that could ever justify turning it on or
switching it off. Left alone, that resolves by attrition — it stays forever
because nobody can prove it should go, or it gets deleted in a clear-out because
nobody can prove it should stay. Both outcomes are decided by mood.

What is missing is small: record the shadow's verdict next to the authoritative
one for the same exact candidate, and report the agreement rate with its sample
size. Then the decision is arithmetic.

## Plan

1. On each shadow review, record its verdict alongside the authoritative verdict
   for the same exact candidate. Same candidate is the whole point: two verdicts
   on different heads are not comparable and must not be counted as agreement.
2. Report an agreement rate over the recorded history, always with the sample
   size beside it. A rate without a denominator is how a handful of runs gets
   mistaken for evidence.
3. Declare the graduation and kill thresholds in one place, and name them in the
   report. Thresholds that live in a person's head drift toward whatever the
   current number happens to be.
4. Record an unavailable or erroring shadow as unavailable, never as agreement.
   An absent verdict matching nothing is not a match, and counting it as one
   inflates the rate exactly when the reviewer is least healthy.
5. Change nothing about what merges. The shadow stays non-authoritative; this
   packet measures it, it does not promote it.

## Not in scope

Actually graduating the reviewer, or switching it off. This packet produces the
evidence for that decision and deliberately does not make it. Changing the
authoritative review path, the reviewer routing, or what either model is.
Retroactively scoring past reviews — the record starts now, because reconstructed
agreement from logs that were not written for it is not evidence.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_local_review.py
python -m ruff check gateway/local_review.py
```

Today this collects 52 tests and passes, and no agreement is recorded anywhere.
The new cases must cover agreement, disagreement, an unavailable shadow, and a
report naming both its sample size and its thresholds. The unavailable case is
the one that matters most: it is the one an implementation is most likely to get
wrong in the flattering direction.

**Tier 2 — running app.** Not applicable.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if the shadow and authoritative verdicts cannot be tied to the
same exact candidate from what is recorded today. Comparing verdicts across
different heads would produce an agreement number that looks like evidence and
is not, which is worse than having no number at all.

## Recovery

Additive: recording and reporting only. Revert `gateway/local_review.py` to
`HEAD` and re-run. Any agreement history already recorded is inert data — it
changes no decision on its own, so a partial run leaves nothing that has to be
undone.
