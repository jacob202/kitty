# Handoff prompt — get `main` green (copy-paste to executor agent)

> **Tasks 1–4 are already done in PR #327. Start at Task 5.**
>
> An executor running Tasks 1–4 now will collide with that branch on the same
> files. #327 carries the labeler v5 migration, the `pr-test-hints` permission
> fix, the Dependabot waiver, and the `pr-review-routing` deletion. Tasks 5, 6,
> and 7 are still open and are what actually turns `main` green.

Context for Jacob, not the executor: this is scoped to make CI green plus two
decisions he already approved. The code-quality findings (F6 chronicle dead
code, F7 UTC bug) are deliberately excluded — separate packet, listed at the
bottom.

---

## PROMPT STARTS HERE

You are working in the `kitty` repository at `~/Projects/kitty`. `main` is red.
Your job is to make it green and apply two approved decisions. Work on a new
branch `fix/ci-green-2026-07-31` off the latest `origin/main`.

Do not refactor anything not listed. Do not reformat unrelated code. Do not
push and do not open a PR — commit locally and stop.

There are six tasks. Do them in order. After each one, run the verification
command given and paste its real output. If a verification fails, stop and
report it rather than moving on.

---

### Task 1 — migrate `.github/labeler.yml` to the v5 schema

`.github/workflows/pr-auto-label.yml` pins `actions/labeler@v5`, but
`.github/labeler.yml` is still v4 format. Every run fails with:

```
Error: found unexpected type for label 'area/backend' (should be array of config options)
```

v5 requires each label to map to a list of match blocks, with globs nested under
`changed-files:` → `any-glob-to-any-file:`. Rewrite the file so it keeps exactly
the same five labels and exactly the same glob patterns. Target shape:

```yaml
area/backend:
  - changed-files:
      - any-glob-to-any-file:
          - "gateway/**/*.py"
          - "mcp/**/*.py"
          - "tests/**/*.py"
          - "requirements*.txt"
          - "pyproject.toml"
```

Apply the same transformation to `area/frontend`, `area/docs`, `area/ci`, and
`area/automation`. Do not add, remove, or reword any glob.

**Verify:** `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/labeler.yml')); assert set(d)=={'area/backend','area/frontend','area/docs','area/ci','area/automation'}, d.keys(); assert all(isinstance(v,list) and 'changed-files' in v[0] for v in d.values()); print('ok', {k: len(v[0]['changed-files'][0]['any-glob-to-any-file']) for k,v in d.items()})"`

Expected counts: backend 5, frontend 1, docs 4, ci 2, automation 3.

---

### Task 2 — fix the permission scope on `pr-test-hints.yml`

`.github/workflows/pr-test-hints.yml` posts a comment on a pull request but
declares `pull-requests: read`. Commenting on a PR is governed by the
`pull-requests` scope even though the REST path is `/issues/{n}/comments`, so
every run 403s with `Resource not accessible by integration`.

Change the `permissions:` block from:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: read
```

to:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: write
```

Change nothing else in the file.

**Verify:** `grep -A4 '^permissions:' .github/workflows/pr-test-hints.yml`

---

### Task 3 — exempt Dependabot from the risk-guardrail hard failure

`.github/workflows/pr-risk-guardrails.yml` flags `requirements*.txt`,
`pyproject.toml`, and `.github/workflows/**` as risky scope, then calls
`core.setFailed()` unless the PR body contains `Manual approval: YES`.
Dependabot never writes that, so all 13 open Dependabot PRs are permanently red
on a gate no bot can satisfy.

Approved decision: bots still get the labels and the status comment, but do not
get the hard failure. Humans still do.

At the end of the script, the final block currently reads:

```js
            if (isRisky && !hasManualApproval) {
              core.setFailed(
                "Risky scope detected without manual approval. Update PR body with `Manual approval: YES` or check the risky-scope manual approval checkbox."
              );
            }
```

Replace it with:

```js
            // Dependabot cannot write `Manual approval: YES` into a PR body, so a
            // hard failure here would pin every dependency PR red forever. The
            // risk labels still apply — only the blocking failure is waived.
            // Matched exactly, not by an `endsWith` test on "[bot]": Copilot and any
            // future app would otherwise inherit the waiver, and those open PRs
            // carrying real code and workflow changes.
            const isDependabot = context.payload.pull_request.user.login === "dependabot[bot]";

            if (isRisky && !hasManualApproval && !isDependabot) {
              core.setFailed(
                "Risky scope detected without manual approval. Update PR body with `Manual approval: YES` or check the risky-scope manual approval checkbox."
              );
            } else if (isRisky && !hasManualApproval && isDependabot) {
              core.warning(
                "Risky scope on a Dependabot PR — labeled, not blocked. Human review still required before merge."
              );
            }
```

**Verify:** `grep -n 'isDependabot' .github/workflows/pr-risk-guardrails.yml` — expect three hits, and `grep -c 'endsWith' ...` — expect 0.

---

### Task 4 — delete the review-routing workflow

Approved decision: `.github/workflows/pr-review-routing.yml` maps every area to
the single repo owner and then filters out the PR author, so it requests zero
reviewers on every human PR and only emits a bot comment. Delete it.

```
git rm .github/workflows/pr-review-routing.yml
```

Then grep the repo for references to it and remove any that exist — check
`docs/WORKFLOW.md` in particular, which documents the workflow set. Update that
doc's prose so it no longer lists review routing.

Known tradeoff, accepted by Jacob: on a **bot**-authored PR the author is not
`jacob202`, so routing does currently request him as reviewer. Deleting it drops
that automatic request on the 13 Dependabot PRs at the same time Task 3 downgrades
their hard failure to a warning. The `risk/high` label still lands and still gates
merge, and on a single-maintainer repo a self-review-request is weak signal — but
it is a real loss, not a no-op.

**Verify:** `grep -rn 'pr-review-routing\|Review Routing\|review-routing' . --exclude-dir=.git --exclude-dir=node_modules` — expect hits only under `docs/research/`.

---

### Task 5 — stop `test_cold_start_acceptance` asserting a mission title

`tests/test_cold_start_acceptance.py:72` is:

```python
    assert "Trust Foundation and Resume-Loop Proof" in documents["active_mission"]
```

`docs/ACTIVE_MISSION.md` was legitimately retitled to
`# Active Mission — Phase 2 Life-First Home Truth`, so this fails. The test
answers the cold-start question "what is active?" — every other assertion in
that test checks a **structural** phrase that survives content changes. This one
hardcodes prose that changes by design every mission.

Do not update the string to the new title. That reintroduces the same breakage
next mission. Replace the line with structural assertions:

```python
    assert documents["active_mission"].startswith("# Active Mission — ")
    assert "## Objective" in documents["active_mission"]
    assert "## Acceptance Contract" in documents["active_mission"]
```

Leave the line immediately after it
(`assert receipt["continuity"]["active_mission"]["status"] == "running"`)
untouched — that is the part that actually proves a mission is live.

**Verify:** `python3.12 -m pytest tests/test_cold_start_acceptance.py -q --tb=short`

---

### Task 6 — unbreak the browser smoke suite

All 14 Playwright smoke tests fail. This is the biggest one and it is a
**test-environment** bug, not a product bug — do not change the health gate.

Cause: the `browser-smoke` job in `.github/workflows/tests.yml` starts only the
Next.js server, with no Python gateway. `HealthGate` in
`gateway/kitty-chat/src/components/KittyRuntimeProvider.tsx` fetches
`/proxy/health`, gets nothing, and renders an "Gateway offline" panel **instead
of its children** — so `<main>` never mounts and every spec that waits on it
times out with `waiting for locator('main')`.

Fix by stubbing the health endpoint for smoke runs only. Create
`gateway/kitty-chat/tests/smoke/fixtures.ts`:

```ts
import { test as base, expect } from '@playwright/test'

// The smoke suite runs the Next server alone, with no Python gateway behind it.
// HealthGate blocks rendering until /proxy/health answers, so stub it here —
// these specs exercise the UI, not the gateway handshake.
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/proxy/health', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    )
    await use(page)
  },
})

export { expect }
```

Then in each of the five spec files — `boot.spec.ts`, `chat.spec.ts`,
`mobile-layout.spec.ts`, `navigation.spec.ts`, `settings.spec.ts` — change the
import from `@playwright/test` to the fixture:

```ts
// before
import { test, expect } from '@playwright/test';
// after
import { test, expect } from './fixtures';
```

Only the import line changes. Do not touch the test bodies. If a spec imports
other symbols (`devices`, `Page`, types) from `@playwright/test`, keep a second
import for those.

The route must be registered before `page.goto('/')`, which the fixture
guarantees.

**Verify:**
```
cd gateway/kitty-chat
npm run build
npx playwright test
```
Expect 14 passed, 10 skipped. If Chromium is missing locally, set
`PLAYWRIGHT_CHROMIUM_PATH` — the config already honours it.

---

### Task 7 — stop tracking OpenCode session residue

`.gitignore` covers `.opencode/` but not `.omo/` or `.ocx/`, so every Builder
run commits its session state. Eight files are already tracked:

```
.omo/run-continuation/ses_*.json   (8 files on main)
```

Add to `.gitignore`, next to the existing `.opencode/` entry:

```
.omo/
.ocx/
```

**STOP — get Jacob's explicit approval before this next step.** `git rm --cached`
records repository deletions, which repo policy treats as work requiring his
sign-off, even though local copies survive. Tasks 3 and 4 carry his approval;
this one does not yet. Ask, then proceed.

Then untrack what is already committed, without deleting anyone's local files:

```
git rm -r --cached .omo .ocx
```

(`.ocx` may not exist in the working tree — if `git rm` errors on it, run the
command for `.omo` alone and say so.)

**Verify:** `git ls-files | grep -E '^\.(omo|ocx)/' | wc -l` — expect `0`.

---

### Finish

Commit in logical chunks — CI workflow fixes, test fixes, and the gitignore
cleanup can be three commits. Use `fix(ci):`, `fix(test):`, `chore(git):`
prefixes.

Then run the full gate and paste the real numbers:

```
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npx playwright test
```

Report exact pass/fail counts. If anything is still failing, say so plainly and
name the test — do not describe a partial fix as done. Do not push.

## PROMPT ENDS HERE

---

## Deliberately out of scope (second packet)

- **F6** — `gateway/db.py:assert_schema_current()` has zero production callers.
  Wire it into gateway startup after `migrate()`, or delete it.
- **F7** — `gateway/chronicle_service.py:hourly_distribution()` buckets in UTC,
  so the peak-hour tip tells Jacob the wrong hour and then advises him to
  schedule around it. Needs local time or a configured timezone.
- **F8** — `/chronicle/tips` JSON-decodes every message of every chat per
  request when it only needs counts.

## Needs GitHub credentials, not a code agent

- Close PR #324 (Builder residue: two `.omo` session files and a 3-line empty
  research doc, opened non-draft against `main`).
- Retarget PR #307 from base `copilot/review-session-history` to `main`, or
  close it — Task 1 above supersedes its content either way.
