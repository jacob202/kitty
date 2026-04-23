import base64
from pathlib import Path

import requests


class DrawThingsGenerator:
    def __init__(self, base_url="http://127.0.0.1:8080"):
        self.base_url = base_url
        self.output_folder = Path("./outputs")
        self.output_folder.mkdir(exist_ok=True)

    def generate(self, prompt, trigger_word="", negative_prompt="bad anatomy, blurry"):
        full_prompt = f"{trigger_word}, {prompt}, photorealistic, 8K, natural lighting"
        payload = {
            "prompt": full_prompt,
            "negative_prompt": negative_prompt,
            "steps": 20,
            "seed": -1
        }
        try:
            response = requests.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload)
            response.raise_for_status()
            r = response.json()

            # Draw Things API returns base64 string
            image_data = base64.b64decode(r['images'][0])
            safe_prompt = "".join(c for c in prompt if c.isalnum() or c in " _-")[:30]
            out_path = self.output_folder / f"drawthings_{safe_prompt}.png"

            with open(out_path, 'wb') as f:
                f.write(image_data)

            return f"Success: Image saved to {out_path}"
        except Exception as e:
            return f"Error reaching Draw Things: {str(e)}"
