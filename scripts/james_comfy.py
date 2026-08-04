#!/usr/bin/env python3
"""Run the James identity workflow against a ComfyUI instance.

The identity LoRA was trained on Flux, so everything here is Flux-family. Jacob's
larger body LoRAs (xhirsute, sulphur2, the Qwen penis LoRAs) target Qwen-Image
and cannot be stacked with it — mixing families is why earlier results were
inconsistent. Retraining identity on Qwen is the only way to use those.

Usage:
    COMFY_URL=https://<pod>-8188.proxy.runpod.net \\
    python3 scripts/james_comfy.py "prompt" --identity 0.9 --steps 24
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
CHECKPOINT = os.environ.get("JAMES_CHECKPOINT", "flux1-dev-fp8.safetensors")
IDENTITY_LORA = os.environ.get(
    "JAMES_IDENTITY_LORA", "FrhOzsbkqvvcgrLw_2Tel_pytorch_lora_weights.safetensors"
)
ANATOMY_LORA = os.environ.get(
    "JAMES_ANATOMY_LORA", "Male_Nude_and_Genital_Anatomy_for_Flux_1_Dev.safetensors"
)
OUT_DIR = Path(os.environ.get("JAMES_OUT_DIR", "data/images/james"))

# RunPod's proxy rejects requests without a browser agent.
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


def upload_image(path: Path) -> str:
    """Push a reference into ComfyUI's input folder and return its name."""
    boundary = "----kitty" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=body,
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)["name"]


YUNET_MODEL = Path(
    os.environ.get(
        "KITTY_FACE_DETECTOR",
        Path.home() / "kitty-services/models/face_detection_yunet_2023mar.onnx",
    )
).expanduser()


def face_mask(image_path: Path, *, feather: int = 48, grow: float = 0.35) -> Path:
    """White over the face, black elsewhere, soft-edged.

    Detected on this Mac rather than on the pod: the detector is 227KB against
    the pod's alternative of a SAM3 checkpoint, and a mask is cheap to upload.
    Raises when no face is found rather than inpainting the whole frame.
    """
    import cv2
    import numpy as np

    image = cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f"cannot read {image_path}")
    if not YUNET_MODEL.exists():
        raise SystemExit(
            f"face detector missing at {YUNET_MODEL}. Fetch it with:\n"
            "  curl -sL -o ~/kitty-services/models/face_detection_yunet_2023mar.onnx \\\n"
            "    https://github.com/opencv/opencv_zoo/raw/main/models/"
            "face_detection_yunet/face_detection_yunet_2023mar.onnx"
        )

    height, width = image.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(YUNET_MODEL), "", (width, height))
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        raise SystemExit(
            f"no face found in {image_path.name}; refusing to inpaint the whole frame"
        )

    x, y, w, h = (int(v) for v in max(faces, key=lambda f: f[2] * f[3])[:4])
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    # Haar boxes the front of the face only. Grow it so hairline, jaw, and ears
    # are inside the repaint — a mask that stops at the cheekbones leaves a seam
    # exactly where skin tone changes most.
    cx, cy = x + w // 2, y + h // 2
    ax, ay = int(w * (0.5 + grow)), int(h * (0.5 + grow))
    cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)
    mask = cv2.GaussianBlur(mask, (feather | 1, feather | 1), 0)

    target = image_path.with_name(f"{image_path.stem}_facemask.png")
    cv2.imwrite(str(target), mask)
    return target


def paste_face(scene: Path, reference: Path) -> tuple[Path, Path]:
    """Align the reference face onto the scene's face and return (image, mask).

    Repainting the face region with the LoRA reproduces the LoRA's likeness,
    which is the thing that was not good enough. Compositing the real face in
    first means the sampler is blending actual pixels of Jacob rather than
    inventing a face again; a low denoise then fixes lighting and edges.
    """
    import cv2
    import numpy as np

    def detect(path: Path):
        image = cv2.imread(str(path))
        if image is None:
            raise SystemExit(f"cannot read {path}")
        height, width = image.shape[:2]
        detector = cv2.FaceDetectorYN.create(str(YUNET_MODEL), "", (width, height))
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        if faces is None or len(faces) == 0:
            raise SystemExit(f"no face found in {path.name}")
        return image, [int(v) for v in max(faces, key=lambda f: f[2] * f[3])[:4]]

    scene_image, (sx, sy, sw, sh) = detect(scene)
    ref_image, (rx, ry, rw, rh) = detect(reference)

    # Scale the reference face to the scene's face box, then paste it there.
    pad = 0.45
    rx0, ry0 = max(0, int(rx - rw * pad)), max(0, int(ry - rh * pad))
    rx1 = min(ref_image.shape[1], int(rx + rw * (1 + pad)))
    ry1 = min(ref_image.shape[0], int(ry + rh * (1 + pad)))
    crop = ref_image[ry0:ry1, rx0:rx1]

    tx0, ty0 = max(0, int(sx - sw * pad)), max(0, int(sy - sh * pad))
    tx1 = min(scene_image.shape[1], int(sx + sw * (1 + pad)))
    ty1 = min(scene_image.shape[0], int(sy + sh * (1 + pad)))
    resized = cv2.resize(crop, (tx1 - tx0, ty1 - ty0), interpolation=cv2.INTER_LANCZOS4)

    blended = scene_image.copy()
    centre = ((tx0 + tx1) // 2, (ty0 + ty1) // 2)
    # An oval, not the crop rectangle. A full-white patch mask carries the
    # reference's own background and collar across with the face, and the blend
    # mask below only repairs the oval — so the rectangle's corners survive as a
    # pasted-on square of someone else's photograph.
    patch_h, patch_w = resized.shape[:2]
    patch_mask = np.zeros((patch_h, patch_w), np.uint8)
    cv2.ellipse(
        patch_mask,
        (patch_w // 2, patch_h // 2),
        (int(patch_w * 0.40), int(patch_h * 0.46)),
        0, 0, 360, 255, -1,
    )
    # seamlessClone matches the pasted skin to the scene's light before the
    # sampler ever sees it, which is what stops a visible tonal edge.
    blended = cv2.seamlessClone(resized, blended, patch_mask, centre, cv2.NORMAL_CLONE)

    mask = np.zeros(scene_image.shape[:2], np.uint8)
    cv2.ellipse(
        mask,
        centre,
        ((tx1 - tx0) // 2, (ty1 - ty0) // 2),
        0, 0, 360, 255, -1,
    )
    mask = cv2.GaussianBlur(mask, (49, 49), 0)

    out_image = scene.with_name(f"{scene.stem}_swap.png")
    out_mask = scene.with_name(f"{scene.stem}_swapmask.png")
    cv2.imwrite(str(out_image), blended)
    cv2.imwrite(str(out_mask), mask)
    return out_image, out_mask


def build_workflow(
    prompt: str,
    *,
    identity: float,
    anatomy: float,
    steps: int,
    seed: int,
    width: int,
    height: int,
    guidance: float,
    source: str | None = None,
    denoise: float = 1.0,
    mask: str | None = None,
    pulid_face: str | None = None,
    pulid_weight: float = 0.9,
) -> dict:
    """Checkpoint -> identity LoRA -> anatomy LoRA -> sample -> save.

    Order matters: identity loads first so the anatomy LoRA modifies a model that
    already knows the face, rather than competing with it for the same weights.
    """
    graph: dict = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": CHECKPOINT},
        },
    }
    # Strength 0 means "do not use it". Loading it anyway costs a file read and
    # fails outright when that LoRA is not on this pod — which is exactly what
    # happens when PuLID is carrying identity instead.
    if identity > 0:
        graph["2"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": IDENTITY_LORA,
                "strength_model": identity,
                "strength_clip": identity,
                "model": ["1", 0],
                "clip": ["1", 1],
            },
        }
    identity_model = ["2", 0] if identity > 0 else ["1", 0]
    identity_clip = ["2", 1] if identity > 0 else ["1", 1]
    graph.update({
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": identity_clip},
        },
        "5": {
            "class_type": "FluxGuidance",
            "inputs": {"guidance": guidance, "conditioning": ["4", 0]},
        },
        "6": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": denoise,
                "model": identity_model,
                "positive": ["5", 0],
                # Flux is guidance-distilled: CFG 1.0 means the negative branch
                # is never evaluated, so it only needs to be a valid conditioning.
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "james", "images": ["8", 0]},
        },
    })
    if pulid_face is not None:
        # PuLID conditions the model on a face *embedding*, so identity survives a
        # change of pose and lighting that pasting pixels cannot. It replaces the
        # identity LoRA rather than stacking with it — both compete for the face.
        graph["20"] = {
            "class_type": "PulidFluxModelLoader",
            "inputs": {"pulid_file": "pulid_flux_v0.9.1.safetensors"},
        }
        graph["21"] = {"class_type": "PulidFluxEvaClipLoader", "inputs": {}}
        graph["22"] = {
            "class_type": "PulidFluxInsightFaceLoader",
            "inputs": {"provider": "CUDA"},
        }
        graph["23"] = {"class_type": "LoadImage", "inputs": {"image": pulid_face}}
        graph["24"] = {
            "class_type": "ApplyPulidFlux",
            "inputs": {
                "model": identity_model,
                "pulid_flux": ["20", 0],
                "eva_clip": ["21", 0],
                "face_analysis": ["22", 0],
                "image": ["23", 0],
                "weight": pulid_weight,
                "start_at": 0.0,
                "end_at": 1.0,
                "fusion": "mean",
                "fusion_weight_max": 1.0,
                "fusion_weight_min": 0.0,
                "train_step": 1000,
                "use_gray": True,
            },
        }
        graph["7"]["inputs"]["model"] = ["24", 0]

    if source is not None:
        # Starting from real pixels of Jacob's face beats any LoRA this pair was
        # trained to be. Low denoise keeps the face and repaints everything else.
        graph["10"] = {"class_type": "LoadImage", "inputs": {"image": source}}
        graph["11"] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["10", 0], "vae": ["1", 2]},
        }
        graph["7"]["inputs"]["latent_image"] = ["11", 0]
        del graph["6"]

    if mask is not None:
        # SetLatentNoiseMask rather than VAEEncodeForInpaint: the latter is for
        # inpainting checkpoints and blanks the region first, which throws away
        # the composition the face has to sit in.
        graph["12"] = {"class_type": "LoadImage", "inputs": {"image": mask}}
        graph["13"] = {
            "class_type": "ImageToMask",
            "inputs": {"image": ["12", 0], "channel": "red"},
        }
        graph["14"] = {
            "class_type": "SetLatentNoiseMask",
            "inputs": {"samples": ["11", 0], "mask": ["13", 0]},
        }
        graph["7"]["inputs"]["latent_image"] = ["14", 0]

    if anatomy > 0:
        graph["3"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": ANATOMY_LORA,
                "strength_model": anatomy,
                "strength_clip": anatomy,
                "model": ["2", 0],
                "clip": ["2", 1],
            },
        }
        graph["3"]["inputs"]["model"] = identity_model
        graph["3"]["inputs"]["clip"] = identity_clip
        graph["4"]["inputs"]["clip"] = ["3", 1]
        graph["7"]["inputs"]["model"] = ["3", 0]
    return graph


def _post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{COMFY_URL}{path}", data=json.dumps(payload).encode(), headers=HEADERS
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def _get(path: str) -> dict:
    request = urllib.request.Request(f"{COMFY_URL}{path}", headers={"User-Agent": HEADERS["User-Agent"]})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def run(workflow: dict, *, timeout: float = 900) -> list[Path]:
    client_id = str(uuid.uuid4())
    queued = _post("/prompt", {"prompt": workflow, "client_id": client_id})
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise SystemExit(f"ComfyUI rejected the workflow: {json.dumps(queued)[:400]}")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = _get(f"/history/{prompt_id}")
        entry = history.get(prompt_id)
        if entry:
            status = (entry.get("status") or {}).get("status_str")
            if status == "error":
                messages = (entry.get("status") or {}).get("messages")
                raise SystemExit(f"ComfyUI errored: {json.dumps(messages)[:600]}")
            images = [
                image
                for output in (entry.get("outputs") or {}).values()
                for image in (output.get("images") or [])
            ]
            if images:
                return [_download(image) for image in images]
        time.sleep(3)
    raise SystemExit(f"ComfyUI did not finish within {timeout:.0f}s")


def _download(image: dict) -> Path:
    query = urllib.parse.urlencode(
        {
            "filename": image["filename"],
            "subfolder": image.get("subfolder", ""),
            "type": image.get("type", "output"),
        }
    )
    request = urllib.request.Request(
        f"{COMFY_URL}/view?{query}", headers={"User-Agent": HEADERS["User-Agent"]}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        data = response.read()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / image["filename"]
    target.write_bytes(data)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--identity", type=float, default=0.9)
    parser.add_argument("--anatomy", type=float, default=0.0)
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--width", type=int, default=896)
    parser.add_argument("--height", type=int, default=1152)
    parser.add_argument("--guidance", type=float, default=3.0)
    parser.add_argument("--source", help="reference image to start from (img2img)")
    parser.add_argument("--denoise", type=float, default=1.0)
    parser.add_argument("--face-from", help="reference photo to composite in before blending")
    parser.add_argument("--pulid", help="reference photo to condition identity on (face embedding)")
    parser.add_argument("--pulid-weight", type=float, default=0.9)
    parser.add_argument(
        "--inpaint-face",
        action="store_true",
        help="repaint only the face region of --source (needs --denoise below 1.0)",
    )
    args = parser.parse_args()

    source = mask_name = pulid_name = None
    if args.pulid:
        pulid_name = upload_image(Path(args.pulid).expanduser())
    if args.inpaint_face and not args.source:
        raise SystemExit("--inpaint-face needs --source (the image to repaint)")
    if args.source:
        source = upload_image(Path(args.source).expanduser())
        if args.denoise >= 1.0:
            # Denoise 1.0 discards the source entirely — silently ignoring the
            # reference the caller just supplied.
            raise SystemExit("--source needs --denoise below 1.0 (try 0.4)")
        if args.face_from:
            swapped, swap_mask = paste_face(
                Path(args.source).expanduser(), Path(args.face_from).expanduser()
            )
            source = upload_image(swapped)
            mask_name = upload_image(swap_mask)
        elif args.inpaint_face:
            mask_name = upload_image(face_mask(Path(args.source).expanduser()))

    workflow = build_workflow(
        args.prompt,
        identity=args.identity,
        anatomy=args.anatomy,
        steps=args.steps,
        seed=args.seed,
        width=args.width,
        height=args.height,
        guidance=args.guidance,
        source=source,
        denoise=args.denoise,
        mask=mask_name,
        pulid_face=pulid_name,
        pulid_weight=args.pulid_weight,
    )
    started = time.monotonic()
    try:
        paths = run(workflow)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"ComfyUI HTTP {exc.code}: {exc.read()[:300].decode(errors='replace')}")
    for path in paths:
        print(f"{time.monotonic() - started:.1f}s  {path}  ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
