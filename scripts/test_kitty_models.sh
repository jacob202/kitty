#!/usr/bin/env bash
# filename: test_kitty_models.sh
# Run from your kitty project root with: bash test_kitty_models.sh
set -e

# Ensure we are in the venv
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Please activate your project venv first."
    exit 1
fi

# We use 3B models to avoid Out Of Memory errors on smaller Apple Silicon chips.
MODELS=(
    "mlx-community/Qwen2.5-3B-Instruct-4bit"
    "mlx-community/Llama-3.2-3B-Instruct-4bit"
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
    python3 -c "from mlx_lm import load; load('$model')" 2>/dev/null || true
    echo "Model ready."

    for prompt in "${PROMPTS[@]}"; do
        echo "--------------------------------------------------"
        echo "MODEL: $model"
        echo "PROMPT: ${prompt:0:80}..."
        
        # Measure timing and generate response
        out=$(python3 -c "
from mlx_lm import load, generate
import time

try:
    model, tokenizer = load('$model')
    start_time = time.time()
    response = generate(model, tokenizer, prompt='$prompt', max_tokens=150, temp=0.7)
    end_time = time.time()
    
    elapsed = end_time - start_time
    # Approximate token count by splitting spaces
    tokens = len(response.split())
    tps = tokens / elapsed if elapsed > 0 else 0
    
    print(f'__RESULT_START__')
    print(f'{elapsed:.2f}|{tokens}|{tps:.1f}')
    print(response)
    print(f'__RESULT_END__')
except Exception as e:
    print(f'__RESULT_START__')
    print(f'0|0|0')
    print(f'ERROR: {e}')
    print(f'__RESULT_END__')
" 2>/dev/null)
        
        # Parse the python output
        elapsed=$(echo "$out" | grep -A 1 "__RESULT_START__" | tail -n 1 | cut -d'|' -f1)
        tokens=$(echo "$out" | grep -A 1 "__RESULT_START__" | tail -n 1 | cut -d'|' -f2)
        tps=$(echo "$out" | grep -A 1 "__RESULT_START__" | tail -n 1 | cut -d'|' -f3)
        response=$(echo "$out" | awk '/__RESULT_START__/{flag=1; getline; getline; next} /__RESULT_END__/{flag=0} flag')
        
        echo "Response: $response"
        echo "Time: ${elapsed}s, Tokens: $tokens, Tok/s: $tps"
        quality="?"
        echo "Quality (1-5): $quality"
        
        # Append to results
        # Strip newlines from response for the CSV, or just replace with space
        clean_response=$(echo "$response" | tr '\n' ' ' | sed 's/"/""/g')
        echo "\"$model\", \"${prompt:0:50}\", $elapsed, $tokens, $tps, $quality, \"$clean_response\"" >> "$RESULTS_FILE"
        echo ""
    done
done

echo "=== Benchmark Complete ==="
echo "Open $RESULTS_FILE and assign quality scores (1-5) for each response."
echo ""
echo "The file model_loader.py has been created in your project."
echo "Please edit model_loader.py's TASK_MODEL_MAP to assign the best model per task."