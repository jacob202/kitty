"""Load and cache versioned system prompts from /prompts/."""
from functools import lru_cache
from gateway.paths import PROMPTS_DIR

DOMAIN_TO_FILE = {
    "soul": "soul_v1.md",
    "repair": "repair_v1.md",
    "health": "health_v1.md",
    "research": "research_v1.md",
    "code": "code_v1.md",
}


@lru_cache(maxsize=10)
def load_prompt(domain: str) -> str:
    filename = DOMAIN_TO_FILE.get(domain, "soul_v1.md")
    path = PROMPTS_DIR / filename
    if not path.exists():
        fallback = PROMPTS_DIR / "soul_v1.md"
        if fallback.exists():
            return fallback.read_text()
        return "You are Kitty, a personal AI for Jacob Brizinski."
    return path.read_text()
