"""
Specialist router — route queries to the right specialist.
"""
from typing import Dict, Optional
import os


def route_specialist(message: str) -> Optional[str]:
    """
    Very simple router: return specialist name or None.
    Order matters: check more specific keywords first.
    """
    low = message.lower()
    if any(w in low for w in ["code", "program", "script", "function", "bug", "python", "javascript"]):
        return "alex"  # code
    if any(w in low for w in ["diagnose", "fix", "repair", "error", "broken", "car", "engine"]):
        return "mike"  # automotive
    if any(w in low for w in ["workout", "exercise", "fitness", "gym", "run", "health"]):
        return "kelly"  # fitness
    if any(w in low for w in ["research", "find", "search", "study", "paper"]):
        return "research"  # research
    return None  # no specialist matched


def get_specialist_context(name: str) -> Dict:
    """Return specialist context from config."""
    path = os.path.join("config", "specialists", f"{name}.md")
    try:
        with open(path, encoding="utf-8") as f:
            return {"name": name, "context": f.read(), "source": f"config/specialists/{name}.md"}
    except FileNotFoundError:
        return {"name": name, "context": "", "source": "not found"}
