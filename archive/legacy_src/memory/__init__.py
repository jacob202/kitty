import sys

# Try to import LightRAGStore, but if LightRAG itself has missing dependencies,
# we still want to be able to import this module
try:
    from .lightrag_store import LightRAGStore
    # Test that LightRAG can actually be loaded
    try:
        _ = LightRAGStore.__module__
    except Exception:
        LightRAGStore = None
except Exception:
    LightRAGStore = None
