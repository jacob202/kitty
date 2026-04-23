"""
Supervisor Error Handling - Decorators and utilities for robust error handling.

Provides:
1. @handle_errors decorator for Supervisor methods
2. Automatic retry logic with exponential backoff
3. Structured logging with context
4. Graceful fallbacks for API failures
"""

import functools
import logging
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class SupervisorError(Exception):
    """Base exception for Supervisor errors."""

    def __init__(self, message: str, error_type: str = "UNKNOWN", details: dict = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class ModelCallError(SupervisorError):
    """Raised when LLM model calls fail."""

    def __init__(self, message: str, model: str = None, details: dict = None):
        super().__init__(message, error_type="MODEL_CALL", details=details or {})
        self.model = model


class ToolExecutionError(SupervisorError):
    """Raised when tool execution fails."""

    def __init__(self, message: str, tool_name: str = None, details: dict = None):
        super().__init__(message, error_type="TOOL_EXECUTION", details=details or {})
        self.tool_name = tool_name


def handle_errors(
    retry_count: int = 3,
    retry_delay: float = 1.0,
    fallback_value: Any = None,
    log_traceback: bool = True,
    raise_on_final_failure: bool = False,
):
    """
    Decorator for robust error handling in Supervisor methods.

    Args:
        retry_count: Number of retry attempts (default: 3)
        retry_delay: Initial delay between retries in seconds (exponential backoff)
        fallback_value: Value to return if all retries fail (default: None)
        log_traceback: Whether to log full traceback (default: True)
        raise_on_final_failure: If True, re-raise exception after all retries fail

    Usage:
        @handle_errors(retry_count=3, fallback_value="Error occurred")
        def supervisor_method(self, ...):
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception = None

            for attempt in range(1, retry_count + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(f"{func.__name__} succeeded on attempt {attempt}/{retry_count}")
                    return result

                except Exception as e:
                    last_exception = e
                    error_msg = (
                        f"{func.__name__} failed (attempt {attempt}/{retry_count}): {str(e)}"
                    )

                    if log_traceback and attempt == retry_count:
                        logger.error(f"{error_msg}\n{traceback.format_exc()}")
                    else:
                        logger.warning(error_msg)

                    # Don't retry on final attempt
                    if attempt < retry_count:
                        delay = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                        logger.debug(f"Retrying in {delay}s...")
                        time.sleep(delay)

            # All retries exhausted
            logger.error(
                f"{func.__name__} failed after {retry_count} attempts. "
                f"Final error: {last_exception}"
            )

            if raise_on_final_failure:
                raise last_exception

            return fallback_value

        return wrapper

    return decorator


def log_context(context_name: str):
    """
    Decorator to add context logging to Supervisor methods.

    Logs method entry/exit and execution time.

    Usage:
        @log_context("supervisor_run")
        def run(self, query):
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time.time()
            logger.debug(f"[{context_name}] Starting {func.__name__}")

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.debug(f"[{context_name}] Completed {func.__name__} in {elapsed:.2f}s")
                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[{context_name}] Failed {func.__name__} after {elapsed:.2f}s: {e}")
                raise

        return wrapper

    return decorator


def safe_model_call(
    supervisor_instance,
    prompt: str,
    model: str = None,
    max_tokens: int = 1000,
    fallback_model: str = "deepseek/deepseek-chat",
) -> str | None:
    """
    Safe model call with automatic fallback and error handling.

    Args:
        supervisor_instance: Supervisor instance with model_caller
        prompt: User prompt
        model: Primary model to use (defaults to flash_model from config)
        max_tokens: Max tokens for response
        fallback_model: Fallback model if primary fails

    Returns:
        Response text or None if all attempts fail
    """
    if not model:
        model = supervisor_instance.config.get("flash_model", fallback_model)

    try:
        # Try primary model
        response = supervisor_instance.model_caller.call_model(
            prompt=prompt, model=model, max_tokens=max_tokens
        )
        return response

    except Exception as primary_error:
        logger.warning(f"Primary model {model} failed: {primary_error}")

        # Try fallback model
        try:
            logger.info(f"Attempting fallback model: {fallback_model}")
            response = supervisor_instance.model_caller.call_model(
                prompt=prompt, model=fallback_model, max_tokens=max_tokens
            )
            return response

        except Exception as fallback_error:
            logger.error(f"Fallback model {fallback_model} also failed: {fallback_error}")
            raise ModelCallError(
                f"Both primary ({model}) and fallback ({fallback_model}) models failed",
                model=model,
                details={
                    "primary_error": str(primary_error),
                    "fallback_error": str(fallback_error),
                },
            )


def log_supervisor_error(
    error: Exception,
    context: dict = None,
    log_file: str = "data/logs/supervisor_errors.log",
):
    """
    Log Supervisor error to structured file and stderr.

    Args:
        error: Exception that occurred
        context: Additional context dict (query, model, tool, etc.)
        log_file: Path to error log file
    """
    import json
    from datetime import datetime

    error_entry = {
        "timestamp": datetime.now().isoformat(),
        "error_type": type(error).__name__,
        "message": str(error),
        "context": context or {},
        "traceback": traceback.format_exc(),
    }

    # Log to stderr
    logger.error(f"Supervisor error: {json.dumps(error_entry, indent=2)}")

    # Append to log file
    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as f:
            f.write(json.dumps(error_entry) + "\n")

    except Exception as log_error:
        logger.error(f"Failed to write error log: {log_error}")


# Example usage patterns (for documentation)
__doc__ += """

## Usage Examples

### Basic error handling with retry:

```python
from src.utils.supervisor_error_handler import handle_errors

class Supervisor:
    @handle_errors(retry_count=3, retry_delay=1.0)
    def call_model(self, prompt: str):
        # This will retry up to 3 times with exponential backoff
        return self.model_caller.call(prompt)
```

### Safe model call with fallback:

```python
from src.utils.supervisor_error_handler import safe_model_call

response = safe_model_call(
    supervisor_instance=self,
    prompt="Analyze this data",
    model="gemini/gemini-2.0-flash",
    fallback_model="deepseek/deepseek-chat"
)
```

### Context logging:

```python
from src.utils.supervisor_error_handler import log_context

class Supervisor:
    @log_context("supervisor_run")
    @handle_errors(retry_count=2)
    def run(self, query: str):
        # Logs entry, exit, timing, and errors
        return self._process_query(query)
```
"""
