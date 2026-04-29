#!/usr/bin/env python3
"""
MLX LoRA Fine-tuning Script for Kitty
Fine-tune MLX models with LoRA adapters for personalized performance.

Usage:
    python scripts/mlx_lora_train.py --model mlx-community/Qwen3.5-4B-4bit --data ./data
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import mlx.core as mx
from mlx_lm import load, generate
from mlx_lm.lora import LoRAConfig, train as lora_train


CONFIG_PATH = Path(__file__).parent.parent / "config" / "mlx_optimization.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def prepare_training_data(data_path: str) -> Path:
    data_dir = Path(data_path)
    if not data_dir.exists():
        raise ValueError(f"Data directory not found: {data_path}")
    return data_dir


def run_lora_training(
    model_name: str,
    data_path: str,
    rank: int = 8,
    layers: int = 16,
    learning_rate: float = 1e-4,
    batch_size: int = 2,
    iters: int = 200,
    adapter_path: str = "./adapters",
    mask_prompt: bool = True,
    max_seq_length: int = 1024,
):
    """Run LoRA fine-tuning on the specified model."""
    print(f"[LoRA Training] Model: {model_name}")
    print(f"[LoRA Training] Data: {data_path}")
    print(f"[LoRA Training] Rank: {rank}, Layers: {layers}, LR: {learning_rate}")

    data_dir = prepare_training_data(data_path)
    adapter_dir = Path(adapter_path)
    adapter_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3", "-m", "mlx_lm", "lora",
        "--model", model_name,
        "--train",
        "--data", str(data_dir),
        "--batch-size", str(batch_size),
        "--num-layers", str(layers),
        "--learning-rate", str(learning_rate),
        "--iters", str(iters),
        "--save-every", str(iters // 4),
        "--max-seq-length", str(max_seq_length),
        "--adapter-path", str(adapter_dir),
    ]

    if mask_prompt:
        cmd.append("--mask-prompt")

    print(f"[LoRA Training] Running: {' '.join(cmd)}")

    os.system(" ".join(cmd))

    adapter_file = adapter_dir / "adapters.npz"
    if adapter_file.exists():
        print(f"[LoRA Training] ✓ Adapters saved to {adapter_file}")
    else:
        print(f"[LoRA Training] ✗ No adapters file found")


def fuse_lora_adapter(
    model_name: str,
    adapter_path: str,
    output_path: str
):
    """Fuse LoRA adapters with the base model."""
    adapter_file = Path(adapter_path) / "adapters.npz"
    output_dir = Path(output_path)

    if not adapter_file.exists():
        print(f"[Fuse] ✗ Adapter file not found: {adapter_file}")
        return

    print(f"[Fuse] Merging adapters into {model_name}")

    cmd = [
        "python3", "-m", "mlx_lm", "fuse",
        "--model", model_name,
        "--adapter-file", str(adapter_file),
        "--save-path", str(output_dir),
    ]

    os.system(" ".join(cmd))
    print(f"[Fuse] ✓ Model saved to {output_dir}")


def generate_with_lora(
    model_name: str,
    adapter_path: str,
    prompt: str,
    max_tokens: int = 150,
    temperature: float = 0.7
):
    """Generate text using a LoRA-fine-tuned model."""
    model_path = Path(adapter_path)
    if model_path.is_dir() and (model_path / "adapters.npz").exists():
        model_dir = model_path
    elif model_path.is_dir():
        model_dir = model_name
    else:
        model_dir = model_name

    try:
        model, tokenizer = load(str(model_dir))
        result = generate(
            model, tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temperature
        )
        return result
    except Exception as e:
        print(f"[Generate] Error: {e}")
        return None


def benchmark_model(
    model_name: str,
    adapter_path: Optional[str] = None
):
    """Benchmark model loading and inference speed."""
    import time

    print(f"[Benchmark] Testing {model_name}")

    start = time.time()
    model, tokenizer = load(model_name)
    load_time = time.time() - start

    prompts = [
        "Write a Python function to calculate factorial:",
        "Explain quantum computing in one sentence:",
        "What is 2 + 2?",
    ]

    total_tokens = 0
    total_time = 0

    for prompt in prompts:
        start = time.time()
        result = generate(model, tokenizer, prompt=prompt, max_tokens=50, verbose=False)
        gen_time = time.time() - start
        tokens = len(result.split())
        total_tokens += tokens
        total_time += gen_time
        print(f"  Prompt: {prompt[:40]}... -> {tokens} tokens in {gen_time:.2f}s")

    print(f"\n[Benchmark] Load: {load_time:.2f}s, Avg: {total_time/len(prompts):.2f}s/prompt")


def main():
    parser = argparse.ArgumentParser(description="MLX LoRA fine-tuning for Kitty")
    parser.add_argument("--model", default="mlx-community/Qwen3.5-4B-4bit", help="Model to fine-tune")
    parser.add_argument("--data", required=True, help="Training data directory")
    parser.add_argument("--rank", type=int, default=8, help="LoRA rank")
    parser.add_argument("--layers", type=int, default=16, help="Number of LoRA layers")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--iters", type=int, default=200, help="Training iterations")
    parser.add_argument("--adapter-path", default="./adapters", help="Adapter output path")
    parser.add_argument("--mode", choices=["train", "fuse", "generate", "benchmark"], default="train")
    parser.add_argument("--output", help="Output path for fused model")
    parser.add_argument("--prompt", help="Prompt for generation mode")

    args = parser.parse_args()

    config = load_config()
    lora_conf = config.get("lora_config", {})

    if args.mode == "train":
        run_lora_training(
            model_name=args.model,
            data_path=args.data,
            rank=args.rank,
            layers=args.layers,
            learning_rate=args.lr,
            iters=args.iters,
            adapter_path=args.adapter_path,
            mask_prompt=lora_conf.get("mask_prompt", True)
        )
    elif args.mode == "fuse":
        if not args.output:
            print("--output required for fuse mode")
            sys.exit(1)
        fuse_lora_adapter(args.model, args.adapter_path, args.output)
    elif args.mode == "generate":
        result = generate_with_lora(args.model, args.adapter_path, args.prompt or "Hello")
        print(f"\n[Result]\n{result}")
    elif args.mode == "benchmark":
        benchmark_model(args.model, args.adapter_path)


if __name__ == "__main__":
    main()