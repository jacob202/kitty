"""
Standalone LLM client for Space Kitty specialists.
Primary: OpenRouter (model-selectable). Fallback: native MLX local inference. Last resort: placeholder.

Native MLX: mlx_lm loads Qwen3.5-4B directly — no separate server needed.

Provider resilience: circuit breakers + outbound rate limiting prevent cascading failures.
"""

import json
import logging
import os
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MLX_MODEL = os.getenv("MLX_MODEL", "mlx-community/Qwen3.5-4B-4bit")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

DEFAULT_MODEL = None  # None = fall through to local MLX; pass explicit model for remote

# Reusable session for connection pooling
_http_session = None


def _get_session() -> requests.Session:
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        _http_session.headers.update({"Content-Type": "application/json"})
    return _http_session


# Reusable Anthropic client singleton
_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None and ANTHROPIC_API_KEY:
        import anthropic

        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


# ── Native MLX Singleton ─────────────────────────────────────────────
_mlx_model = None
_mlx_tokenizer = None
_mlx_loaded = False
_mlx_lock = threading.Lock()


def _load_mlx():
    """Lazily load MLX model once (thread-safe singleton)."""
    global _mlx_model, _mlx_tokenizer, _mlx_loaded
    if _mlx_loaded:
        return _mlx_model is not None

    with _mlx_lock:
        if _mlx_loaded:
            return _mlx_model is not None

        try:
            from mlx_lm import load as mlx_load
            logger.info(f"Loading MLX model: {MLX_MODEL}")
            _mlx_model, _mlx_tokenizer = mlx_load(MLX_MODEL)
            _mlx_loaded = True
            logger.info("MLX model loaded successfully")
            return True
        except ImportError:
            logger.debug("mlx_lm not installed — native MLX unavailable")
            _mlx_loaded = True
            return False
        except Exception as e:
            logger.warning(f"Failed to load MLX model: {e}")
            _mlx_loaded = True
            return False


def _generate_mlx(prompt: str, system_prompt: str, max_tokens: int, temperature: float) -> str | None:
    """Generate text using native MLX (no HTTP server needed)."""
    if not _load_mlx() or _mlx_model is None:
        return None

    try:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        prompt_text = _mlx_tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False
        )

        sampler = make_sampler(temp=temperature)
        return generate(
            _mlx_model,
            _mlx_tokenizer,
            prompt=prompt_text,
            max_tokens=max_tokens,
            verbose=False,
            sampler=sampler,
        )
    except Exception as e:
        logger.debug(f"Native MLX generation failed: {e}")
        return None

# Cost per 1M tokens [input, output] — update if pricing changes
_MODEL_COSTS: dict = {
    "qwen/qwen3-235b-a22b-2507": [0.07, 0.10],
    "deepseek/deepseek-r1-0528": [0.50, 2.15],
    "anthropic/claude-sonnet-4-6": [3.00, 15.00],
}
_BUDGET_DIR = Path("data/budget")


def _track_spend(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Append token usage to today's daily spend file (atomic write)."""
    try:
        _BUDGET_DIR.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        path = _BUDGET_DIR / f"{today}.json"

        costs = _MODEL_COSTS.get(model, [0.001, 0.001])
        cost = (prompt_tokens * costs[0] + completion_tokens * costs[1]) / 1_000_000

        record = {"model": model, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cost_usd": round(cost, 6)}

        existing = json.loads(path.read_text()) if path.exists() else []
        existing.append(record)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(_BUDGET_DIR), suffix=".json")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(existing, f, indent=2)
            os.replace(tmp_path, str(path))  # Atomic on POSIX
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.debug(f"Budget tracking failed: {e}")


def get_today_spend() -> dict:
    """Return today's total spend and call count."""
    try:
        today = date.today().isoformat()
        path = _BUDGET_DIR / f"{today}.json"
        if not path.exists():
            return {"total_usd": 0.0, "calls": 0}
        records = json.loads(path.read_text())
        return {
            "total_usd": round(sum(r["cost_usd"] for r in records), 4),
            "calls": len(records),
        }
    except Exception:
        return {"total_usd": 0.0, "calls": 0}


# ── Provider Resilience ──────────────────────────────────────────────
# Lazy-loaded circuit breakers and rate limiters for each provider tier.

_circuit_breakers: dict = {}
_rate_limiters: dict = {}
_resilience_lock = __import__("threading").Lock()


def _get_circuit_breaker(provider: str):
    """Get or create a circuit breaker for a provider tier."""
    with _resilience_lock:
        if provider not in _circuit_breakers:
            from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
            # OpenRouter/Anthropic: 3 failures in 5 min → 15 min cooldown
            # MLX local: 5 failures in 5 min → 5 min cooldown (local is more reliable)
            if provider == "mlx_local":
                config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=300)
            else:
                config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=900)
            _circuit_breakers[provider] = CircuitBreaker(provider, config=config)
        return _circuit_breakers[provider]


def _get_rate_limiter(provider: str):
    """Get or create a rate limiter for a provider tier."""
    with _resilience_lock:
        if provider not in _rate_limiters:
            from src.core.rate_limiter import RateLimiterRegistry
            registry = RateLimiterRegistry()
            _rate_limiters[provider] = registry.get(provider)
        return _rate_limiters[provider]


def _check_provider_resilience(provider: str) -> bool:
    """Check if a provider should be used (circuit closed + not rate limited).
    Returns True if the provider is available, False if it should be skipped."""
    cb = _get_circuit_breaker(provider)
    if cb.is_open():
        stats = cb.get_stats()
        logger.warning(
            f"Skipping {provider}: circuit breaker is {stats['state']} "
            f"(recovery in {stats['recovery_timeout_remaining']}s)"
        )
        return False

    rl = _get_rate_limiter(provider)
    if rl.should_throttle():
        usage = rl.get_usage()
        logger.warning(
            f"Throttling {provider}: {usage['requests_in_window']}/{usage['max_requests']} "
            f"in window ({usage['utilization_pct']}%)"
        )
        return False

    return True


def _record_provider_outcome(provider: str, success: bool, error: str = ""):
    """Record the outcome of a provider call for resilience tracking."""
    if success:
        _get_circuit_breaker(provider).record_success()
        _get_rate_limiter(provider).record_request()
    else:
        _get_circuit_breaker(provider).record_failure(error)


def get_provider_health() -> list[dict]:
    """Return health status of all provider tiers for UI telemetry."""
    providers = ["openrouter", "anthropic", "mlx_local"]
    health = []
    for p in providers:
        cb = _get_circuit_breaker(p)
        rl = _get_rate_limiter(p)
        health.append({
            "provider": p,
            **cb.get_stats(),
            **rl.get_usage(),
        })
    return health


# ── Main LLM Call ────────────────────────────────────────────────────

def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """
    Call an LLM. Primary: OpenRouter. Fallback: local MLX server. Last resort: placeholder.

    model: OpenRouter model ID (e.g. "qwen/qwen3-235b-a22b-2507").
           Pass "anthropic/claude-sonnet-4-6" for explicit premium requests.
           None = use DEFAULT_MODEL.

    Provider resilience: circuit breakers skip failing providers,
    rate limiters throttle preemptively before hitting provider limits.
    """
    selected = model or DEFAULT_MODEL
    errors = []

    for attempt in range(3):
        result = _call_llm_once(prompt, system_prompt, selected, max_tokens, temperature, errors)
        if result is not None:
            return result
        if attempt < 2:
            backoff = 2 ** attempt
            logger.info(f"LLM attempt {attempt + 1} failed, retrying in {backoff}s...")
            time.sleep(backoff)

    logger.warning(f"All LLM backends failed after 3 attempts: {errors}")
    return f"[offline mode — {'; '.join(errors)}]"


def _call_llm_once(prompt, system_prompt, selected, max_tokens, temperature, errors):
    # Try OpenRouter (with circuit breaker + rate limiting)
    if OPENROUTER_API_KEY:
        if _check_provider_resilience("openrouter"):
            result = _try_openrouter(prompt, system_prompt, selected, max_tokens, temperature)
            if result is not None:
                _record_provider_outcome("openrouter", True)
                return result
            _record_provider_outcome("openrouter", False, "request_failed")
        errors.append(f"OpenRouter/{selected} unavailable")

    # Try Anthropic direct (only for claude models)
    if not OPENROUTER_API_KEY and ANTHROPIC_API_KEY and "claude" in selected:
        if _check_provider_resilience("anthropic"):
            result = _try_anthropic(prompt, system_prompt, selected, max_tokens, temperature)
            if result is not None:
                _record_provider_outcome("anthropic", True)
                return result
            _record_provider_outcome("anthropic", False, "request_failed")
        errors.append("Anthropic direct unavailable")

    # Try MLX local fallback (native inference, no server needed)
    if _check_provider_resilience("mlx_local"):
        result = _try_mlx(prompt, system_prompt, max_tokens, temperature)
        if result is not None:
            _record_provider_outcome("mlx_local", True)
            logger.info("Using native MLX local inference")
            return result
        _record_provider_outcome("mlx_local", False, "mlx_unavailable")
    errors.append("MLX local inference failed (install mlx-lm: pip install mlx-lm)")
    return None


def _try_openrouter(
    prompt: str, system_prompt: str, model: str, max_tokens: int, temperature: float
) -> str | None:
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        session = _get_session()
        resp = session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://github.com/kitty",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=(10, 60),
        )
        if resp.status_code == 200:
            data = resp.json()
            usage = data.get("usage", {})
            _track_spend(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            return data["choices"][0]["message"]["content"]

        if resp.status_code == 429:
            logger.warning(f"OpenRouter rate limit (429) hit for {model}. Backing off...")
            return None

        logger.debug(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.debug(f"OpenRouter error: {e}")
        return None


def _try_anthropic(
    prompt: str, system_prompt: str, model: str, max_tokens: int, temperature: float
) -> str | None:
    client = _get_anthropic_client()
    if not client:
        return None
    try:
        native_model = model.replace("anthropic/", "")
        messages = [{"role": "user", "content": prompt}]
        kwargs = {"model": native_model, "max_tokens": max_tokens, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        resp = client.messages.create(**kwargs)
        return resp.content[0].text
    except Exception as e:
        logger.debug(f"Anthropic direct failed: {e}")
        return None


def _try_mlx(
    prompt: str, system_prompt: str, max_tokens: int, temperature: float
) -> str | None:
    """Native MLX inference on Apple Silicon — no HTTP server needed."""
    return _generate_mlx(prompt, system_prompt, max_tokens, temperature)
