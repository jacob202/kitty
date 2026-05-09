#!/bin/bash
# Start the MLX local model server for private/sensitive queries
# Model: Qwen3.5-4B-4bit — stays on device, never calls cloud APIs
set -e

echo "Starting MLX LM server on port 8010..."
echo "Model: mlx-community/Qwen3.5-4B-4bit"
echo "Used for: medical, financial, and other sensitive queries"
python3 -m mlx_lm.server \
    --model mlx-community/Qwen3.5-4B-4bit \
    --port 8010 \
    --host 0.0.0.0
