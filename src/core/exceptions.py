"""Centralized exception handling for Project Kitty."""

import functools
import logging
import traceback
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("kitty.core.exceptions")

class KittyError(Exception):
    """Base class for all Kitty exceptions."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}

class RoutingError(KittyError):
    """Raised when the domain router fails."""
    pass

class SpecialistError(KittyError):
    """Raised when a specialist fails to process a query."""
    pass

class MemoryError(KittyError):
    """Raised when memory retrieval or ingestion fails."""
    pass

class IngestionError(MemoryError):
    """Raised specifically during file ingestion."""
    pass

def handle_exception(e: Exception, context: str = "general", silent: bool = False):
    """
    Standard entry point for handling exceptions.
    Logs the error with context and traceback.
    """
    error_type = type(e).__name__
    msg = f"[{context}] {error_type}: {str(e)}"

    if not silent:
        logger.error(msg)
        logger.debug(traceback.format_exc())
    else:
        # Even if 'silent', we should at least leave a trail in debug
        logger.debug(f"Silenced {msg}")

def safe_execution(context: str = "execution", fallback_return: Any = None):
    """Decorator for safely executing functions with automatic logging."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handle_exception(e, context=f"{context}.{func.__name__}")
                return fallback_return
        return wrapper
    return decorator
