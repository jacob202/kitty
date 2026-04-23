#!/usr/bin/env python3
"""
SD Agent - Image-to-Image Edition
Upload an image, describe what you want changed, LLM enhances and generates variations
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1:8b"

# Backend URLs
BACKENDS = {
    "fooocus": "http://127.0.0.1:7865",
    "auto1111": "http://127.0.0.1:7860",
}

IMG2IMG_PROMPT_TEMPLATE = """You are an expert at image-to-image generation prompts.

User wants to transform an image with this description: {description}

Create an optimized prompt for img2img generation.

Important:
- Describe the desired changes clearly
- Include the overall style/mood
- Mention quality enhancers
- Set appropriate denoising guidance

Output ONLY a JSON object:
{{
    "prompt": "detailed transformation description",
    "negative_prompt": "what to avoid",
    "denoising_strength": 0.7,
    "style_preservation": "high|medium|low"
}}

Denoising strength guide:
- 0.3 = Subtle changes (keep structure)
- 0.5 = Moderate changes (balance)
- 0.7 = Heavy changes (creative)
- 0.9 = Almost complete redraw
"""


def encode_image_to_base64(image_path: str) -> str:
    """Convert image to base64 string"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def enhance_img2img_prompt(description: str, model: str = DEFAULT_MODEL) -> dict:
    """Use LLM to create optimal img2img prompt"""

    prompt = IMG2IMG_PROMPT_TEMPLATE.format(description=description)

    try:
        response = requests.post(
            OLLAMA_URL, json={"model": model, "prompt": prompt, "stream": False}
        )
        response.raise_for_status()

        result = response.json()
        generated = result.get("response", "")

        # Extract JSON
        start = generated.find("{")
        end = generated.rfind("}") + 1
        if start != -1 and end != -1:
            enhanced = json.loads(generated[start:end])
        else:
            raise ValueError("No JSON")

        print(f"✨ Enhancement: {enhanced['prompt'][:60]}...")
        print(f"⚙️  Denoising: {enhanced.get('denoising_strength', 0.7)}")
        return enhanced

    except Exception as e:
        print(f"⚠️  Using defaults: {e}")
        return {
            "prompt": description,
            "negative_prompt": "worst quality, low quality",
            "denoising_strength": 0.7,
            "style_preservation": "medium",
        }


def img2img_fooocus(image_path: str, enhanced: dict, output_dir: str = "outputs"):
    """Image-to-image with Fooocus"""

    image_b64 = encode_image_to_base64(image_path)

    payload = {
        "prompt": enhanced["prompt"],
        "negative_prompt": enhanced.get("negative_prompt", ""),
        "style_selections": ["Fooocus V2", "Fooocus Enhance"],
        "performance_selection": "Quality",
        "aspect_ratios_selection": "1024*1024",
        "image_number": 1,
        "image_seed": -1,
        "sharpness": 2.0,
        "guidance_scale": 7.0,
        "input_image": image_b64,
        "input_image_mask": None,
        "image_prompts": [],
    }

    try:
        print("🎨 Processing image with Fooocus...")
        response = requests.post(
            f"{BACKENDS['fooocus']}/v1/generation/image-prompt", json=payload, timeout=300
        )
        response.raise_for_status()

        result = response.json()

        # Save
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, img_data in enumerate(result.get("images", [])):
            img_bytes = base64.b64decode(img_data)
            filepath = os.path.join(output_dir, f"sd_agent_img2img_{timestamp}_{i}.png")
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            print(f"✅ Saved: {filepath}")

    except Exception as e:
        print(f"❌ Error: {e}")


def img2img_auto1111(image_path: str, enhanced: dict, output_dir: str = "outputs"):
    """Image-to-image with Auto1111"""

    image_b64 = encode_image_to_base64(image_path)

    payload = {
        "init_images": [image_b64],
        "prompt": enhanced["prompt"],
        "negative_prompt": enhanced.get("negative_prompt", ""),
        "denoising_strength": enhanced.get("denoising_strength", 0.7),
        "steps": 30,
        "cfg_scale": 7,
        "width": 512,
        "height": 512,
        "sampler_name": "DPM++ 2M Karras",
    }

    try:
        print("🎨 Processing image with Auto1111...")
        response = requests.post(
            f"{BACKENDS['auto1111']}/sdapi/v1/img2img", json=payload, timeout=300
        )
        response.raise_for_status()

        result = response.json()

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, img_data in enumerate(result.get("images", [])):
            img_bytes = base64.b64decode(img_data)
            filepath = os.path.join(output_dir, f"sd_agent_img2img_{timestamp}_{i}.png")
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            print(f"✅ Saved: {filepath}")

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Transform images using natural language")
    parser.add_argument("image", help="Path to source image")
    parser.add_argument("description", nargs="+", help="Description of changes you want")
    parser.add_argument("--backend", choices=["fooocus", "auto1111"], default="fooocus")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", default="outputs")
    parser.add_argument("--strength", type=float, help="Override denoising strength (0.1-0.9)")

    args = parser.parse_args()

    # Check image exists
    if not os.path.exists(args.image):
        print(f"❌ Image not found: {args.image}")
        sys.exit(1)

    description = " ".join(args.description)
    print(f"🖼️  Source: {args.image}")
    print(f"🎯 Changes: {description}")
    print()

    # Enhance prompt
    enhanced = enhance_img2img_prompt(description, args.model)

    # Override strength if specified
    if args.strength:
        enhanced["denoising_strength"] = args.strength
        print(f"⚙️  Denoising overridden: {args.strength}")

    # Generate
    if args.backend == "fooocus":
        img2img_fooocus(args.image, enhanced, args.output)
    elif args.backend == "auto1111":
        img2img_auto1111(args.image, enhanced, args.output)


if __name__ == "__main__":
    main()
