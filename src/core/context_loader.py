"""
Domain context loading and management.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONTEXTS_DIR = Path.home() / "Documents/Kitty/contexts"


def load_domain_contexts() -> dict[str, dict]:
    """Load all domain context JSON files from ~/Documents/Kitty/contexts/."""
    contexts = {}
    if CONTEXTS_DIR.exists():
        for f in CONTEXTS_DIR.glob("*.json"):
            try:
                contexts[f.stem] = json.loads(f.read_text())
            except Exception as e:
                logger.warning(f"Failed to load context {f}: {e}")
    return contexts


def select_contexts(query: str, contexts: dict[str, dict]) -> list[dict]:
    """Return contexts relevant to this query based on keyword matching.
    preferences.json is always injected."""
    query_lower = query.lower()
    selected = []

    # Always include preferences if it exists
    if "preferences" in contexts:
        selected.append(contexts["preferences"])

    # Score other contexts based on keyword matches
    for name, ctx in contexts.items():
        if name == "preferences":
            continue  # Already handled

        keywords = ctx.get("keywords", [])
        if any(kw.lower() in query_lower for kw in keywords):
            # Calculate relevance score
            score = sum(1 for kw in keywords if kw.lower() in query_lower)
            selected.append({**ctx, "_relevance_score": score, "_domain": name})

    # Sort by relevance score (highest first)
    selected = sorted(
        [ctx for ctx in selected if not ctx.get("always_inject", False)],
        key=lambda x: x.get("_relevance_score", 0),
        reverse=True,
    )

    # Limit to top 3 most relevant contexts to avoid token bloat
    return selected[:3]


def format_context_block(contexts: list[dict]) -> str:
    """Format selected domain contexts for injection into system prompt."""
    if not contexts:
        return ""

    parts = ["## Active Domain Context"]
    for ctx in contexts:
        domain = ctx.get("domain", ctx.get("_domain", "unknown"))
        # Exclude internal fields from the injected block
        summary = {
            k: v
            for k, v in ctx.items()
            if not k.startswith("_")
            and k not in ("keywords", "index_paths", "always_inject", "domain", "description")
        }

        if summary:  # Only include if there's actual content
            parts.append(f"\n### {domain.upper()}")
            parts.append(json.dumps(summary, indent=2))

    return "\n".join(parts) if len(parts) > 1 else ""
