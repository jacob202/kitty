# PR #306 review — guarded RunPod worker vertical slice

Head `46b4586b` on `feat/runpod-image-studio-smoke`, base `aae7577`.
5,329 additions across 33 files, 128 commits. Draft.

Verdict: **keep it draft.** The cost-safety design is genuinely good and I
verified the core claims in code. But the live path has never once succeeded,
the PR body claims a CI state that is not true, and a bearer credential is being
published to world-readable logs. None of those block the design — they block
believing the evidence.

---

## What is actually solid

I went looking for the ways this burns money unattended. The design holds up.

**Cloud-enforced termination is real.** `gateway/runpod_control.py:358` puts
`terminateAfter` into the GraphQL create input:

```python
"startSsh": False,
"supportPublicIp": False,
"templateId": template_id,
"terminateAfter": expires_at_rfc3339,
```

RunPod itself holds the deadline, so the cap survives the local process dying —
which is the single most important property for rented GPU. Claim verified.

**The budget guard fails closed.** `_validate_created_pod_rate` deletes the Pod
and raises on *both* an over-ceiling rate and a missing/unparseable rate:

```python
if pod.hourly_rate <= 0:
    cleanup_error = await self._delete_after_invalid_create(pod.pod_id)
    ...
    raise RunPodApiError("RunPod create response omitted a positive finite hourly rate" + detail)
```

An unknown price is treated as a failure, not as zero. That is the right call
and it is rarer than it should be. Claim verified.

**Ambiguity is never retried.** `gateway/runpod_graphql.py` has a careful error
taxonomy: transport error, non-200, invalid JSON, and "neither a Pod nor a
rejection" all raise `RunPodGraphQLAmbiguousError`; only an explicit GraphQL
`errors` array raises `RunPodGraphQLRejectedError`. The GPU-fallback loop
continues only on `Rejected` and re-raises on `Ambiguous`. So a create whose
outcome is unknown never spawns a second billable Pod. This is the part I
expected to find wrong, and it is right.

**Caller env cannot override the Kitty markers** — `_RESERVED_ENV_KEYS` is
filtered out of caller-supplied env before the merge.

**`infra/runpod/smoke.env.example` commits blank values.** Both credential
fields are empty. Claim verified.

**The Python suite is strong.** 3,451 passed, 1 failed — and the one failure is
`test_cold_start_acceptance`, inherited from main, unrelated to this branch.
Every one of the ~1,300 lines of new tests passes.

---

## F1 — the PR body's CI status section is false

The body states:

```
## CI status
- pytest: passed
- hygiene: passed
- browser-smoke: passed
```

Actual check runs on head `46b4586b`:

| job | body claims | actual |
|-----|-------------|--------|
| pytest | passed | **failure** |
| hygiene | passed | **failure** |
| browser-smoke | passed | **failure** |
| james-smoke | — | **failure** |
| lint, typecheck, kitty-chat | passed | success |

`mergeable_state` is `unstable`, which is GitHub agreeing.

Two of those three are inherited from main and not this PR's fault. That is not
the point. The point is that a PR whose entire purpose is to be trusted with a
credit card asserts a verification state that did not happen. Non-negotiable #2
exists for exactly this. Fix the section or delete it — an absent CI summary is
better than a wrong one.

## F2 — the worker bearer credential is published in cleartext, and the repo is public

`jacob202/kitty` is public (`private: false`).

`.github/workflows/runpod-james-live.yml` mints a random value and writes it
straight into `$GITHUB_ENV` in one line, without registering it as a mask.
Because it is never masked, GitHub prints it in the env dump of every
subsequent step. The live log for run 30633053795 shows the full 64-character
hex value in plaintext, unredacted, at least three times — where a masked value
would read `***`.

That value sits in a log anyone on the internet can read. Paired with the Pod's
public proxy URL (`https://{pod_id}-8000.proxy.runpod.net`, built by
`PodInfo.proxy_url`), it is the complete credential for submitting jobs to a GPU
Jacob is paying for, for as long as that Pod is up.

Mitigating: it is per-run, the Pod is terminated by the cleanup job, and
`terminateAfter` caps it at 30 minutes. So the window is bounded, not open. It
still should never have been printed.

Fix — capture into a shell variable, mask it, then export:

```yaml
- name: Prepare ephemeral worker credential
  run: |
    value="$(openssl rand -hex 32)"
    echo "::add-mask::$value"
    echo "KITTY_WORKER_BEARER_TOKEN=$value" >> "$GITHUB_ENV"
```

`::add-mask::` is what makes GitHub redact every later occurrence. Treat the
value from that run as burned — it is already dead by `terminateAfter`, so there
is nothing to revoke, just do not reuse the pattern.

## F3 — CI patches the source before the live run

`runpod-james-live.yml` step 2:

```yaml
- name: Apply verified REST schema correction
  run: |
    sed -i '/"templateId": None,/d' gateway/runpod_control.py
    ! grep -q '"templateId": None' gateway/runpod_control.py
```

`git grep '"templateId": None' 46b4586b -- gateway/` returns **nothing**, so
today this is a no-op against a line that no longer exists. Vestigial, not
currently harmful.

But the pattern is the problem: the job that produces the "genuine image and
provenance" evidence runs a tree that CI mutated. Any artifact it uploads
attests to `46b4586b + sed`, not to `46b4586b`. If the sed ever matches again,
the evidence silently stops describing the commit.

Delete the step. If a schema correction is needed, it belongs in the source.

## F4 — every push to the branch rents a GPU, and each failure costs the full 20 minutes

```yaml
on:
  push:
    branches: [feat/runpod-image-studio-smoke]
    paths:
      - gateway/runpod_control.py
      - workers/comfy_worker/**
      - workflows/**
      ...
```

So editing any RunPod file and pushing spends money, unattended, with
`--accept-charges` hardcoded in the run step. Today that fired at least twice:
one run cancelled at ~12 minutes by `cancel-in-progress`, one that burned the
full `RUNPOD_READY_TIMEOUT_SECONDS: 1200` before failing. At the `0.60`/hr
ceiling that is roughly $0.30–0.40 of nothing.

Cheap in isolation. The shape is what matters: an unattended loop that spends
on every push, waits 20 minutes to discover a failure that was knowable in 30
seconds, and is currently failing 100% of the time.

Two changes:

1. Drop the `push:` trigger. Leave `workflow_dispatch:` only, until a live run
   has succeeded once. Cost becomes opt-in.
2. Make readiness fail fast. The probe currently treats every non-ready
   response the same. A **connection refused** means the container is still
   booting — keep waiting. A **sustained HTTP 404** means something is
   listening and it is not the Kitty worker — that will never become ready, so
   abort after a short confirmation window instead of burning 1,200 seconds.

Credit where due: `concurrency.cancel-in-progress` plus a `cleanup` job with
`if: always()` is the right shape, and the cleanup job succeeded on both runs
including the cancelled one. The reconciler only deletes Pods prefixed
`kitty-image-james-`, so it cannot nuke unrelated Pods.

## F5 — the live path has never worked, and the body reads as though it has

The one substantive live result, run 30633053795:

```
comfy-proxy 8188 status=404 len=0
Adaptive James batch failed: worker readiness timeout: worker health returned 404:
```

Twenty minutes of 404. Something answers on the proxy; the Kitty worker does
not. That is consistent with RunPod template `2lv7ev3wfp` being stock ComfyUI
with no `workers/comfy_worker/app.py` in it and nothing launching it.

The body's "Remaining live validation" section says this honestly. The summary
bullets above it do not — "add one guarded authenticated-worker smoke script
with cost estimates, billing reconciliation, unique provenance, and automatic
Pod termination" describes code that exists, in a voice that implies it ran.
The test-plan checkbox `[ ] live paid smoke test remains manual` is the only
honest signal and it is the last line. Move it up.

**On Path A vs Path B.** The handoff calls Path A — set `containerStartCmd` on
the template through the RunPod console — the fastest. The code agrees, and not
by accident. `create_image_pod` explicitly refuses to send a start command down
the GraphQL path:

```python
if container_start_cmd is not None:
    raise RunPodConfigurationError(
        "container_start_cmd requires image_name and REST deployment"
    )
```

The live workflow uses the template/GraphQL path. So with the code as written
there is no way to inject the worker launch command via the API — baking it
into the template is the only route that works without also switching to REST
deployment with a custom image. Path A is correct, and the 404 is precisely the
symptom of it not being done yet.

## F6 — hygiene regression: two dead parameters

New in this PR, and the reason `hygiene` is red here while it is green on main:

```
gateway/runpod_control.py:274: unused variable 'docker_entrypoint' (100% confidence)
gateway/runpod_control.py:275: unused variable 'docker_start_cmd' (100% confidence)
```

`create_image_pod` accepts both and uses neither. Delete them from the
signature — repo rule is no dead code, and an accepted-but-ignored parameter is
worse than dead, because a caller will reasonably assume passing it does
something.

---

## What I would do next, in order

1. Mask the credential (F2). One line, do it before the next live run.
2. Delete the `push:` trigger (F4). Stops unattended spend immediately.
3. Delete the sed step (F3) and the two dead params (F6). Both trivial; F6 turns
   hygiene green.
4. Fix the PR body's CI section (F1).
5. Then Path A: set the worker start command on template `2lv7ev3wfp` in the
   console, and `workflow_dispatch` one run. That is the experiment that
   actually resolves the 404.
6. Add the fail-fast readiness rule (F4.2) once you have seen one success, so
   the next failure costs 30 seconds instead of 20 minutes.

Nothing here argues against the approach. The control plane is the most careful
code in this repo. It just has not been shown to work yet, and the PR body
currently claims more than the evidence supports.
