#!/usr/bin/env bash
# filename: test_kitty_models.sh
# Run from your kitty project root with: bash test_kitty_models.sh
set -e

# Ensure we are in the venv
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Please activate your project venv first."
    exit 1
fi

# Models to test (all 8B community fine‑tunes in MLX format)
MODELS=(
    "mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit"
    "mlx-community/Orchestrator-8B-4bit"
    "mlx-community/Qwen3-8B-4bit"
)

# A set of Kitty‑specific prompts that cover routing, conversation, and domain knowledge.
# Each prompt is tested with a system message that includes the SOUL.md and domain context.
PROMPTS=(
    "System: You are Kitty, a quiet capable presence who knows Jacob. You are speaking to Jacob.\nUser: im okay a little sad and overwhelmed how're you doing"
    "System: You are the Automotive specialist for Kitty. You answer Ridgeline questions using data.\nUser: my 2007 Ridgeline has a shudder when I accelerate from a stop"
    "System: You are the router. Decide which specialist (auto, fitness, growth, code, chat) should handle this query. Reply with just the specialist name.\nUser: how do i fix the clear coat on the hood"
)

echo "=== Kitty Model Benchmark ==="
echo "Testing models: ${MODELS[*]}"
echo ""

# Prepare the results file
RESULTS_FILE="model_test_results_$(date +%Y%m%d_%H%M%S).txt"
echo "Results will be saved to $RESULTS_FILE"
echo "Model, Prompt, Time(s), Tokens, Tok/s, Quality(1-5), Notes" > "$RESULTS_FILE"

for model in "${MODELS[@]}"; do
    echo "--- Pulling/Downloading $model (if not cached) ---"
    # Pre-fetch the model: mlx-lm will cache it automatically on first use
    python3 -c "from mlx_lm import load; load('$model')" 2>/dev/null || true
    echo "Model ready."

    for prompt in "${PROMPTS[@]}"; do
        echo "--------------------------------------------------"
        echo "MODEL: $model"
        echo "PROMPT: ${prompt:0:80}..."
        # Measure timing
        start=$(python3 -c "import time; print(time.time())")
        # Generate (max 150 tokens). Capture output.
        out=$(python3 -c "
from mlx_lm import generate
import time
response = generate('$model', prompt='$prompt', max_tokens=150, temp=0.7)
print(response)
" 2>/dev/null)
        end=$(python3 -c "import time; print(time.time())")
        elapsed=$(python3 -c "print(f'{float($end)-float($start):.2f}')")
        # Count tokens (approximate by splitting)
        tokens=$(echo "$out" | wc -w | tr -d ' ')
        # tokens/s
        tps=$(python3 -c "print(f'{int($tokens)/float($elapsed):.1f}' if float($elapsed)>0 else '0')")
        echo "Response: $out"
        echo "Time: ${elapsed}s, Tokens: $tokens, Tok/s: $tps"
        # Quick quality score (1-5) – you decide. I'll put a placeholder.
        quality="?"  # You will manually fill this in after reading the response.
        echo "Quality (1-5): $quality"
        # Append to results
        echo "$model, \"${prompt:0:50}\", $elapsed, $tokens, $tps, $quality, " >> "$RESULTS_FILE"
        echo ""
    done
done

echo "=== Benchmark Complete ==="
echo "Open $RESULTS_FILE and assign quality scores (1-5) for each response."
echo ""
echo "The file model_loader.py has been created in your project."
echo "Please edit model_loader.py's TASK_MODEL_MAP to assign the best model per task."