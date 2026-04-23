#!/usr/bin/env python3
"""
Retry and Fallback Logic for Kitty
Handles model failures gracefully with retries and fallbacks
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    max_attempts: int = 3
    initial_delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior"""

    models: list[str]  # Fallback model list
    enabled: bool = True


class RetryHandler:
    """Handles retry logic with customizable strategies"""

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt"""
        if self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.initial_delay * attempt
        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.initial_delay * (self.config.backoff_multiplier ** (attempt - 1))
        else:  # CONSTANT
            delay = self.config.initial_delay

        return min(delay, self.config.max_delay)

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry"""
        last_error = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_attempts:
                    delay = self.get_delay(attempt)
                    logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)

        raise last_error


class FallbackHandler:
    """Handles model fallbacks"""

    def __init__(self, primary_model: str, fallback_models: list[str]):
        self.primary = primary_model
        self.fallbacks = fallback_models
        self.current_index = 0

    def get_current_model(self) -> str:
        """Get current model to try"""
        if self.current_index == 0:
            return self.primary
        return self.fallbacks[self.current_index - 1]

    def try_next(self) -> bool:
        """Try next fallback model"""
        if self.current_index < len(self.fallbacks):
            self.current_index += 1
            return True
        return False

    def reset(self):
        """Reset to primary model"""
        self.current_index = 0

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with fallback"""
        self.reset()

        while True:
            model = self.get_current_model()
            try:
                logger.info(f"Trying model: {model}")
                kwargs["model"] = model
                return func(*args, **kwargs)
            except Exception as e:
                if not self.try_next():
                    raise e


def with_retry(config: RetryConfig = None):
    """Decorator to add retry to a function"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = RetryHandler(config)
            return handler.execute(func, *args, **kwargs)

        return wrapper

    return decorator


def with_fallback(primary: str, fallbacks: list[str]):
    """Decorator to add fallback to a function"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = FallbackHandler(primary, fallbacks)
            return handler.execute(func, *args, **kwargs)

        return wrapper

    return decorator


# Usage examples
def example_usage():
    """Show how to use retry and fallback"""

    # Simple retry
    @with_retry(RetryConfig(max_attempts=3, initial_delay=1.0))
    def call_api():
        # Your API call here
        pass

    # With exponential backoff
    @with_retry(
        RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
        )
    )
    def call_api_slow():
        pass

    # With fallback models
    @with_fallback("gpt-4", ["gpt-3.5-turbo", "claude-2"])
    def call_llm(prompt: str, model: str = None):
        pass


# CLI
def main():
    """Retry/Fallback CLI"""
    import typer

    app = typer.Typer(help="Retry and Fallback Configuration")

    @app.command("test")
    def test_retry():
        """Test retry logic"""
        config = RetryConfig(max_attempts=3, initial_delay=0.5)
        handler = RetryHandler(config)

        attempt_count = 0

        def failing_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Simulated failure")
            return "Success"

        result = handler.execute(failing_func)
        typer.echo(f"Result: {result}")
        typer.echo(f"Attempts: {attempt_count}")

    @app.command("config")
    def show_config():
        """Show current config"""
        config = RetryConfig()
        typer.echo(f"Max attempts: {config.max_attempts}")
        typer.echo(f"Initial delay: {config.initial_delay}s")
        typer.echo(f"Strategy: {config.strategy.value}")

    app()


if __name__ == "__main__":
    main()
