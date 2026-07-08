"""Deterministic hashing for expert topics.

Used for deduplication, cooldowns, and user feedback (dismissals).
"""
import hashlib
import re

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
    "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were",
    "will", "with", "this", "these", "those"
}

def generate_topic_hash(expert_id: str, text: str) -> str:
    """Generate a deterministic hash from text for an expert.

    Normalizes the text by:
    1. Extracting a subsystem name if present (e.g., from CSV filenames)
    2. Lowercasing and removing punctuation
    3. Removing common stopwords
    4. Simple stemming
    """
    # Try to extract subsystem from "CSV Data (filename):"
    m = re.search(r"CSV Data \((.*?)\)", text)
    if m:
        base = m.group(1).split(".")[0]
        normalized = re.sub(r'[^a-z0-9\s]', ' ', base.lower())
    else:
        # Take the first line or up to 100 chars
        first_line = text.splitlines()[0][:100]
        normalized = re.sub(r'[^a-z0-9\s]', ' ', first_line.lower())

    words = normalized.split()

    stemmed = []
    for w in words:
        if w in STOPWORDS:
            continue

        # Very simple stemming
        if w.endswith("ing") and len(w) > 4:
            w = w[:-3]
        elif w.endswith("ed") and len(w) > 3:
            w = w[:-2]
        elif w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
            w = w[:-1]

        stemmed.append(w)

    core_text = " ".join(stemmed)

    # Combine with expert_id to keep hashes scoped
    payload = f"{expert_id}::{core_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
