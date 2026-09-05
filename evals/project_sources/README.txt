# Project Source retrieval eval

This fixture measures whether Kitty Project Sources improve retrieval and consequential
judgment without treating Sources as current technical authority.

The frozen corpus has 24 cases: 18 should retrieve durable Source context and 6 are
live-state questions that must abstain and use Git/GitHub/KX/runtime instead. The
candidate set is the nine numbered v3.3 Sources plus raw `Why kitty exists.txt` as a
separate ablation candidate.

Run:

```bash
python3 evals/project_sources/score.py \
  --corpus evals/project_sources/corpus.json \
  --observations evals/project_sources/observations.json
pytest -q tests/test_project_source_eval.py
```

`observations.json` is a frozen evidence record, not a live retriever implementation.
Re-run and replace it when the Source pack, retrieval mechanism, or case prompts change.

## Frozen v3.3 result

- acceptable hit@1: 15/18 (83.3%)
- acceptable hit@3: 18/18 (100%)
- preferred-Source hit@1: 12/18 (66.7%)
- preferred-Source hit@3: 17/18 (94.4%)
- irrelevant Source slots in top 3: 28/54 (51.9%)
- historical/context mistaken as live authority: 0
- full-Source context upper bound: ~85,332 char/4 tokens
- irrelevant portion of that upper bound: ~44,942 tokens (52.7%)
- consequential decision pairs: 4 complete; 0 decision reversals, 2 material
  workflow improvements, 0 regressions
- paid spend: CAD 0

The numbered pack shows no missing durable category, so expansion is not supported by
this corpus. Retrieval is not precise enough to freeze: broad Sources still displace
specialist Sources and more than half of top-3 slots are irrelevant under the strict
case labels.

## Why Kitty Exists check

Raw `Why kitty exists.txt` ranks first for the deliberately unique human-conditions
query about uneven capacity, activation cost, continuity loss, disappearing ideas, and
AI-enabled avoidance. Removing it promotes Source 01 to rank one, so the narrative has
real unique signal but the numbered pack still covers the operational product judgment.

On the generic purpose query, raw Why is absent from the top four. On the two focused
active-focus/proactivity checks it is rank four or absent, with zero non-target top-3
attractions. Preserve it as narrative/historical evidence; this eval does not support
making it a tenth numbered Source or loading it by default.

## Limitations

Search rankings are observations of the current Project-files retriever, not a benchmark
of every future retrieval stack. Approximate token burden uses full-file character count
divided by four, so it intentionally overstates snippet-based runtime cost. Decision
pairs use one fixed free model and test whether Source context changes consequential
judgment; they are not a general model-capability benchmark.

The four decision pairs are qualitative adversarial examples, not a statistical estimate
of Source effect size. The ten frozen candidate SHA-256 values are distinct. The six
NO-SOURCE cases define and diagnose the required abstention boundary, but this fixture
does not prove that a live Kitty retrieval router currently enforces that abstention;
that is a separate runtime integration claim and is reported as unverified here.

The largest strict irrelevant-attractor counts are Source 01 (7 top-3 slots), Source 04
(5), and Source 05 (5). Source 01 also occupies rank one in 6 of the 18 Source-needed
cases. This is evidence for retrieval/scoping work, not for deleting those broad Sources:
several of the same documents are correctly relevant in other cases.
