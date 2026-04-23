"""
Semantic Router for Space Kitty.
Uses sentence-transformers for local embedding-based domain classification.
"""

import logging
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Use a lightweight, fast model
MODEL_NAME = "all-MiniLM-L6-v2"


class SemanticRouter:
    """
    Semantic router that maps queries to domains using vector similarity.
    """

    def __init__(self, domains: dict[str, Any]):
        """
        Args:
            domains: Dict mapping domain names to their config (must include description/keywords)
        """
        self.domains = domains
        self.domain_names = list(domains.keys())

        try:
            self.model = SentenceTransformer(MODEL_NAME)
            self._precompute_domain_embeddings()
            self.enabled = True
        except Exception as e:
            logger.warning(f"Failed to load SemanticRouter model ({MODEL_NAME}): {e}")
            self.enabled = False

    def _precompute_domain_embeddings(self):
        """Precompute embeddings for each domain based on its description and keywords."""
        self.domain_embeddings = []
        for name in self.domain_names:
            config = self.domains[name]
            # Combine description and top keywords for a rich semantic anchor
            keywords = ", ".join(config.get("keywords", [])[:10])
            text = f"{config.get('description', '')} {keywords}"
            embedding = self.model.encode(text)
            self.domain_embeddings.append(embedding)

        self.domain_embeddings = np.array(self.domain_embeddings)

    def route(self, query: str, threshold: float = 0.3) -> tuple[str | None, float]:
        """
        Route a query to the most similar domain.

        Returns:
            (domain_name, confidence) or (None, 0.0)
        """
        if not self.enabled or not query:
            return None, 0.0

        query_embedding = self.model.encode(query)

        # Cosine similarity
        similarities = np.dot(self.domain_embeddings, query_embedding) / (
            np.linalg.norm(self.domain_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        best_idx = np.argmax(similarities)
        confidence = float(similarities[best_idx])

        if confidence >= threshold:
            return self.domain_names[best_idx], confidence

        return None, confidence
