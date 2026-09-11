# Codex review-fidelity eval

This fixture measures how much of one strong reviewer's output a candidate review model
reproduces. It exists to answer a specific question with evidence instead of opinion:
when a reviewer is called "not as good as Codex", which findings does it actually miss?

The reference labels are the inline review comments that `chatgpt-codex-connector` left on
Kitty pull requests between 2026-08-28 and 2026-09-11. Those comments name a file, a diff
hunk, a severity, and a specific defect and corrective action. They are frozen here as the
corpus, so a candidate can be scored repeatedly against the same standard.

## Contents

- `corpus.json` — the frozen reference labels. 45 review units (PRs), 446 findings
  (153 P1, 293 P2). Each review unit records the exact `base` and `head` SHAs Codex
  reviewed, so the diff is reproducible from Git rather than duplicated here.
  All 45 units reproduce today, and each reconstructed diff's file count matches the
  PR's recorded changed-file count. One unit (PR 674) has a head that is no longer
  reachable from any local ref because its branch was deleted after merging; the harness
  fetches `refs/pull/<n>/head` for that case and says so on stderr. A revision that cannot
  be obtained at all raises rather than silently shrinking the run.
- `detect.py` — the producing half. Reconstructs a review unit's diff, chunks it
  file-aware, asks a candidate model to review it under the same strict standard, and
  writes candidate findings as observations.
- `score.py` — the scoring half. Deterministic and offline; matches candidate findings to
  Codex findings by file and line.
- `observations.json` — not committed. See "Producing observations" below.

## Running a candidate

The harness is endpoint-agnostic: anything that speaks the OpenAI-compatible
`/v1/chat/completions` shape works, including a local llama.cpp server, Ollama, or a hosted
router. Which model produced observations is recorded inside them, because a fidelity score
is only meaningful with the model that earned it.

```bash
python3 evals/codex_review_fidelity/detect.py \
  --corpus evals/codex_review_fidelity/corpus.json \
  --out evals/codex_review_fidelity/observations.json \
  --endpoint http://127.0.0.1:8080 \
  --model <model-name> \
  --prs 845,846,852        # omit to run every review unit

python3 evals/codex_review_fidelity/score.py \
  --corpus evals/codex_review_fidelity/corpus.json \
  --observations evals/codex_review_fidelity/observations.json \
  --show-missed 20
```

`README.txt` is intentionally not Markdown: eval notes should not widen coordination scope.

## Producing observations

`observations.json` is deliberately absent. It is a frozen measurement, and no measurement
has been taken on this repository's terms yet. Producing it requires a candidate endpoint
that can actually complete a review; record the model and endpoint in the output rather
than substituting a different or weaker model and presenting the number as if the intended
one had run.

The intended local candidate is `Qwen3.5-9B-Q3_K_M` served by llama.cpp from
`~/Library/Application Support/Kitty/models/local-reviewer/`, matching `gateway/local_review.py`.
On a machine with 8 GB unified memory that candidate could not complete a review: the
configured Metal profile failed with `Insufficient Memory (kIOGPUCommandBufferCallbackErrorOutOfMemory)`,
and CPU-only inference measured roughly 0.25 tokens/second (16 tokens in 64s; a 128-token
request did not finish in 400s). That is an environment measurement, not a statement about
the model's review quality, and it is why no observations are committed.

## Choosing a candidate model

`--max-tokens` (default 16000, or `CODEX_EVAL_MAX_TOKENS`) is not a cosmetic knob. A
reasoning model spends most of its completion budget on chain-of-thought before it emits
the JSON answer, so a small cap truncates the response mid-thought. The failure is easy to
misread: the model narrates the defects it found and then stops, and a naive parser reports
zero findings for a run that in fact found several.

Two guards exist because of exactly that:

- A response is accepted only when its final JSON array could be a findings list (empty, or
  objects carrying a `path`). Incidental brackets in reasoning prose ("files [a.py, b.py]")
  are refused with an error instead of being counted as "no findings".
- The `NO_ACTIONABLE_FINDINGS` sentinel is honoured only when the response contains no array
  at all, because a reasoning model commonly restates that instruction in its narration.

A chunk that cannot be parsed is recorded in `chunk_errors` and surfaced by `score.py` as
`provenance.chunk_errors`. Always read that count alongside recall: a run with parse errors
is a failed measurement, not a candidate that found nothing.

In practice, prefer a candidate that answers directly. Testing found that a heavy reasoning
model on a large diff would exhaust even a 16000-token budget on narration and never emit
the array, leaving only recorded chunk errors.

## How scoring works

Matching is by location, because location is the only part a scorer can decide mechanically.
A candidate finding counts against a Codex finding when it names the same file and its line
falls inside the Codex finding's diff hunk or within `--tolerance` lines (default 10) of the
finding's anchor line. `corpus.json` stores the parsed hunk span for every finding so this
comparison needs no diff parsing at score time.

Reported metrics:

- `recall.location_match_rate` — share of Codex findings a candidate located, overall and
  split by Codex's own P1/P2 severity.
- `recall.confirmed_real` — the same rate restricted to the 89 findings a human explicitly
  fixed. This is the strongest subset: a `Fixed in <sha>` reply means the finding named a
  defect the project actually repaired, so it separates real defects from Codex noise.
- `precision.candidate_location_precision` — share of a candidate's own findings that land on
  a Codex finding. A candidate that reports everything scores high recall and low precision,
  which is why recall alone is not reported as a quality verdict.
- `missed_findings` — the specific defects a candidate did not reproduce, with severity and
  confirmed-real status, so misses can be read rather than only counted.

## Limitations

- **Location match is not defect match.** Two findings on the same line can describe different
  defects, and a defect can be described accurately at a different line. Location matching
  bounds this but does not eliminate it. Whether a matched candidate describes the *same*
  defect is a judgment that belongs in a reviewer record, not in this scorer.
- **The reference is one reviewer, not ground truth.** Codex's findings are the labels; they
  are not a complete inventory of every defect in those diffs. A candidate that finds a real
  defect Codex missed is scored as a precision loss, not a win. Low recall means "did not
  reproduce Codex", never "wrong".
- **The corpus inherits Codex's blind spots and severity choices.** P1/P2 labels are Codex's.
- **The reviewer model is undisclosed.** The GitHub-hosted Codex connector does not reveal
  which model produced these reviews, so comparisons cannot be normalized by model.
- **Only 106 of 446 findings have a human reply**, and only 89 carry an explicit
  `Fixed in <sha>`. The remaining findings are unclassified: absence of a reply is not
  evidence the finding was false, so `confirmed_real` is a high-precision subset, not a
  full label set.
- **There is no negative label set.** Reading all 106 replies, none rejects a finding:
  the other 17 confirm or address it in different words ("Confirmed and added",
  "Addressed on current head"). So this corpus cannot measure whether a candidate is
  *better calibrated* than Codex by correctly dismissing bad findings -- a candidate that
  over-reports is only penalised through `candidate_location_precision`. That reading is a
  manual observation, not a computed field; a keyword heuristic for rejection was tried and
  discarded because it misfired on fix prose such as "the two reads cannot disagree".
- **Review units differ in size and difficulty.** Recall is reported per unit, and a corpus-wide
  rate is an average over unequal PRs rather than a controlled measurement.
- **Chunked review can lose cross-file defects.** A defect spanning two files that land in
  different chunks may be unreproducible by construction. `provenance.chunk_errors` reports
  chunks that failed outright so a partial run is never mistaken for a candidate that found
  nothing.
- **No observations are frozen yet.** This fixture currently ships the corpus plus the
  machinery to produce and score observations. It does not yet assert a fidelity number.
