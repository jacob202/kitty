#!/usr/bin/env python3
"""
SD Agent - Natural Language to Stable Diffusion
Takes plain English descriptions, enhances with LLM, generates images

Supports: Fooocus, ComfyUI, AUTOMATIC1111
"""

import argparse
import json
import os
import sys
from datetime import datetime

import requests

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1:8b"

# Backend URLs (adjust as needed)
BACKENDS = {
    "fooocus": "http://127.0.0.1:7865",  # Fooocus default
    "comfyui": "http://127.0.0.1:8188",  # ComfyUI default
    "auto1111": "http://127.0.0.1:7860",  # A1111 default
}

PROMPT_ENHANCER_TEMPLATE = """You are an expert Stable Diffusion prompt engineer.

Convert the user's simple description into an optimized, detailed prompt.

Rules:
- Add quality tags: "masterpiece, best quality, highly detailed"
- Add style descriptors when relevant (photorealistic, anime, oil painting, etc.)
- Add lighting and atmosphere descriptors
- Keep negative prompts simple: "worst quality, low quality, blurry, deformed"

User description: {description}

Output ONLY a JSON object with this structure:
{{
    "prompt": "enhanced detailed prompt here",
    "negative_prompt": "negative descriptors",
    "style": "photorealistic|anime|oil_painting|cyberpunk|fantasy",
    "aspect_ratio": "1:1|16:9|9:16|4:3"
}}
"""


def enhance_prompt(description: str, model: str = DEFAULT_MODEL) -> dict:
    """Use Ollama to enhance the user's simple description"""

    prompt = PROMPT_ENHANCER_TEMPLATE.format(description=description)

    try:
        response = requests.post(
            OLLAMA_URL, json={"model": model, "prompt": prompt, "stream": False}
        )
        response.raise_for_status()

        # Parse the LLM response
        result = response.json()
        generated_text = result.get("response", "")

        # Extract JSON from response
        try:
            # Find JSON block
            start = generated_text.find("{")
            end = generated_text.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = generated_text[start:end]
                enhanced = json.loads(json_str)
            else:
                raise ValueError("No JSON found")

            print(f"✨ Enhanced prompt: {enhanced['prompt'][:80]}...")
            return enhanced

        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️  Couldn't parse JSON, using fallback: {e}")
            return {
                "prompt": f"{description}, masterpiece, best quality, highly detailed",
                "negative_prompt": "worst quality, low quality, blurry, deformed",
                "style": "photorealistic",
                "aspect_ratio": "1:1",
            }

    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to Ollama. Is it running?")
        print("   Start with: ollama serve")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error calling Ollama: {e}")
        sys.exit(1)


def generate_fooocus(enhanced_prompt: dict, output_dir: str = "outputs"):
    """Generate image using Fooocus API"""

    # Map aspect ratio to dimensions
    ratio_map = {
        "1:1": (1024, 1024),
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "4:3": (1024, 768),
        "3:4": (768, 1024),
    }

    width, height = ratio_map.get(enhanced_prompt.get("aspect_ratio", "1:1"), (1024, 1024))

    payload = {
        "prompt": enhanced_prompt["prompt"],
        "negative_prompt": enhanced_prompt.get("negative_prompt", ""),
        "style_selections": ["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"],
        "performance_selection": "Quality",
        "aspect_ratios_selection": f"{width}*{height}",
        "image_number": 1,
        "image_seed": -1,
        "sharpness": 2.0,
        "guidance_scale": 7.0,
        "base_model_name": "juggernautXL_version6Rundiffusion.safetensors",
        "refiner_model_name": "None",
        "loras": [],
    }

    try:
        print("🎨 Sending to Fooocus...")
        response = requests.post(
            f"{BACKENDS['fooocus']}/v1/generation/text-to-image", json=payload, timeout=300
        )
        response.raise_for_status()

        result = response.json()

        # Save images
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, img_data in enumerate(result.get("images", [])):
            import base64

            img_bytes = base64.b64decode(img_data)
            filepath = os.path.join(output_dir, f"sd_agent_{timestamp}_{i}.png")
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            print(f"✅ Saved: {filepath}")

        return result

    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to Fooocus at {BACKENDS['fooocus']}")
        print("   Start Fooocus with: python entry_with_update.py")
        return None
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        return None


def generate_auto1111(enhanced_prompt: dict, output_dir: str = "outputs"):
    """Generate image using AUTOMATIC1111 API"""

    ratio_map = {
        "1:1": (512, 512),
        "16:9": (768, 432),
        "9:16": (432, 768),
        "4:3": (640, 480),
    }

    width, height = ratio_map.get(enhanced_prompt.get("aspect_ratio", "1:1"), (512, 512))

    payload = {
        "prompt": enhanced_prompt["prompt"],
        "negative_prompt": enhanced_prompt.get("negative_prompt", ""),
        "steps": 30,
        "cfg_scale": 7,
        "width": width,
        "height": height,
        "sampler_name": "DPM++ 2M Karras",
        "n_iter": 1,
    }

    try:
        print("🎨 Sending to AUTOMATIC1111...")
        response = requests.post(
            f"{BACKENDS['auto1111']}/sdapi/v1/txt2img", json=payload, timeout=300
        )
        response.raise_for_status()

        result = response.json()

        # Save images
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, img_data in enumerate(result.get("images", [])):
            import base64

            img_bytes = base64.b64decode(img_data)
            filepath = os.path.join(output_dir, f"sd_agent_{timestamp}_{i}.png")
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            print(f"✅ Saved: {filepath}")

        return result

    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to AUTOMATIC1111 at {BACKENDS['auto1111']}")
        print("   Start with: ./webui.sh --api")
        return None
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        return None


def generate_comfyui(enhanced_prompt: dict, output_dir: str = "outputs"):
    """Generate image using ComfyUI (requires workflow setup)"""
    print("⚠️  ComfyUI support requires a pre-configured workflow.")
    print("   For now, use Fooocus or Auto1111 for simplicity.")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate images from natural language descriptions"
    )
    parser.add_argument(
        "description", nargs="+", help="Description of the image you want to generate"
    )
    parser.add_argument(
        "--backend",
        choices=["fooocus", "comfyui", "auto1111"],
        default="fooocus",
        help="Which SD backend to use (default: fooocus)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model for prompt enhancement (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--output", default="outputs", help="Output directory for generated images")
    parser.add_argument(
        "--raw", action="store_true", help="Skip LLM enhancement, use prompt directly"
    )

    args = parser.parse_args()

    # Join description arguments
    description = " ".join(args.description)

    print(f"🎯 Description: {description}")
    print(f"🤖 Using model: {args.model}")
    print(f"⚙️  Backend: {args.backend}")
    print()

    # Enhance prompt with LLM (unless --raw)
    if args.raw:
        enhanced = {
            "prompt": description,
            "negative_prompt": "worst quality, low quality",
            "style": "photorealistic",
            "aspect_ratio": "1:1",
        }
    else:
        enhanced = enhance_prompt(description, args.model)

    # Generate image
    if args.backend == "fooocus":
        generate_fooocus(enhanced, args.output)
    elif args.backend == "auto1111":
        generate_auto1111(enhanced, args.output)
    elif args.backend == "comfyui":
        generate_comfyui(enhanced, args.output)


if __name__ == "__main__":
    main()
