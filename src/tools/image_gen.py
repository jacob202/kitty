import base64
import json
from pathlib import Path

import requests


class DrawThingsGenerator:
    def __init__(self, base_url="http://127.0.0.1:7859"):
        self.base_url = base_url
        self.output_folder = Path("./outputs")
        self.output_folder.mkdir(exist_ok=True)

    def generate(self, prompt, trigger_word="", negative_prompt="", seed=-1):
        full_prompt = f"{trigger_word}, {prompt}" if trigger_word else prompt
        payload = {
            "prompt": full_prompt,
            "negative_prompt": negative_prompt or "blurry, low quality",
            "seed": seed,
            "steps": 28,
            "width": 1024,
            "height": 1024,
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=300)
            r = response.json()

            if "images" in r and r["images"]:
                image_data = base64.b64decode(r['images'][0])
            elif "image" in r:
                image_data = base64.b64decode(r['image'])
            else:
                return f"Error: Unexpected response: {list(r.keys())}"

            safe_prompt = "".join(c for c in prompt if c.isalnum() or c in " _-")[:30]
            out_path = self.output_folder / f"drawthings_{safe_prompt}.png"

            with open(out_path, 'wb') as f:
                f.write(image_data)

            return f"Success: Image saved to {out_path}"
        except Exception as e:
            return f"Error reaching Draw Things: {str(e)}"
