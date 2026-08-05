# The James workflow — proven 2026-08-02

Photorealistic images of Jacob's own likeness, generated locally on open weights.
Every setting below produced a real image; nothing here is theory.

## The finding that mattered

Jacob's LoRA collection splits across **two incompatible base models**, which is
why earlier results were inconsistent:

| LoRA | Base | Stacks with identity? |
|---|---|---|
| `FrhOzsbkqvvcgrLw_2Tel…` (fal portrait trainer) | **Flux** | — this *is* the identity |
| `t_FUsAIviW1xkHW3KmByJ…` (fal portrait trainer) | **Flux** | second identity training |
| `Male_Nude_and_Genital_Anatomy_for_Flux_1_Dev` | **Flux** | yes |
| `dickie` | Flux-family | yes |
| `xhirsute-4.0` (2.3GB) | **Qwen-Image** | **no** |
| `sulphur2_gay_sex_coachbate_v1` | **Qwen-Image** | **no** |
| `qwen-image-penis-lora-coachbate-v2` | **Qwen-Image** | **no** |
| `Qwen Image Edit 2511_v2` | **Qwen-Image** | **no** |

The identity was trained on Flux. The strongest body LoRAs are Qwen. They cannot
load together. Using the Qwen set means retraining identity on Qwen — a separate
job, not a setting.

## What runs

- **Pod:** `c8pwk8tb79d57l` (`miserable_blue_herring`), RTX 3090 Ti 24GB, $0.27/hr
- **ComfyUI:** `https://c8pwk8tb79d57l-8188.proxy.runpod.net`
- **Model root:** `/workspace/runpod-slim/ComfyUI/models` — the **persistent
  volume**. `/opt/comfyui-baked/models` looks like the right place and is not:
  it is container disk and is wiped when the pod stops.
- **Checkpoint:** `flux1-dev-fp8.safetensors` (17GB, on the volume, survives stops)
- **LoRAs on the pod:** the Flux identity LoRA and the Flux anatomy LoRA

Runner: `scripts/james_comfy.py`.

```bash
COMFY_URL=https://c8pwk8tb79d57l-8188.proxy.runpod.net \
python3 scripts/james_comfy.py "<prompt>" --identity 1.0 --steps 26 --seed 404
```

## Settings that worked

| Setting | Value | Why |
|---|---|---|
| identity strength | **1.0** | 0.9 gave the face but let the build drift generic |
| steps | 26 | 24 was fine; 26 slightly cleaner skin |
| guidance | 3.0 | Flux default; higher went waxy |
| cfg | 1.0 | Flux is guidance-distilled — never raise this |
| sampler/scheduler | euler / simple | |
| size | 896×1152 | portrait; 1024² also fine |
| time | ~29s per image | on the 3090 Ti |

## Prompt rules learned the hard way

1. **Never write "bear".** Flux rendered a fur sweater — a literal animal pelt as
   clothing. Say "stocky heavy-set man" instead.
2. **Say "shirtless" and "bare chest" explicitly.** Without it Flux invents a
   garment to put the described hair on.
3. **"thick dark chest hair"** beats "covered in dense body hair" — the latter
   reads as a material.
4. Name the build: *stocky, heavy-set, soft belly, broad shoulders*. The identity
   LoRA carries the face, not the body.
5. Name the greying: *short salt-and-pepper hair greying at the temples*.
6. Camera language earns its place: *DSLR 85mm, shallow depth of field, natural
   skin texture with visible pores, film grain, candid*.

### The prompt that landed

```
photorealistic photograph of a shirtless stocky heavy-set man, bare hairy chest,
thick dark chest hair, soft belly, broad shoulders, short salt-and-pepper hair
greying at the temples, stubble, standing waist-deep in a clear blue lake, pine
forest and rocks behind, warm golden hour sunlight, shot on a DSLR 85mm lens,
natural skin texture with visible pores, film grain, candid
```

Seeds 404 and 505 at identity 1.0 both matched the reference set on face, build,
body hair, and greying.

## Cost

About $0.18 for the whole session: pod time at $0.27/hr for roughly forty
minutes, including a 17GB model download. Generation itself is ~$0.002 an image.

The 17GB checkpoint is on the persistent volume, so the next session starts
generating in about a minute rather than twenty.

## Not done yet

- **Nudes.** The Flux anatomy LoRA is uploaded but untested. `--anatomy 0.6` is
  the starting point; it has not been exercised.
- **The Qwen lane.** Better body/hair LoRAs, needs identity retrained on Qwen —
  roughly an hour of pod time, under a dollar.
- **img2img and inpainting.** The runner only does text-to-image so far. Editing
  an existing keeper at denoise 0.35–0.5 is the next thing to build.
- **Kitty integration.** This runs from a script, not from chat. Wiring it to the
  `image_jobs` pipeline and a `Kitty Image` menu row comes after the workflow
  itself is settled.

## Operating rule

**Stop the pod when finished.** It bills by the hour whether or not anything is
generating.

```bash
python3 - <<'PY'
import json, urllib.request
k = "<RUNPOD_API_KEY>"
r = urllib.request.Request("https://rest.runpod.io/v1/pods/c8pwk8tb79d57l/stop",
    data=b"{}", method="POST",
    headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
print(urllib.request.urlopen(r, timeout=60).status)
PY
```
