# Image Studio — the next four pieces

**Status:** planned, not started. Written 2026-08-02 so a cold session can execute
without rediscovering anything.
**Branch:** `feat/openwebui-tomorrow-ready` (PR #384)
**Findings this builds on:** `docs/plans/james-workflow-2026-08-02.md`
**Architecture authority:** `docs/plans/image-studio-character-first-architecture-2026-07-28.md`

## Read this first — what is already true

Do not re-derive these. Every one cost real pod time to establish.

| Fact | Value |
|---|---|
| Pod | `c8pwk8tb79d57l` (`miserable_blue_herring`), RTX 3090 Ti 24GB, $0.27/hr |
| ComfyUI | `https://c8pwk8tb79d57l-8188.proxy.runpod.net` |
| Proxy quirk | rejects requests without a browser `User-Agent` |
| Model root | `/workspace/runpod-slim/ComfyUI/models` — **persistent** |
| Trap | `/opt/comfyui-baked/models` looks right, is container disk, wiped on stop |
| On the volume | `flux1-dev-fp8.safetensors` (17GB), both identity LoRAs, Flux anatomy LoRA |
| Trigger word | **`James`** |
| Best identity LoRA | `t_FUsAIviW1xkHW3KmByJ_pytorch_lora_weights.safetensors` (#2, not #1) |
| Strength | 1.0. 1.3 burns — visible grid artifacts |
| Sampler | euler / simple, 26 steps, guidance 3.0, **cfg 1.0** (Flux is distilled) |
| Speed | ~29s per 896×1152 image |
| Runner | `scripts/james_comfy.py` |
| SSH | `ssh -p <port> root@64.119.209.250` — port changes on every pod restart |

**LoRA families do not mix.** Identity + `Male_Nude_and_Genital_Anatomy_for_Flux_1_Dev`
+ `dickie` are Flux. `xhirsute-4.0`, `sulphur2`, `qwen-image-penis-lora-coachbate-v2`,
`Qwen Image Edit 2511_v2` are Qwen-Image. Loading across families silently wastes one.

**Prompt rules:** never write "bear" (renders a fur garment); say "shirtless" and
"bare chest" explicitly; name the build (*stocky, heavy-set, soft belly*) because
the LoRA carries the face only; name the greying.

**Likeness reality:** both fal LoRAs give a family resemblance, not a match.
img2img from a real photograph at denoise 0.55 is markedly better — but Flux
img2img holds the source composition so hard that even 0.75 kept the original
jacket and background. **A portrait source gets his face; it does not get his
face in a new scene.** That is what item 1 exists to fix.

**Operating rule:** stop the pod when finished. It bills whether or not it is
generating. Stop command is at the end of the findings doc.

---

## 0. SOLVED — PuLID-Flux is the likeness answer

**2026-08-03.** After inpainting and face-pasting both failed, PuLID-Flux worked
on the first real try. It conditions the model on a face *embedding*, so identity
survives a change of pose, lighting, and scene — the exact thing pixels could not
do.

| Setting | Value |
|---|---|
| node | `sipie800/ComfyUI-PuLID-Flux-Enhanced` (cubiq's `PuLID_ComfyUI` is **SDXL only**) |
| model | `pulid_flux_v0.9.1.safetensors` in `models/pulid/` |
| face analysis | `antelopev2` unpacked into `models/insightface/models/` |
| pip | `timm insightface onnxruntime-gpu facexlib` — `timm` missing is the usual import failure |
| weight | 0.95 |
| identity LoRA | **off** (`--identity 0.0`) — PuLID and the LoRA compete for the face |
| speed | ~21s per image after the first (first run loads the face models, ~100s) |

`scripts/james_comfy.py --pulid <reference photo> --identity 0.0`

Verified across two unrelated scenes at different seeds: waist-deep in a lake at
golden hour, and sitting on a rock at sunset. Same man in both, correct stocky
build and body hair, no LoRA involved.

**Do not** stack PuLID with the identity LoRA. Strength 0 now skips the LoRA node
entirely rather than loading a file it will not use.

### Pod traps found getting here

- **Stopping a pod releases its GPU and you may not get it back.** Two pods were
  stranded with `not enough free GPUs on the host machine`. Creating a *new* pod
  always works; restarting an old one often does not. Models on that pod's volume
  are then unreachable. A network volume is the real fix if this keeps hurting.
- **`runpod/comfyui:cuda13.0` will not run on a host with an older driver.** One
  pod came up with CUDA 12.4 and torch refused. Constrain with
  `allowedCudaVersions: ["13.0","12.9","12.8"]` at create time.
- `unzip` is not installed on the image — extract with Python's `zipfile`.
- ComfyUI must be relaunched over SSH with the session held open (a `sleep` after
  the `&`); `setsid`/`disown` alone did not survive.

---

## 1. Inpainting — built, and it did NOT fix likeness

**Status 2026-08-03: implemented, tested, verdict negative.** Read this before
repeating it.

Two approaches were built and both work mechanically. Neither produced a good
likeness, and the reason is worth knowing.

**`--inpaint-face`** detects the face with YuNet on this Mac (227KB ONNX, no pod
model needed), builds a feathered oval mask, and repaints only that region via
`SetLatentNoiseMask`. Clean result, no seam, scene preserved. But repainting the
face with the identity LoRA reproduces *the LoRA's* likeness — which is the thing
that was not good enough. Concentrating it on a smaller region did not help.

**`--face-from`** composites the real photograph's face onto the scene with
`seamlessClone` and then blends at low denoise. Measured:

| denoise | result |
|---|---|
| 0.25–0.30 | composite artifacts survive — foliage bleeds into the hairline, ghosting |
| 0.45 | clean and seamless, but the sampler redraws enough that likeness drifts back to the LoRA |

There is no value between them that is both clean and faithful, because the
reference's head angle and lighting differ from the scene. Pixels cannot be
argued into a different pose.

**What would actually work:** a face model that conditions on a face *embedding*
rather than pasting pixels — InstantID, PuLID, or IPAdapter-FaceID. Those carry
identity through a pose change, which is exactly the gap. That is a custom-node
install on the pod plus a model download, not a parameter.

One bug worth remembering: the first `--face-from` pasted the crop *rectangle*,
carrying the reference's jacket collar and background into the scene as a visible
square. The patch mask handed to `seamlessClone` has to be an oval, not
`np.full(..., 255)`.

**Original reasoning, kept for context —**

**Why first:** it is the only item that improves the thing Jacob actually
complained about. Everything else is plumbing around a likeness that is not good
enough yet.

**The approach:** two passes. Generate the scene with the identity LoRA at
whatever strength composes well, then repaint only the face region starting from
his real photograph at low denoise. The scene comes from the model; the face
comes from pixels of him.

**Build:**
- Extend `scripts/james_comfy.py` with `--inpaint-face`.
- Nodes: `LoadImage` (generated scene) → face mask → `VAEEncodeForInpaint` →
  `KSampler` at denoise 0.35–0.5 → `VAEDecode`.
- Mask: try `ComfyUI-Impact-Pack`'s face detector if the pod already has it
  (`GET /object_info` and look for `FaceDetailer` / `UltralyticsDetectorProvider`).
  If absent, install via ComfyUI-Manager (V3.41 is on the pod) rather than
  hand-rolling a mask — a bounding box from a detector beats a guessed ellipse.
- Second stage must reuse the same checkpoint already in VRAM. Do not reload.

**Acceptance:**
1. A generated lake scene plus his reference produces an image where the scene is
   the prompt's and the face is recognisably his.
2. Denoise sweep 0.3 / 0.4 / 0.5 captured, best value written into the findings doc.
3. No visible seam or colour shift at the mask edge at the chosen value.
4. Refuses clearly when no face is detected rather than inpainting the whole frame.

**Watch for:** over-strong inpaint drifts age and beautifies — the architecture
doc names beautification and fake skin texture as failure modes. Compare against
the reference at full size, not thumbnails.

---

## 2. Make characters real

**Why:** Jacob's own words — "the character feature we have now doesn't actually
do anything, there's no place to enter a description and no information on how it
actually works." He is right. `gateway/image_characters.py` stores characters,
references, and gallery items. Nothing connects any of it to generation.

**What a character must hold** (it is the *recipe*, not just the photos):

| Field | Example | Exists today |
|---|---|---|
| identity LoRA filename | `t_FUsAI…safetensors` | no |
| LoRA strength | 1.0 | no |
| trigger word | `James` | no |
| base family | `flux` \| `qwen` | no |
| appearance fragment | "stocky heavy-set man, soft belly, salt-and-pepper…" | no (`description` unused) |
| negative fragment | words that break it, e.g. `bear` | no |
| reference images | 24 files | **yes** |
| preferred recipe | | yes, unused |

**Build:**
- Migration adding those columns to `image_character`. Follow the existing
  migration pattern in `gateway/image_characters.py::_ensure_db`.
- `resolve_character(character_id) -> CharacterRecipe` returning everything the
  runner needs.
- `scripts/james_comfy.py --character james` loads the recipe instead of taking
  a LoRA name and strength on the command line.
- Seed James from the findings doc. References already live at
  `~/kitty-services/faces/james/` (24 files, outside the repo — keep it that way).

**Acceptance:**
1. `--character james` alone reproduces the known-good settings with no other flags.
2. Changing the stored strength changes the output; nothing is hardcoded twice.
3. A character naming a LoRA that is not on the pod fails loudly, before spending.
4. A character whose `base_family` disagrees with a requested extra LoRA is
   refused with both families named — this is the mistake that wasted the most time.

**Explicitly not:** a second gallery, queue, or job store. `image_jobs` is the
substrate; the architecture doc says extend it, do not replace it.

---

## 3. Retrain identity on Qwen

**Why:** `xhirsute-4.0` (2.3GB) and `sulphur2` are the strongest body/hair LoRAs
Jacob has and they are Qwen-family. His face is Flux. Retraining is the only way
to use them together. Cannot be worked around with settings.

**Build:**
- Assemble the training set from `~/kitty-services/faces/james/`. **Curate**: the
  24 files mix real photographs with earlier AI generations. Train on real photos
  only — training on generated output compounds whatever the previous model got
  wrong. Expect roughly 12–19 usable images.
- Download Qwen-Image base to the pod volume (~20GB). Check free space first;
  the volume is 50GB and Flux already occupies 17GB. If it does not fit, either
  grow the volume or stage Flux out and back.
- Train with a Qwen-compatible LoRA trainer (`ai-toolkit` or `diffusion-pipe`).
  Trigger word **`James`**, same as the Flux LoRAs, so prompts stay portable.
- Budget: an hour of pod time, well under a dollar. Set a hard cap; do not leave
  training unattended without one.

**Acceptance:**
1. The resulting LoRA loads in ComfyUI against Qwen-Image without key mismatch warnings.
2. Side-by-side against the best Flux result, same prompt, same seed, captured.
3. Stacks with `xhirsute` without either being visibly ignored.
4. Verdict written down: is the Qwen lane actually better, or is this a dead end?
   A negative result recorded honestly is a good outcome — it closes the question.

**Do not** start this before item 1. If inpainting solves likeness on the Flux
lane, the value of this drops a lot and Jacob should get to make that call with
evidence in hand.

---

## 4. Wire it into Kitty chat

**Why last:** wiring a workflow that is not settled means rewiring it. Items 1–3
change the interface.

**Build:**
- New engine in `gateway/image_runner.py`, alongside `flux` and `openrouter`,
  talking to ComfyUI. Same job lifecycle: create → SUBMITTED → RUNNING →
  artifact under `data/images/<job_id>/` → SUCCEEDED. Mirror `_run_flux`.
- Pod lifecycle is the hard part. ComfyUI is only reachable while the pod runs,
  and it must not be left running. Either:
  - **(a)** the engine starts the pod, generates, and stops it in a `finally` —
    ~40s of cold start per request, correct billing; or
  - **(b)** it refuses with "the pod is stopped, start it with X" and Jacob runs
    a batch by hand.
  `gateway/runpod_control.py` already exists with budget caps and termination in
  a `finally` path — reuse it, do not write a second one. **(a)** is the better
  experience; **(b)** is honest and much simpler. Pick one and say why.
- Add `generate_image` to `/tools/v1` so Daily Kitty can call it, gated behind
  `KITTY_IMAGE_PAID_ENABLED` like the other paid lanes.
- Add the `Kitty Image` row to the model menu **only once** a pick from that row
  reliably produces an image. A row that fails when tapped is worse than no row.

**Acceptance:**
1. A generation started from Open WebUI produces an image in the gallery.
2. The pod is not running afterwards — verified by polling status, not assumed.
3. A failure (pod stopped, out of credit, moderated) reaches the user as words,
   not a blank reply.
4. Restart persistence: the job and artifact survive a gateway restart.

---

## Order and dependencies

```
1 inpainting ──► 2 characters ──► 4 chat wiring
                      ▲
       3 Qwen retrain ┘   (independent; decide after 1)
```

1 before 2 because the character recipe should record whatever inpainting turns
out to need. 4 last because 1–3 change what it wires to. 3 is independent but
worth deferring until 1 shows whether Flux is good enough.

## Resuming cold

1. `git log --oneline -15` on `feat/openwebui-tomorrow-ready`.
2. Read `docs/plans/james-workflow-2026-08-02.md` — every proven setting.
3. Read this file for what is left.
4. Pod is stopped. Start it, wait for `/system_stats` to answer 200, and note
   that **the SSH port changes on every restart** — read it from
   `GET https://rest.runpod.io/v1/pods/c8pwk8tb79d57l`.
5. Stop the pod when finished. Always.

## Budget

Items 1, 2 and 4 are code plus short generation runs — under a dollar of pod time
in total. Item 3 is the only one with real cost, and it is still under a dollar.
The RunPod keys have limited funds and no card attached, so nothing here should
run unattended without a cap.
