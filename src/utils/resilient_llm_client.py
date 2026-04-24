"""
Resilient LLM Client — Production-grade LLM calls with circuit breaker, retry, and fallback.
Applies resilience patterns to all critical LLM operations.
"""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from src.utils.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    FallbackChain,
    RetryConfig,
    RetryHandler,
    RetryStrategy,
)

logger = logging.getLogger(__name__)

# API Configuration
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_API_URL = os.getenv("OLLAMA_API_BASE", "http://localhost:11434") + "/api/generate"

# Default models for fallback chain
DEFAULT_MODELS = [
    "openrouter/free",  # Primary - free tier
    "google/gemini-2.0-flash-exp:free",  # Fallback 1
    "meta-llama/llama-3.3-70b-instruct:free",  # Fallback 2
    "qwen/qwen3-coder:free",  # Fallback 3
]


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    model: str
    usage: dict[str, int] | None = None
    latency_ms: float | None = None
    success: bool = True
    error: str | None = None


class ResilientLLMClient:
    """
    Resilient LLM client with circuit breaker, retry, and fallback.

    Automatically handles:
    - Circuit breaking after repeated failures
    - Exponential backoff retry with jitter
    - Automatic fallback to backup models
    - Error recovery and logging

    Usage:
        client = ResilientLLMClient()
        response = client.chat(
            messages=[{"role": "user", "content": "Hello"}],
            model="google/gemini-2.0-flash-001"
        )
    """

    def __init__(
        self,
        api_key: str | None = None,
        circuit_name: str = "openrouter",
        max_retries: int = 3,
        fallback_models: list[str] | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.circuit_name = circuit_name
        self.max_retries = max_retries
        self.fallback_models = fallback_models or DEFAULT_MODELS[1:]

        # Initialize circuit breaker
        self.circuit = CircuitBreaker.get(
            circuit_name,
            CircuitBreakerConfig(
                failure_threshold=5,
                window_seconds=60.0,
                retry_seconds=30.0,
            ),
        )

        # Initialize retry handler
        self.retry = RetryHandler(
            RetryConfig(
                max_attempts=max_retries,
                initial_delay=1.0,
                backoff_multiplier=2.0,
                strategy=RetryStrategy.EXPONENTIAL,
                jitter=True,
                retryable_exceptions=(
                    ConnectionError,
                    TimeoutError,
                    Exception,  # LLM APIs raise various exceptions
                ),
            )
        )

        logger.info(f"Initialized ResilientLLMClient with circuit '{circuit_name}'")

    def _call_openrouter(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Make OpenRouter API call."""
        import time

        import requests

        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kitty.local",
            "X-Title": "Kitty AI",
        }

        payload = {"model": model, "messages": messages, "temperature": temperature, **kwargs}

        if max_tokens:
            payload["max_tokens"] = max_tokens

        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=model,
            usage=data.get("usage"),
            latency_ms=latency_ms,
        )

    def _call_ollama(
        self,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Make Ollama API call."""
        import time

        import requests

        start_time = time.time()

        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature},
        }

        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()
        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=data["response"],
            model=model,
            latency_ms=latency_ms,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_fallbacks: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """
        Send chat completion request with full resilience.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to first in fallback chain)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            use_fallbacks: Whether to try fallback models on failure
            **kwargs: Additional parameters for API

        Returns:
            LLMResponse with content, model used, and metadata
        """
        model = model or self.fallback_models[0]

        # Check circuit breaker first
        if not self.circuit.can_execute():
            logger.warning(f"Circuit '{self.circuit_name}' is OPEN, fast failing")
            return LLMResponse(
                content="",
                model=model,
                success=False,
                error="Circuit breaker open - service temporarily unavailable",
            )

        # Build fallback chain
        if use_fallbacks:
            chain = FallbackChain[LLMResponse]("llm_chat")

            # Primary model
            chain.register_primary(
                model,
                lambda: self._call_openrouter(model, messages, temperature, max_tokens, **kwargs),
            )

            # Fallback models
            for i, fallback_model in enumerate(self.fallback_models):
                if fallback_model != model:
                    chain.register_fallback(
                        fallback_model,
                        lambda m=fallback_model: self._call_openrouter(
                            m, messages, temperature, max_tokens, **kwargs
                        ),
                        priority=i + 1,
                    )

        # Execute with retry and circuit breaker
        try:
            if use_fallbacks:
                result = self.retry.execute(lambda: self._execute_with_circuit(chain.execute))
            else:
                result = self.retry.execute(
                    lambda: self._execute_with_circuit(
                        lambda: self._call_openrouter(
                            model, messages, temperature, max_tokens, **kwargs
                        )
                    )
                )

            return result

        except Exception as e:
            logger.error(f"All LLM attempts failed: {e}")
            return LLMResponse(
                content="",
                model=model,
                success=False,
                error=str(e),
            )

    def _execute_with_circuit(self, func: Callable[[], LLMResponse]) -> LLMResponse:
        """Execute function with circuit breaker tracking."""
        try:
            result = func()
            self.circuit.record_success()
            return result
        except Exception as e:
            self.circuit.record_failure()
            raise e

    def get_circuit_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return self.circuit.get_state()

    @staticmethod
    def quick_chat(
        prompt: str,
        model: str = "google/gemini-2.0-flash-001",
        system: str | None = None,
    ) -> str:
        """
        Quick one-off chat with resilience.

        Usage:
            response = ResilientLLMClient.quick_chat("Hello")
        """
        client = ResilientLLMClient()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat(messages, model=model)
        return response.content if response.success else f"Error: {response.error}"


# Decorator for resilient LLM calls


def resilient_llm_call(
    circuit_name: str = "llm",
    max_retries: int = 3,
    fallback_models: list[str] | None = None,
):
    """
    Decorator to make any LLM function resilient.

    Usage:
        @resilient_llm_call(circuit_name="openrouter")
        def call_custom_llm(prompt: str) -> str:
            return requests.post(...).json()["text"]
    """

    def decorator(func: Callable) -> Callable:
        client = ResilientLLMClient(
            circuit_name=circuit_name,
            max_retries=max_retries,
            fallback_models=fallback_models,
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a fallback chain that calls the original function
            chain = FallbackChain("decorated_llm")
            chain.register_primary("primary", lambda: func(*args, **kwargs))

            # Add model fallbacks if specified
            if fallback_models:
                for i, model in enumerate(fallback_models):
                    # Modify kwargs to use fallback model
                    def fallback_call(m=model):
                        kwargs_with_model = {**kwargs, "model": m}
                        return func(*args, **kwargs_with_model)

                    chain.register_fallback(model, fallback_call, priority=i + 1)

            return client.retry.execute(lambda: client._execute_with_circuit(chain.execute))

        return wrapper

    return decorator


# Legacy compatibility


def call_llm_with_resilience(
    prompt: str,
    system: str | None = None,
    model: str = "google/gemini-2.0-flash-001",
    max_retries: int = 3,
) -> str:
    """
    Legacy compatibility function for LLM calls with resilience.

    Returns content string or error message.
    """
    client = ResilientLLMClient(max_retries=max_retries)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat(messages, model=model)
    return response.content if response.success else f"Error: {response.error}"


# Export
__all__ = [
    "ResilientLLMClient",
    "LLMResponse",
    "resilient_llm_call",
    "call_llm_with_resilience",
]
