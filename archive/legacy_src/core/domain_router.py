"""
Backward-compatible re-exports from query_router.
All new code should import directly from src.core.query_router.
"""

from src.core.query_router import (
    Domain,
    DomainClassifier,
    ModelSelector,
    ModelTier,
    QueryRouter,
    RoutingDecision,
    get_domain_config,
)

# Backward compat alias — QueryRouter replaces DomainRouter
DomainRouter = QueryRouter

__all__ = [
    "Domain",
    "DomainClassifier",
    "DomainRouter",
    "ModelSelector",
    "ModelTier",
    "QueryRouter",
    "RoutingDecision",
    "get_domain_config",
]
