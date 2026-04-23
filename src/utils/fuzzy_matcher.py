"""
Fuzzy matching utility for component IDs and technical terms.
Provides spell-check and typo tolerance for RAG queries.
"""

import difflib
import re

COMPONENT_PATTERN = re.compile(r"([RC]|TR|C|Q|L|U|J|P|M)\d{1,4}[A-Z]?", re.IGNORECASE)


def normalize_component_id(text: str) -> str:
    """Normalize component ID format: R761 -> r761, r 7 6 1 -> r761"""
    text = text.upper().replace(" ", "")
    text = re.sub(r"([RC])\s*(\d)", r"\1\2", text)
    text = re.sub(r"(\d)\s*([A-Z])", r"\1\2", text)
    return text


def fuzzy_match(
    query: str,
    candidates: list[str],
    cutoff: float = 0.6,
    max_results: int = 3,
) -> list[tuple[str, float]]:
    """
    Find fuzzy matches for query in candidate list.

    Returns: List of (candidate, score) tuples sorted by score.
    """
    query_norm = normalize_component_id(query)
    matches = difflib.get_close_matches(
        query_norm, candidates, n=max_results, cutoff=cutoff
    )
    if not matches:
        return []

    scores = []
    for match in matches:
        score = difflib.SequenceMatcher(None, query_norm, match).ratio()
        scores.append((match, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:max_results]


def extract_component_ids(text: str) -> list[str]:
    """Extract component IDs from text (R101, C47, TR5, etc)."""
    return COMPONENT_PATTERN.findall(text.upper())


def fix_typo(query: str, known_components: list[str]) -> str:
    """
    Fix typos in component ID query using fuzzy matching.

    If no exact match, finds closest match in known_components.
    """
    extracted = extract_component_ids(query)
    if not extracted:
        return query

    for comp in extracted:
        if comp in known_components:
            continue

        matches = fuzzy_match(comp, known_components, cutoff=0.5)
        if matches:
            best_match, score = matches[0]
            if score > 0.7:
                query = query.replace(comp, best_match)

    return query


def tokenize_query(query: str) -> list[str]:
    """Split query into tokens for search."""
    query = normalize_component_id(query)
    tokens = re.split(r"[\s,\-_]+", query)
    return [t for t in tokens if t]


def expand_query(query: str, known_components: list[str]) -> list[str]:
    """
    Expand query with fuzzy variations for robust RAG retrieval.

    Returns list of query variations to try.
    """
    variations = [query]

    extracted = extract_component_ids(query)
    for comp in extracted:
        matches = fuzzy_match(comp, known_components, cutoff=0.4, max_results=2)
        for match, score in matches:
            if match != comp:
                variations.append(query.replace(comp, match))

    return variations[:5]
