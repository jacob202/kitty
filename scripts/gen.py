#!/usr/bin/env python3
"""Quick fal.ai image generator. Usage: python3 gen.py "your prompt here" """
import sys, os, fal_client

if len(sys.argv) < 2:
    print("Usage: gen.py \"prompt\" [num_images]")
    sys.exit(1)

prompt = sys.argv[1]
num = int(sys.argv[2]) if len(sys.argv) > 2 else 4

result = fal_client.run(
    "fal-ai/flux-pro/v1.1-ultra",
    arguments={"prompt": prompt, "num_images": num},
)

for img in result.get("images", []):
    print(img["url"])
