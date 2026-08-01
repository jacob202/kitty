# Grounding — verified architecture and current state

**Written:** 2026-08-01. **Verified against:** code at `b68268b`, GitHub Actions
runs 1124–1139, a clean `python3.12 -m venv` install, and one full pytest run.

Every line here was checked this session. Anything not checked is marked
UNVERIFIED and must not be treated as fact.

## The finding that reorders everything

`main` is red and has been since 2026-07-31T22:40Z.

- `tests.yml` `pytest` job failed on 8 consecutive `main` commits (runs 1124,
  1125, 1126, 1127, 1132, 1133, 1134, 1139). Run 1139 is current HEAD `b68268b`.
- Failure is at `pip install -r requirements.txt`, before any test executes:
  `ERROR: ResolutionImpossible`.
- Cause: `requirements.txt:17` pinned `openai>=2.49.0,<2.50.0`; `mem0ai` 0.1.x
  (line 29, `mem0ai>=0.1.118,<0.2`) requires `openai<1.110.0,>=1.90.0`. No
  version satisfies both.
- Introduced by Dependabot commit `600c0fa` ("bump openai from 2.48.0 to
  2.49.0"), which rewrote the pin from `>=1.90.0,<1.110.0` — a range that had
  been derived from mem0ai's own ceiling — to the 2.x range.

`docs/ROADMAP.md` Gate 0.1 claims "Restore green main … Status: COMPLETE",
verified at `59f598c5`. That was true when written and false by the time the
Dependabot queue merged. **The roadmap's foundation claim did not survive
contact with its own merge queue.**

Reproduced locally with the identical error text before changing anything.

## Test reality (single run, this session)

Command: the exact CI invocation
`pytest tests/ -q --tb=short --cov=gateway --cov-report=term-missing --cov-fail-under=73`

Result after the dependency repair: **3452 passed, 7 failed, 2 deselected,
77.50% coverage** (floor is 73%).

The 7 failures split cleanly:

**Container-environmental (4) — would pass on CI/Jacob's Mac:**
- `test_resume_script.py::test_exits_zero` — `gh` binary absent
- `test_kitty_launcher_runtime.py::test_down_handles_launchd_ui_and_owned_listeners` — launchd is macOS-only
- `test_check_continuity_state.py` ×2 tied to `repo:canonical_checkout`
  expecting `~/Projects/kitty`; CI sets `KITTY_EXPECTED_CANONICAL_CHECKOUT`

**Real committed-state defects (3) — would have failed CI too:**
- `.claude/STATE.md` `head_sha` was `"9c446874"`, an 8-char SHA; the validator
  (`gateway/context_receipt.py:693`) requires a full 40-char lowercase SHA
- `.claude/STATE.md` declared PR #331 with `"state": "MERGED"`; the validator
  (`context_receipt.py:854`) fails any `pull_request` block that is not `OPEN`
  with a `head_sha`. `null` is the correct value for a finished PR.
- `.claude/HANDOFF.md` was missing the required `pull_request` key entirely

All three repaired this session. Their own `invalidation_conditions` had
already fired — they recorded `9c446874` while main sat at `b68268b` — so
updating them clobbered no live workstream.

## Image subsystem — issue #336's diagnosis is accurate

Checked each claim against code rather than trusting the issue:

| Claim | Verified |
| --- | --- |
| Plan is not persisted | TRUE — `build_image_plan()` (`gateway/image_plan.py:61`) returns a dataclass; `/studio/plan` (`gateway/routes/extended.py:606`) serialises and returns it. No store, no DB write, no plan id. |
| Approving the preview generates from original form state | TRUE — `StudioGenerateRequest` (`extended.py:406`) carries `prompt`/`quality`/`identity`/`character_id`/`recipe_id`/`negative_prompt`. There is no `plan_id` field. The approved plan cannot reach dispatch. |
| Guidance selections do not reach the renderer | TRUE — `guidance_tags` exists only on `PlanPreviewRequest` (`extended.py:415`), not on `StudioGenerateRequest`. |
| No LLM acts as image specialist | TRUE — no `gateway/image_agent.py`; no image-specialist prompt path. |
| No image-session state | TRUE — migrations stop at `028_image_jobs_queue.sql`; no session table, no anchor, no protected traits. |
| Worker exposes only `text_to_image_v1` | TRUE — `workers/comfy_worker/app.py:704` hardcodes it; `workflows/` contains exactly one bundle. |

So a follow-up edit today **cannot** be a real edit: there is no image input
path to bind a parent artifact to.

## What exists and must be reused (not rebuilt)

`gateway/image_jobs.py` (731 lines, durable jobs + lineage),
`image_runner.py` (212, single dispatch boundary), `image_characters.py`,
`image_recipes.py`, `image_plan.py`, `image_guidance.py` + 8 guidance
Markdown files, `image_backends.py`, `image_quality.py`, `image_gen.py`;
`gateway/runpod_worker.py`, `gateway/runpod_control.py`,
`workers/comfy_worker/`, `workflows/text_to_image_v1/`;
`ImageStudio.tsx` (985 lines), `ImageGallery.tsx`, `ImageGenPanel.tsx`.

## Builder surface (inventory only — UNVERIFIED behaviour)

27 `gateway/builder_*.py` modules, 7 `gateway/actions/builder_*.py`,
2 route modules (`routes/builder.py`, `routes/builder_control.py`),
`gateway/models/builder.py`, `scripts/kittybuilder_opencode_worker.sh`,
25 `tests/test_builder_*.py` files.

No Builder runtime behaviour was exercised this session. The count of modules
is a fact; "which of these is the live execution path" is not yet established
and is the first job of Outcome B.

## Environment ceiling for this session

Ran in an ephemeral Linux cloud container, not Jacob's Mac. Absent: `.env`,
RunPod credentials, LiteLLM/MLX, a running Kitty, a browser, `gh`, launchd,
`~/Projects/kitty`, and any GPU. Anything in issue #336's hard acceptance test
— browser flow, real artifacts, artifact hashes, GPU billing cleanup — is
**not producible here at all**, by any amount of effort. It is not a
difficulty; it is an absence.
