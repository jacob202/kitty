"""
CLI helper functions and constants for supervisor.
"""
import json
from pathlib import Path

from rich.console import Console

from src.core.aura_loader import get_branding

_branding = get_branding()
console = Console()

LIBRARY_INDEX = Path("./data/vector_store/library.json")

# Cost per 1K tokens (input, output) in USD
_COSTS = {
    "gpt-4": (0.03, 0.06),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "anthropic/claude-3-5-sonnet": (0.003, 0.015),
    "google/gemini-2.0-flash-001": (0.0001, 0.0004),
    "openrouter/free": (0.0, 0.0),
    "google/gemini-2.0-flash-exp:free": (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "qwen/qwen3-coder:free": (0.0, 0.0),
    "deepseek/deepseek-chat": (0.00014, 0.00028),
    "qwen/qwen2.5-coder-32b-instruct": (0.00007, 0.00028),
}

def _cost(model: str, in_tok: int, out_tok: int) -> float:
    r = _COSTS.get(model, (0.0, 0.0))
    return (in_tok / 1000) * r[0] + (out_tok / 1000) * r[1]

def load_library_index() -> dict:
    return json.loads(LIBRARY_INDEX.read_text()) if LIBRARY_INDEX.exists() else {}

def p_warn(msg):  console.print(f"[yellow]⚠ {msg}[/yellow]")
def p_dim(msg):   console.print(f"[dim]{msg}[/dim]")
def p_route(msg): console.print(f"[dim]  → {msg}[/dim]")
def p_success(msg): console.print(f"[green]✓ {msg}[/green]")
def p_err(code: str, msg: str):
    """Print a structured error with a short code for easy reference."""
    console.print(f"[red]✗ [{code}][/red] {msg}")
    console.print(f"[dim]    → /help {code.lower()} for details or ask {_branding['assistant_name'].lower()}: 'what does {code} mean?'[/dim]")
