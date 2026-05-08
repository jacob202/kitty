#!/usr/bin/env python3
"""
Kitty Builder – autonomous multi‑model agent for Jacob.
Runs entirely on Apple Silicon / MLX with full session memory.
"""

from __future__ import annotations

import argparse, hashlib, json, logging, os, py_compile, re, shlex, shutil, sqlite3, subprocess, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

# Ensure the repository root is in the Python path so that `src` can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Token optimization: semantic caching
try:
    from src.core.prompt_cache import SemanticCache
    _semantic_cache = SemanticCache()
except ImportError:
    _semantic_cache = None
    print("[KittyBuilder] SemanticCache not available", file=sys.stderr)

log = logging.getLogger("kitty_builder")
if not log.handlers:
    _stderr_handler = logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    log.addHandler(_stderr_handler)
    log.setLevel(logging.INFO)

# Plan-only mode blocks mutating / shell tools (set via --plan-only or KITTY_BUILDER_PLAN_ONLY=1).
PLAN_ONLY_MODE = False
PLAN_ONLY_BLOCKED_TOOLS = frozenset({
    "run_command",
    "write_file",
    "modify_project_tasks",
    "launch_kitty",
    "kitty_self_improve",
    "delegate",
})

HISTORY_MAX_MESSAGES = int(os.environ.get("KITTY_BUILDER_HISTORY_MAX", "40"))

DELEGATE_TIMEOUT_SEC = float(os.environ.get("KITTY_BUILDER_DELEGATE_TIMEOUT_SEC", "7200"))

# Brain tier order: comma-separated subset of groq, openrouter, mlx.
# Default: OpenRouter free pool (multi-model rotation) → local MLX → Groq last.
# Groq is fast when healthy but free tier / routing errors are common; don't lead with it.
# Examples: KITTY_BUILDER_BRAIN_ORDER=mlx,openrouter for local-first;
# KITTY_BUILDER_BRAIN_ORDER=groq,openrouter,mlx to restore old Groq-first behavior.
_BRAIN_TIER_ALIASES = frozenset({"groq", "openrouter", "mlx"})

_DEFAULT_BRAIN_ORDER: tuple[str, ...] = ("openrouter", "mlx", "groq")


def _parse_brain_order() -> tuple[str, ...]:
    raw = os.environ.get(
        "KITTY_BUILDER_BRAIN_ORDER", ",".join(_DEFAULT_BRAIN_ORDER)
    ).strip().lower()
    parts = [p.strip() for p in raw.replace(" ", "").split(",") if p.strip()]
    ordered = [p for p in parts if p in _BRAIN_TIER_ALIASES]
    return tuple(ordered) if ordered else _DEFAULT_BRAIN_ORDER


def _estimate_openrouter_call_usd(model_id: str) -> float:
    """Preflight reservation for paid models; free pool ids ending in :free → 0."""
    mid = (model_id or "").strip().lower()
    if mid.endswith(":free") or ":free" in mid:
        return 0.0
    return float(os.environ.get("KITTY_BUDGET_OR_ESTIMATE_USD", "0.002"))


PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

POLICY_FILE = PROJECT_ROOT / "config" / "kittybuilder_orchestrator_policy.json"

_DEFAULT_ORCHESTRATOR_POLICY: dict[str, Any] = {
    "brain_tier_order": ["openrouter", "mlx", "groq"],
    "delegate_order": ["gemini", "agent", "claude", "opencode", "aider", "crush", "goose"],
    "routing": {
        "max_retries_per_tier": {
            "openrouter": 4,
            "groq": 1,
            "mlx": 1,
        },
        "context_budgets": {
            "history_max_messages": 40,
            "file_read_max_tokens": 2000,
        },
    },
}


def _merge_policy(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_policy(out[key], value)
        else:
            out[key] = value
    return out


def _load_orchestrator_policy() -> dict[str, Any]:
    if not POLICY_FILE.is_file():
        return dict(_DEFAULT_ORCHESTRATOR_POLICY)
    try:
        raw = json.loads(POLICY_FILE.read_text())
        if not isinstance(raw, dict):
            raise ValueError("policy root must be an object")
        return _merge_policy(_DEFAULT_ORCHESTRATOR_POLICY, raw)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"[KittyBuilder] policy load failed ({POLICY_FILE}): {e}", file=sys.stderr)
        return dict(_DEFAULT_ORCHESTRATOR_POLICY)


ORCHESTRATOR_POLICY = _load_orchestrator_policy()

_policy_brain_order = tuple(
    t for t in ORCHESTRATOR_POLICY.get("brain_tier_order", []) if t in _BRAIN_TIER_ALIASES
)
if _policy_brain_order:
    _DEFAULT_BRAIN_ORDER = _policy_brain_order

if "KITTY_BUILDER_HISTORY_MAX" not in os.environ:
    try:
        HISTORY_MAX_MESSAGES = int(
            ORCHESTRATOR_POLICY.get("routing", {})
            .get("context_budgets", {})
            .get("history_max_messages", HISTORY_MAX_MESSAGES)
        )
    except (TypeError, ValueError):
        pass


def _resolve_tool_bin(env_var: str, *default_paths: str) -> Optional[str]:
    """Resolve a CLI binary: env override, then default absolute paths, then PATH."""
    override = os.environ.get(env_var, "").strip()
    if override:
        p = Path(override).expanduser()
        if p.is_file():
            return str(p)
        which = shutil.which(override)
        if which:
            return which
    for d in default_paths:
        p = Path(d).expanduser()
        if p.is_file():
            return str(p)
        which = shutil.which(Path(d).name)
        if which:
            return which
    return None


def _apply_history_cap(messages: List[Dict[str, str]], max_msgs: int = HISTORY_MAX_MESSAGES) -> None:
    """Shrink history in-place, always preserving the first system message when present."""
    if len(messages) <= max_msgs:
        return
    system = messages[0] if messages and messages[0].get("role") == "system" else None
    if system:
        tail_budget = max_msgs - 2  # system + omission note + recent tail
        if tail_budget < 4:
            tail_budget = max(4, max_msgs - 1)
        omitted = max(0, len(messages) - 1 - tail_budget)
        tail = messages[-tail_budget:] if tail_budget > 0 else []
        if omitted > 0:
            note = {
                "role": "system",
                "content": f"[{omitted} older turn(s) omitted to stay within the {max_msgs}-message budget.]",
            }
            messages[:] = [system, note] + tail
        else:
            messages[:] = [system] + messages[-(max_msgs - 1) :]
    else:
        messages[:] = messages[-max_msgs:]

generate = load = stream_generate = make_sampler = None
def _try_import_mlx() -> None:
    """Best-effort MLX import. Keeps startup safe in headless/sandboxed sessions."""
    global generate, load, stream_generate, make_sampler
    if load is not None:
        return
    try:
        from mlx_lm import generate as _g, load as _l, stream_generate as _sg
        from mlx_lm.sample_utils import make_sampler as _ms
        generate, load, stream_generate, make_sampler = _g, _l, _sg, _ms
    except Exception:
        generate = load = stream_generate = make_sampler = None


if os.environ.get("KITTY_ENABLE_LOCAL_MLX", "").strip().lower() in ("1", "true", "yes"):
    _try_import_mlx()

from src.utils.security_scanner import scan_text

_env_loaded = False
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
    _env_loaded = True

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
USE_OPENROUTER = os.environ.get("USE_OPENROUTER", "true").lower() == "true"

# Curated list of OpenRouter free-tier coding models (override via OPENROUTER_FREE_MODELS).
DEFAULT_FREE_MODELS = [
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1-distill-llama-70b:free",
    "google/gemini-2.0-flash-exp:free",
]

def _parse_free_models() -> list[str]:
    raw = os.environ.get("OPENROUTER_FREE_MODELS", "").strip()
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return list(DEFAULT_FREE_MODELS)

OPENROUTER_FREE_MODELS = _parse_free_models()

# Optional explicit override. If set, exact model is used and free-pool rotation is skipped.
# Empty default = free pool rotation.
OPENROUTER_MODEL_OVERRIDE = os.environ.get("OPENROUTER_MODEL", "").strip()

# Optional paid fallback used only after the entire free pool is on cooldown.
OPENROUTER_PAID_FALLBACK = os.environ.get("OPENROUTER_PAID_FALLBACK", "").strip()

# Back-compat module attribute (referenced by `/models` UI). Empty string means "free pool".
OPENROUTER_MODEL = OPENROUTER_MODEL_OVERRIDE

_openrouter_client = None
if USE_OPENROUTER and OPENROUTER_API_KEY:
    try:
        from openai import OpenAI
        _openrouter_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            timeout=60.0,
        )
    except ModuleNotFoundError:
        _openrouter_client = None

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# Set KITTY_BUILDER_DISABLE_GROQ=1 to skip Groq entirely (brain + probe) while keeping the key in .env.
_GROQ_DISABLED = os.environ.get("KITTY_BUILDER_DISABLE_GROQ", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
_groq_client = None
if GROQ_API_KEY and not _GROQ_DISABLED:
    try:
        from openai import OpenAI as _GroqOpenAI
        _groq_client = _GroqOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)
    except ModuleNotFoundError:
        _groq_client = None

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
PROJECT_FILE = PROJECT_ROOT / "project.json"

# Preferred Model (project standard — MLX optimized for quality)
# Qwen3.5-4bit tested as best performer for reasoning/instruction following
MODEL_BUILDER = "mlx-community/Qwen3.5-4B-4bit"
MODEL_CODE    = MODEL_BUILDER
MODEL_CONV    = MODEL_BUILDER

WEB_SEARCH_API_KEY = os.environ.get("TAVILY_API_KEY", "")   # Tavily API key
WHITELISTED_COMMANDS = {
    "git", "python3", "python3.12", "python3.11", "python3.10", "python", "pip", "pip3",
    "ls", "echo", "mkdir", "touch", "cat", "head", "tail", "wc", "grep", "find", "pwd",
    "pytest", "unittest", "mypy", "ruff", "black", "npm", "npx", "bash", "sh",
}

# ------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------
class Session:
    def __init__(self):
        self.history: List[Dict[str, str]] = []
        self.project_state: Dict = {}

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        # Keep history manageable (last 20 turns)
        if len(self.history) > 40:
            self.history = self.history[-40:]

SESSION_FILE = PROJECT_ROOT / ".kittybuilder_session.json"
KITTYBUILDER_SESSION_LOG = PROJECT_ROOT / "docs" / "handoffs" / "kittybuilder-session-log.md"
APPEND_STANDUP = os.environ.get("KITTY_BUILDER_APPEND_STANDUP", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

def save_session():
    """Atomic session save. Failure is logged but not raised. Also flushes model stats."""
    tmp = SESSION_FILE.with_suffix(SESSION_FILE.suffix + ".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump({
                "history": session.history,
                "project_state": session.project_state,
            }, f)
        os.replace(tmp, SESSION_FILE)
    except (OSError, TypeError) as e:
        print(f"[Session] save failed: {e}", file=sys.stderr)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    # Best-effort: persist a JSONL row of model health for future MCP ingest.
    try:
        flush_model_stats()
    except Exception as e:
        print(f"[ModelStats] flush from save_session failed: {e}", file=sys.stderr)

def load_session():
    if not SESSION_FILE.exists():
        return False
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
        session.history = data.get("history", [])
        session.project_state = data.get("project_state", {})
        return True
    except (json.JSONDecodeError, OSError) as e:
        print(f"[Session] load failed: {e}", file=sys.stderr)
        return False

session = Session()

# ------------------------------------------------------------
# MODEL CACHE
# ------------------------------------------------------------
_model_cache = {}

def get_model(model_id: str, retries: int = 2, *, force_local: bool = False):
    """Load MLX model weights. When ``force_local`` is False and OpenRouter is
    configured, returns ``("openrouter", model_id)`` for routing layers that
    expect that sentinel. Tier-3 Brain and other MLX-only paths must pass
    ``force_local=True`` so weights actually load.
    """
    if not force_local and USE_OPENROUTER and _openrouter_client:
        return ("openrouter", model_id)
    if load is None:
        _try_import_mlx()
    if load is None:
        raise RuntimeError("MLX is not installed. Use OpenRouter or install mlx_lm for local model mode.")
    if model_id in _model_cache:
        return _model_cache[model_id]
    if _model_cache:
        _model_cache.clear()
    log.info("Loading MLX model: %s", model_id)
    for attempt in range(retries):
        try:
            # MLX load options for optimization
            model, tokenizer = load(
                model_id,
                tokenizer_config={"trust_remote_code": True}
            )
            _model_cache[model_id] = (model, tokenizer)
            return model, tokenizer
        except Exception as e:
            if attempt == retries - 1:
                raise
            log.warning("MLX load retry %s after: %s", attempt + 2, e)
    raise RuntimeError(f"Failed to load {model_id} after {retries} attempts")

# MLX Optimization constants
MLX_OPTIMIZATIONS = {
    "use_lazy_imports": True,  # Reduces memory during loading
    "fp16": False,  # Use fp16 for faster inference on M1/M2
    "stream_chunk_size": 512,  # Optimal chunk size for streaming
}

class BuilderError(Exception):
    """Structured error raised by the inference layer.

    Attributes:
        code: short machine-readable label (e.g. RATE_LIMITED, FREE_POOL_EXHAUSTED, NO_CLIENT)
        retry_after: seconds the caller may wait before retrying, if known
        model: the model id that failed, if any
    """

    def __init__(self, code: str, message: str, *, retry_after: Optional[float] = None,
                 model: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after
        self.model = model


class BudgetExhausted(BuilderError):
    """Raised by BudgetManager when a preflight check would exceed the daily cap."""


_FREE_MODELS_DISCOVERY_TTL = 3600  # 1h


class FreeModelPool:
    """Round-robin pool of OpenRouter free models with per-model cooldown.

    On 429/503 we 'park' the failing model for `retry_after` seconds; other
    models keep serving requests. discover() merges newly-found free models
    from the OpenRouter /models endpoint at most once per TTL.
    """

    def __init__(self, models: list[str]) -> None:
        self._models = list(models)
        self._index = 0
        self._cooldowns: Dict[str, float] = {}
        self._stats: Dict[str, Dict[str, int]] = {}
        self._last_discovery: float = 0.0
        self._lock = threading.Lock()

    def all_models(self) -> list[str]:
        with self._lock:
            return list(self._models)

    def next_available(self) -> Optional[str]:
        with self._lock:
            if not self._models:
                return None
            now = time.time()
            n = len(self._models)
            for _ in range(n):
                model = self._models[self._index % n]
                self._index = (self._index + 1) % n
                if self._cooldowns.get(model, 0.0) <= now:
                    return model
            return None

    def cooldown_remaining(self) -> float:
        with self._lock:
            now = time.time()
            future = [t - now for t in self._cooldowns.values() if t > now]
            return min(future) if future else 0.0

    def park(self, model: str, retry_after: float) -> None:
        with self._lock:
            self._cooldowns[model] = time.time() + max(retry_after, 1.0)

    def record_success(self, model: str) -> None:
        with self._lock:
            s = self._stats.setdefault(model, {"ok": 0, "fail": 0})
            s["ok"] += 1

    def record_failure(self, model: str) -> None:
        with self._lock:
            s = self._stats.setdefault(model, {"ok": 0, "fail": 0})
            s["fail"] += 1

    def stats(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return {m: dict(v) for m, v in self._stats.items()}

    def discover(self, force: bool = False) -> None:
        now = time.time()
        with self._lock:
            if not force and now - self._last_discovery < _FREE_MODELS_DISCOVERY_TTL:
                return
        try:
            import requests as _req
            resp = _req.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"} if OPENROUTER_API_KEY else {},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", []) or []
            discovered: list[str] = []
            for m in data:
                mid = (m.get("id") or "").strip()
                if not mid:
                    continue
                pricing = m.get("pricing") or {}
                p_prompt = str(pricing.get("prompt", "")).strip()
                p_compl = str(pricing.get("completion", "")).strip()
                is_free_id = mid.endswith(":free")
                is_zero_price = p_prompt in ("0", "0.0") and p_compl in ("0", "0.0")
                if is_free_id or is_zero_price:
                    discovered.append(mid)
            with self._lock:
                seen = set(self._models)
                for mid in discovered:
                    if mid not in seen:
                        self._models.append(mid)
                        seen.add(mid)
                self._last_discovery = now
        except Exception as e:
            print(f"[FreeModelPool] discover failed: {e}", file=sys.stderr)


free_pool = FreeModelPool(OPENROUTER_FREE_MODELS)


# OpenRouter provider routing — let upstream try multiple providers per request.
_OR_PROVIDER_ROUTING = {"allow_fallbacks": True}


def _retry_after_seconds(exc: BaseException) -> Optional[float]:
    """Extract Retry-After header (seconds) from an OpenAI/HTTP exception, if any."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) if resp is not None else None
    if not headers:
        return None
    try:
        val = headers.get("retry-after") or headers.get("Retry-After")
    except Exception:
        return None
    if not val:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _classify_openrouter_error(exc: BaseException) -> tuple[str, Optional[int]]:
    """Return (kind, status_code). kind is one of: rate, unavailable, request, network."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    if status == 429 or "RateLimit" in name:
        return "rate", status
    if status in (502, 503, 504):
        return "unavailable", status
    if status is not None and 400 <= status < 500:
        return "request", status
    return "network", status


def _select_or_model(explicit: Optional[str]) -> tuple[str, bool]:
    """Pick a model: (model_id, is_from_pool). Raises BuilderError if pool exhausted."""
    if explicit:
        return explicit, False
    if OPENROUTER_MODEL_OVERRIDE:
        return OPENROUTER_MODEL_OVERRIDE, False
    free_pool.discover()
    picked = free_pool.next_available()
    if picked:
        return picked, True
    if OPENROUTER_PAID_FALLBACK:
        return OPENROUTER_PAID_FALLBACK, False
    wait = free_pool.cooldown_remaining()
    raise BuilderError(
        "FREE_POOL_EXHAUSTED",
        f"All OpenRouter free models on cooldown (next available in {wait:.1f}s)"
        " and no OPENROUTER_PAID_FALLBACK configured",
        retry_after=wait or None,
    )


def call_openrouter(
    messages: list,
    *,
    model: Optional[str] = None,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    max_attempts: int = 4,
    use_cache: bool = True,
):
    """Non-streaming OpenRouter call with rotation + Retry-After + provider routing.

    Returns the assistant message text. Raises BuilderError on terminal failure.

    Args:
        use_cache: If True, check semantic cache before calling LLM.
    """
    if not _openrouter_client:
        raise BuilderError("NO_CLIENT", "OpenRouter client not initialized; set OPENROUTER_API_KEY")

    # Extract system prompt and user prompt for cache key
    system_prompt = ""
    user_prompt = ""
    for msg in messages:
        if msg.get("role") == "system":
            system_prompt = msg.get("content", "")
        elif msg.get("role") == "user":
            user_prompt = msg.get("content", "")

    # Check semantic cache
    if use_cache and _semantic_cache:
        cached = _semantic_cache.get("openrouter", model or "default", system_prompt, user_prompt)
        if cached is not None:
            return cached

    last_err: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        picked, from_pool = _select_or_model(model)
        budget.assert_can_spend(provider="or", est_usd=_estimate_openrouter_call_usd(picked))
        try:
            resp = _openrouter_client.chat.completions.create(
                model=picked,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                extra_body={"provider": _OR_PROVIDER_ROUTING},
            )
            content = resp.choices[0].message.content or ""
            free_pool.record_success(picked)
            budget.record_or(0.0 if picked.endswith(":free") else 0.001, model=picked)
            log_token_usage(
                provider="openrouter",
                model=picked,
                operation="chat.completions.create",
                usage=_extract_usage_dict(getattr(resp, "usage", None)),
                metadata={"stream": False, "from_pool": from_pool, "completion_chars": len(content)},
            )
            # Store in semantic cache
            if use_cache and _semantic_cache:
                _semantic_cache.put("openrouter", picked, system_prompt, user_prompt, content)
            return content
        except BuilderError:
            raise
        except Exception as e:
            last_err = e
            kind, status = _classify_openrouter_error(e)
            retry_after = _retry_after_seconds(e) or 0.0
            free_pool.record_failure(picked)
            if kind == "rate" or kind == "unavailable":
                cooldown = retry_after if retry_after > 0 else min(60.0, 5.0 * (2 ** (attempt - 1)))
                if from_pool:
                    free_pool.park(picked, cooldown)
                    print(
                        f"[OpenRouter] {picked} {status or kind} → park {cooldown:.1f}s, rotate",
                        file=sys.stderr,
                    )
                    continue
                # explicit model: backoff in place
                print(f"[OpenRouter] {picked} {status or kind} → wait {cooldown:.1f}s",
                      file=sys.stderr)
                time.sleep(min(cooldown, 30.0))
                continue
            if kind == "request":
                raise BuilderError("REQUEST_ERROR", f"OpenRouter {status}: {e}",
                                   model=picked) from e
            # network / unknown
            print(f"[OpenRouter] {picked} network error: {e} (attempt {attempt})",
                  file=sys.stderr)
            time.sleep(min(2.0 * attempt, 8.0))

    raise BuilderError(
        "MAX_RETRIES",
        f"OpenRouter exhausted after {max_attempts} attempts. Last: {last_err}",
    ) from last_err


def stream_openrouter(
    messages: list,
    *,
    model: Optional[str] = None,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    max_attempts: int = 4,
    use_cache: bool = True,
):
    """Streaming OpenRouter call. Yields (model_id, delta_text) tuples.

    Retries to OPEN the stream are handled here; mid-stream errors propagate
    to the caller. Raises BuilderError if no attempt opens a stream.

    Args:
        use_cache: If True, check semantic cache before calling LLM.
    """
    if not _openrouter_client:
        raise BuilderError("NO_CLIENT", "OpenRouter client not initialized; set OPENROUTER_API_KEY")

    # Extract system prompt and user prompt for cache key
    system_prompt = ""
    user_prompt = ""
    for msg in messages:
        if msg.get("role") == "system":
            system_prompt = msg.get("content", "")
        elif msg.get("role") == "user":
            user_prompt = msg.get("content", "")

    # Check semantic cache (return as single chunk to simulate streaming)
    if use_cache and _semantic_cache:
        cached = _semantic_cache.get("openrouter", model or "default", system_prompt, user_prompt)
        if cached is not None:
            yield (model or "cached", cached)
            return

    last_err: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        picked, from_pool = _select_or_model(model)
        budget.assert_can_spend(provider="or", est_usd=_estimate_openrouter_call_usd(picked))
        try:
            stream = _openrouter_client.chat.completions.create(
                model=picked,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                extra_body={"provider": _OR_PROVIDER_ROUTING},
            )
        except Exception as e:
            last_err = e
            kind, status = _classify_openrouter_error(e)
            retry_after = _retry_after_seconds(e) or 0.0
            free_pool.record_failure(picked)
            if kind in ("rate", "unavailable"):
                cooldown = retry_after if retry_after > 0 else min(60.0, 5.0 * (2 ** (attempt - 1)))
                if from_pool:
                    free_pool.park(picked, cooldown)
                    print(
                        f"[OpenRouter] {picked} {status or kind} → park {cooldown:.1f}s, rotate",
                        file=sys.stderr,
                    )
                    continue
                time.sleep(min(cooldown, 30.0))
                continue
            if kind == "request":
                raise BuilderError("REQUEST_ERROR", f"OpenRouter {status}: {e}",
                                   model=picked) from e
            print(f"[OpenRouter] {picked} network error: {e} (attempt {attempt})",
                  file=sys.stderr)
            time.sleep(min(2.0 * attempt, 8.0))
            continue

        # Stream opened; iterate
        completion_chars = 0
        usage_snapshot: dict[str, int] = {}
        full_response = []
        try:
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    completion_chars += len(delta)
                    full_response.append(delta)
                    yield (picked, delta)
                maybe_usage = _extract_usage_dict(getattr(chunk, "usage", None))
                if maybe_usage:
                    usage_snapshot = maybe_usage
            free_pool.record_success(picked)
            budget.record_or(0.0 if picked.endswith(":free") else 0.001, model=picked)
            log_token_usage(
                provider="openrouter",
                model=picked,
                operation="chat.completions.create",
                usage=usage_snapshot,
                metadata={
                    "stream": True,
                    "from_pool": from_pool,
                    "completion_chars": completion_chars,
                },
            )
            # Store in semantic cache
            if use_cache and _semantic_cache and full_response:
                _semantic_cache.put("openrouter", picked, system_prompt, user_prompt, "".join(full_response))
            return
        except Exception as e:
            # mid-stream failure — record + give up; partial content already sent
            free_pool.record_failure(picked)
            raise BuilderError("STREAM_INTERRUPTED",
                               f"OpenRouter stream interrupted on {picked}: {e}",
                               model=picked) from e

    raise BuilderError(
        "MAX_RETRIES",
        f"OpenRouter exhausted after {max_attempts} attempts. Last: {last_err}",
    ) from last_err


def call_openrouter_race(
    messages: list,
    *,
    n: int = 2,
    max_tokens: int = 1500,
    temperature: float = 0.7,
):
    """Race up to `n` distinct free models in parallel; return first valid response.

    Falls back to call_openrouter() if fewer than 2 models are available.
    """
    pool_models = [m for m in free_pool.all_models()
                   if free_pool._cooldowns.get(m, 0.0) <= time.time()]
    pool_models = pool_models[:max(1, n)]
    if len(pool_models) < 2:
        return call_openrouter(messages, max_tokens=max_tokens, temperature=temperature)

    def _one(model_id: str) -> str:
        return call_openrouter(messages, model=model_id,
                                max_tokens=max_tokens, temperature=temperature,
                                max_attempts=1)

    with ThreadPoolExecutor(max_workers=len(pool_models)) as pool:
        futures = {pool.submit(_one, m): m for m in pool_models}
        done, not_done = wait(futures, timeout=90, return_when=FIRST_COMPLETED)
        result_text: Optional[str] = None
        last_err: Optional[BaseException] = None
        # Drain done first
        for fut in done:
            try:
                result_text = fut.result()
                break
            except Exception as e:
                last_err = e
        # If the first-done failed, await the rest until one succeeds
        if result_text is None:
            for fut in not_done:
                try:
                    result_text = fut.result(timeout=120)
                    break
                except Exception as e:
                    last_err = e
        # Cancel any still-pending futures
        for fut in futures:
            if not fut.done():
                fut.cancel()
        if result_text is None:
            raise BuilderError("RACE_ALL_FAILED",
                               f"All raced models failed. Last: {last_err}") from last_err
        return result_text


# ── Back-compat shims ─────────────────────────────────────────────────────────
def generate_openrouter(prompt: str, max_tokens: int = 1500, temp: float = 0.7,
                        retries: int = 4) -> str:
    """Back-compat wrapper. Returns assistant text or an error string (legacy contract)."""
    if not _openrouter_client:
        return "OpenRouter client not initialized. Set OPENROUTER_API_KEY."
    try:
        return call_openrouter(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temp,
            max_attempts=retries,
        )
    except BuilderError as e:
        return f"[BuilderError {e.code}] {e}"


def stream_generate_openrouter(prompt: str, max_tokens: int = 1500, temp: float = 0.7):
    """Back-compat: yield objects with `.text` attribute (matches MLX stream_generate)."""
    if not _openrouter_client:
        return
    try:
        for _model_id, delta in stream_openrouter(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temp,
        ):
            yield type("obj", (object,), {"text": delta})()
    except BuilderError as e:
        yield type("obj", (object,), {"text": f"[BuilderError {e.code}] {e}"})()

# ------------------------------------------------------------
# SAFETY HELPERS
# ------------------------------------------------------------
def is_safe_path(path: str) -> bool:
    try:
        abs_path = (PROJECT_ROOT / path).resolve()
        return abs_path.resolve().is_relative_to(PROJECT_ROOT)
    except (ValueError, RuntimeError):
        return False

_INTERPRETERS = {"python3", "python3.12", "python3.11", "python3.10", "python", "bash", "sh"}

def sanitize_command(command: str) -> bool:
    """Return True if the command is safe to run.

    Accepts both exact names (pytest) and path-based executables
    (venv/bin/python3.12) by comparing the basename against the whitelist.
    Blocks -c flag on interpreters to prevent inline code injection.
    
    Set KITTY_BUILDER_UNSAFE=1 to relax (for autonomous mode only).
    """
    forbidden = [";", "&&", "||", "|", ">", "<", "`", "$("]
    parts = command.split()
    if not parts:
        return False
    base_name = Path(parts[0]).name   # "venv/bin/python3.12" → "python3.12"
    if base_name not in WHITELISTED_COMMANDS:
        return False
    # Block interpreter code injection via -c flag
    if base_name in _INTERPRETERS and "-c" in parts[1:]:
        return False
    for char in forbidden:
        if char in command:
            return False
    return True

# ------------------------------------------------------------
# PROJECT MANAGER - Full Context Loading
# ------------------------------------------------------------
CONTEXT_FILES = [
    "docs/LAYER0_CONTROL_PLANE.md",
    "CURRENT_FOCUS.md",
    "TASKS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/DECISIONS.md",
    "docs/AGENT_COORDINATION.md",
    "docs/KITTY_CONTEXT.md",
    "docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md",
    "README.md",
    "project.json",
]

def load_full_context() -> dict:
    """Load all relevant project context for the project manager."""
    context = {
        "files_read": [],
        "content": {},
        "git_info": {},
    }

    # Read key context files
    for rel_path in CONTEXT_FILES:
        full_path = PROJECT_ROOT / rel_path
        if full_path.exists():
            try:
                with open(full_path) as f:
                    context["content"][rel_path] = f.read(5000)
                    context["files_read"].append(rel_path)
            except (OSError, UnicodeDecodeError) as e:
                print(f"[Context] read {rel_path} failed: {e}", file=sys.stderr)

    # Get git info
    try:
        proc = subprocess.run(
            ["git", "log", "--oneline", "-10", "--format=%h %s"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        context["git_info"]["recent_commits"] = proc.stdout.strip().split("\n") if proc.returncode == 0 else []
    except (subprocess.SubprocessError, OSError) as e:
        print(f"[Context] git log failed: {e}", file=sys.stderr)

    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        context["git_info"]["status"] = proc.stdout.strip() if proc.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError) as e:
        print(f"[Context] git status failed: {e}", file=sys.stderr)

    return context

def parse_tasks_md() -> dict:
    """Parse TASKS.md checkbox counts (source of truth for task completion)."""
    tasks_file = PROJECT_ROOT / "TASKS.md"
    if not tasks_file.exists():
        return {"completed": 0, "pending": 0, "total": 0, "completion_pct": 0.0}

    completed = 0
    pending = 0
    pattern = re.compile(r'^\s*-\s*\[(x| )\]', re.I)

    with open(tasks_file) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                if m.group(1).lower() == 'x':
                    completed += 1
                else:
                    pending += 1

    total = completed + pending
    return {
        "completed": completed,
        "pending": pending,
        "total": total,
        "completion_pct": round((completed / total * 100), 1) if total > 0 else 0.0
    }


def build_project_state() -> dict:
    """Build comprehensive current project state with progress estimates."""
    full_context = load_full_context()
    name = "Kitty AI Router"

    # Read project.json
    proj = {"milestones": [], "backlog": [], "notes": ""}
    if PROJECT_FILE.exists():
        try:
            with open(PROJECT_FILE) as f:
                proj = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Project] {PROJECT_FILE.name} read failed: {e}", file=sys.stderr)

    # Scan for TODOs
    todos = []
    pattern = re.compile(r'#\s*(TODO|FIXME|HACK|NOTE|IDEA)[: ]?\s*(.*)', re.I)
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'node_modules')]
        for fname in files:
            if fname.endswith('.py'):
                try:
                    with open(os.path.join(root, fname)) as f:
                        for lno, line in enumerate(f, 1):
                            m = pattern.search(line)
                            if m:
                                todos.append({
                                    "file": os.path.relpath(os.path.join(root, fname), PROJECT_ROOT),
                                    "line": lno,
                                    "tag": m.group(1).upper(),
                                    "text": m.group(2).strip()
                                })
                except (OSError, UnicodeDecodeError):
                    continue

    # Calculate progress (total = pending + done)
    pending_tasks = sum(len(m.get("tasks", [])) for m in proj.get("milestones", []))
    done_tasks = sum(len(m.get("done_tasks", [])) for m in proj.get("milestones", []))
    total_tasks = pending_tasks + done_tasks
    total_milestones = len(proj.get("milestones", []))
    completed_milestones = sum(1 for m in proj.get("milestones", []) if m.get("status") == "completed")

    progress = {
        "total_tasks": total_tasks,
        "completed_tasks": done_tasks,
        "remaining_tasks": pending_tasks,
        "task_completion_pct": round((done_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0,
        "total_milestones": total_milestones,
        "completed_milestones": completed_milestones,
        "milestone_completion_pct": round((completed_milestones / total_milestones * 100), 1) if total_milestones > 0 else 0,
        "open_todos": len(todos),
    }

    # Drift check: compare project.json progress with TASKS.md (source of truth)
    tasks_md = parse_tasks_md()
    if tasks_md["total"] > 0:
        progress_diff = abs(progress["completed_tasks"] - tasks_md["completed"])
        progress_pct_diff = abs(progress["task_completion_pct"] - tasks_md["completion_pct"])
        # Warn if counts differ significantly AND completion % differs (both 100% is not drift)
        if (progress_diff > 3 or progress_pct_diff > 10) and not (
            progress["task_completion_pct"] == 100.0 and tasks_md["completion_pct"] == 100.0
        ):
            print(
                f"[Project] WARNING: project.json progress may drift from TASKS.md. "
                f"project.json: {progress['completed_tasks']}/{progress['total_tasks']} "
                f"({progress['task_completion_pct']}%), "
                f"TASKS.md: {tasks_md['completed']}/{tasks_md['total']} "
                f"({tasks_md['completion_pct']}%)",
                file=sys.stderr
            )

    return {
        "project_name": proj.get("project_name", name),
        "description": proj.get("description", ""),
        "milestones": proj.get("milestones", []),
        "backlog": proj.get("backlog", []),
        "notes": proj.get("notes", ""),
        "progress": progress,
        "context_files": full_context["files_read"],
        "git_info": full_context["git_info"],
        "open_todos": todos,
    }

def generate_project_brief() -> str:
    """Generate a brief from CURRENT_FOCUS.md (canonical control doc)."""
    try:
        from src.core.morning_brief import generate_brief
        brief_data = generate_brief()
        
        # Read CURRENT_FOCUS to get real state  
        # PROJECT_ROOT is parent.parent of this file, so we need to go back to the kitty root
        kitty_root = PROJECT_ROOT / "kitty"
        focus_path = kitty_root / "CURRENT_FOCUS.md"
        focus_content = focus_path.read_text(encoding="utf-8") if focus_path.exists() else ""
        
        # Build output: header + progress + working commands + tests
        lines = [
            "# 🐾 KITTY PROJECT BRIEF",
            "",
            f"**Active Phase:** {brief_data['active_focus']}",
            f"**Date:** {brief_data['date']}",
            "",
        ]
        
        # Add forbidden work as scope guard
        if brief_data.get('forbidden_distractions'):
            lines.append("## Forbidden Distractions (Scope Guard)")
            for d in brief_data['forbidden_distractions']:
                lines.append(f"- ❌ {d}")
            lines.append("")
        
        lines.append("## Next Action (Merge Gate)")
        lines.append(brief_data.get('next_action', 'Review CURRENT_FOCUS.md'))
        lines.append("")
        
        # Extract and include relevant sections from CURRENT_FOCUS
        focus_lines = focus_content.splitlines()
        for i, line in enumerate(focus_lines):
            if line.startswith("## Today") or line.startswith("## Working") or line.startswith("## Skills") or line.startswith("## Tests"):
                lines.append(line)
                # Add following content until next ##
                for j in range(i + 1, len(focus_lines)):
                    if focus_lines[j].startswith("##"):
                        break
                    if focus_lines[j].strip():
                        lines.append(focus_lines[j])
                lines.append("")
        
        brief = "\n".join(lines)
    except Exception as e:
        import traceback
        brief = f"[Brief generation error: {e}]\n\nTraceback:\n{traceback.format_exc()}\n\nPlease check CURRENT_FOCUS.md directly."
    
    return brief

def update_project_from_scan():
    """Build comprehensive project state from all sources."""
    state = build_project_state()

    preserved: dict = {}
    if isinstance(session.project_state, dict):
        for k in ("goal_verify", "builder_spec_path"):
            if k in session.project_state:
                preserved[k] = session.project_state[k]

    # Update project.json if needed
    current = {}
    if PROJECT_FILE.exists():
        try:
            with open(PROJECT_FILE) as f: current = json.load(f)
        except (json.JSONDecodeError, OSError): pass

    current["project_name"] = state["project_name"]
    current["description"] = state.get("description", "")
    current["notes"] = f"Active in: {PROJECT_ROOT}"

    with open(PROJECT_FILE, "w") as f: json.dump(current, f, indent=2)

    session.project_state = state
    session.project_state.update(preserved)
    return state

def _pipe_output_until_cap(proc: subprocess.Popen, *, max_chars: int, echo: bool) -> tuple[str, bool]:
    """Drain stdout line-wise until ``max_chars``; returns (text, truncated)."""
    out: list[str] = []
    total = 0
    truncated = False
    if proc.stdout is None:
        return "", False
    for line in proc.stdout:
        if total + len(line) > max_chars:
            out.append(f"\n[Output truncated ({max_chars:,} char limit)]")
            truncated = True
            break
        if echo:
            print(line, end="")
        out.append(line)
        total += len(line)
    return "".join(out), truncated


def _finalize_subprocess(proc: subprocess.Popen, *, truncated: bool, wait_timeout: float) -> None:
    """Ensure child exits; kill aggressively when output was truncated (pipe backpressure)."""
    if truncated:
        proc.kill()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    proc.wait(timeout=wait_timeout)

def run_command(command: str) -> str:
    if not sanitize_command(command):
        return f"Error: Command '{command}' failed safety check."
    blocked = _format_security_findings("<command>", command)
    if blocked:
        return blocked
    log.info("Executing: %s", command)
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            shlex.split(command), shell=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=PROJECT_ROOT,
        )
        output, truncated = _pipe_output_until_cap(proc, max_chars=50_000, echo=True)
        _finalize_subprocess(proc, truncated=truncated, wait_timeout=60)
        if proc.returncode != 0:
            return f"Command exited with code {proc.returncode}:\n{output}"
        return output if output else "Command completed with no output."
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Execution Error: {str(e)}"


def run_trusted_bash_script(script_relative: str) -> str:
    """Run a repo script with bash using argv list (no shell string).

    Used for known entrypoints like run_gates.sh so we do not need to add
    ``bash`` to the interactive command whitelist (which would allow ``bash -c``).
    """
    script = (PROJECT_ROOT / script_relative).resolve()
    try:
        script.relative_to(PROJECT_ROOT)
    except ValueError:
        return "Error: Script path must stay inside the project root."
    if not script.is_file():
        return f"Error: Script not found: {script_relative}"
    log.info("Executing bash script: %s", script)
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            ["/bin/bash", str(script)],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=PROJECT_ROOT,
        )
        output, truncated = _pipe_output_until_cap(proc, max_chars=50_000, echo=True)
        _finalize_subprocess(proc, truncated=truncated, wait_timeout=300)
        if proc.returncode != 0:
            return f"Command exited with code {proc.returncode}:\n{output}"
        return output if output else "Command completed with no output."
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        return "Error: Command timed out after 300 seconds."
    except Exception as e:
        return f"Execution Error: {str(e)}"


def read_file(path: str, max_tokens: int = 2000) -> str:
    """
    Read file with token-aware truncation.

    Args:
        max_tokens: Maximum tokens to read (default 2000 ≈ 8KB text).
    """
    if not is_safe_path(path): return "Error: Access denied (outside project root)."
    try:
        from src.core.prompt_cache import truncate_to_token_budget
        with open(PROJECT_ROOT / path) as f:
            content = f.read(50000)  # Read up to ~50KB
        return truncate_to_token_budget(content, max_tokens=max_tokens)
    except Exception as e: return str(e)

def _format_security_findings(path: str, content: str) -> str:
    findings = scan_text(path, content)
    if not findings:
        return ""
    lines = ["Error: Security scan blocked builder action."]
    for finding in findings[:10]:
        lines.append(
            f"- {finding.severity} {finding.rule} at {finding.path}:{finding.line}: {finding.message}"
        )
    if len(findings) > 10:
        lines.append(f"- ... {len(findings) - 10} more finding(s)")
    return "\n".join(lines)

def write_file(path: str, content: str) -> str:
    if not is_safe_path(path): return "Error: Access denied."
    blocked = _format_security_findings(path, content)
    if blocked:
        return blocked
    try:
        full_path = PROJECT_ROOT / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w") as f: f.write(content)
        verify_note = ""
        if path.endswith(".py"):
            try:
                py_compile.compile(str(full_path), doraise=True)
                verify_note = " py_compile: OK."
            except py_compile.PyCompileError as e:
                verify_note = f" py_compile warning: {e.msg} (file saved)."
        # Quality judge
        judge = quality_judge(path)
        return f"File {path} written.{verify_note} Review: {judge}"
    except Exception as e: return str(e)

def quality_judge(path: str) -> str:
    try:
        with open(PROJECT_ROOT / path) as f: code = f.read(3000)
        content = f"Review this code briefly. Grade A-F and give one sentence of feedback.\nFile: {path}\nCode:\n```\n{code}\n```"
        if USE_OPENROUTER and OPENROUTER_API_KEY:
            return generate_openrouter(content, max_tokens=80, temp=0.1).strip()
        model, tok = get_model(MODEL_BUILDER, force_local=True)
        messages = [{"role": "user", "content": content}]
        prompt = _build_prompt(tok, messages)
        return generate(model, tok, prompt=prompt, max_tokens=80,
                        sampler=make_sampler(temp=0.1)).strip()
    except Exception:
        return "Judge unavailable."

def update_project(action: str, **kwargs) -> str:
    proj = session.project_state
    milestones = proj.setdefault("milestones", [])

    if action == "add_task":
        task_str = kwargs.get("task") or kwargs.get("task_name") or kwargs.get("title")
        if not task_str or not str(task_str).strip():
            return "Error: add_task requires a non-empty task/title."
        task_str = str(task_str).strip()
        mid = kwargs.get("milestone_id") if kwargs.get("milestone_id") is not None else kwargs.get("milestone_number")
        found = False
        for m in milestones:
            if m.get("id") == mid:
                m.setdefault("tasks", []).append(task_str)
                found = True
                break
        if not found:
            return f"Error: milestone id {mid!r} not found."
    elif action == "mark_task_done":
        mid = kwargs.get("milestone_id") if kwargs.get("milestone_id") is not None else kwargs.get("milestone_number")
        task_str = kwargs.get("task") or kwargs.get("task_name") or kwargs.get("title")
        if not task_str or not str(task_str).strip():
            return "Error: mark_task_done requires a non-empty task/title."
        task_str = str(task_str).strip()
        found = False
        for m in milestones:
            if m.get("id") == mid and task_str in m.get("tasks", []):
                m["tasks"].remove(task_str)
                m.setdefault("done_tasks", []).append(task_str)
                found = True
                break
        if not found:
            return f"Error: task not found on milestone {mid!r}."
    elif action == "move_to_backlog":
        task_str = kwargs.get("task") or kwargs.get("task_name") or kwargs.get("title")
        if not task_str or not str(task_str).strip():
            return "Error: move_to_backlog requires a non-empty task/title."
        task_str = str(task_str).strip()
        for m in milestones:
            if task_str in m.get("tasks", []):
                m["tasks"].remove(task_str)
        proj.setdefault("backlog", []).append(task_str)
    elif action == "add_note":
        note = kwargs.get("note") or ""
        proj["notes"] = (proj.get("notes", "") + "\n" + str(note)).strip()
    elif action == "add_milestone":
        new_id = max([m.get("id", 0) for m in milestones], default=0) + 1
        title = kwargs.get("title") or kwargs.get("name") or f"Milestone {new_id}"
        milestones.append({
            "id": new_id,
            "title": title,
            "status": "todo",
            "tasks": []
        })
        action = f"add_milestone ({title})"
    else:
        return f"Error: Unknown action '{action}'"

    with open(PROJECT_FILE, "w") as f: json.dump(proj, f, indent=2)
    return f"Project updated: {action}"

def search_web(query: str) -> str:
    if not WEB_SEARCH_API_KEY:
        return "Error: Web search disabled (set TAVILY_API_KEY)."
    for attempt in range(2):
        try:
            import requests
            resp = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": WEB_SEARCH_API_KEY, "query": query, "search_depth": "basic"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:5]
            return "\n".join(f"- {r['title']}: {r['url']}" for r in results) if results else "No results found."
        except Exception as e:
            if attempt == 1:
                return f"Search error after retries: {e}"
    return "Search error: unknown"

def get_project_brief() -> str:
    return generate_project_brief()

def run_pattern(pattern_name: str, text: str) -> str:
    """Run a pattern on the given text. Available patterns: summarize, action-items, explain-code, review-code, audit, breakdown, compare, brainstorm"""
    patterns_path = PROJECT_ROOT / "config" / "patterns.json"
    if not patterns_path.exists():
        return "Error: patterns.json not found"

    try:
        with open(patterns_path) as f:
            patterns = json.load(f)

        if pattern_name not in patterns:
            return f"Error: Pattern '{pattern_name}' not found. Available: {', '.join(patterns.keys())}"

        prompt_template = patterns[pattern_name]["prompt"]
        prompt = prompt_template.replace("{text}", text)

        if USE_OPENROUTER and OPENROUTER_API_KEY:
            return generate_openrouter(prompt, max_tokens=1000, temp=0.5)
        else:
            model, tok = get_model(MODEL_BUILDER, force_local=True)
            messages = [{"role": "user", "content": prompt}]
            return generate(model, tok, prompt=_build_prompt(tok, messages),
                          max_tokens=1000, sampler=make_sampler(temp=0.5))
    except Exception as e:
        return f"Error running pattern: {e}"

def scan_project_health() -> str:
    """Thorough project health scan with codebase analysis."""
    state = build_project_state()
    p = state["progress"]

    issues = []
    warnings = []

    if p["task_completion_pct"] < 30:
        issues.append("Low task completion (<30%)")
    if p["open_todos"] > 5:
        issues.append(f"Many open TODOs ({p['open_todos']})")
    if len(state.get("backlog", [])) > 10:
        issues.append(f"Large backlog ({len(state['backlog'])} items)")

    git_status = state.get("git_info", {}).get("status", "")
    git_lines = [l for l in git_status.split("\n") if l.strip()]
    untracked = len([l for l in git_lines if l.startswith("??")])
    modified = len([l for l in git_lines if l.startswith((" M", "M "))])
    if untracked > 10:
        warnings.append(f"Many untracked files ({untracked})")
    if modified > 10:
        warnings.append(f"Many modified files ({modified})")

    # Check for stale/incomplete files
    import os, glob
    project_root = PROJECT_ROOT
    stale_patterns = [
        ("CURRENT_PROJECT_STATE.json", "Stale debug file at project root"),
    ]
    for fname, desc in stale_patterns:
        if (project_root / fname).exists():
            warnings.append(f"{fname}: {desc}")

    # Check for missing requirements.txt
    if not (project_root / "requirements.txt").exists():
        warnings.append("Missing requirements.txt (dependency documentation)")

    # Check test count
    test_files = list(project_root.glob("tests/**/test_*.py"))
    if len(test_files) < 10:
        warnings.append(f"Low test coverage ({len(test_files)} test files)")

    report = f"""# Project Health Report

**Progress:** {p['task_completion_pct']}% tasks, {p['milestone_completion_pct']}% milestones
**Remaining:** {p['remaining_tasks']} tasks, {p['open_todos']} TODOs

## Status: {"⚠️ Needs Attention" if issues else "✅ Healthy"}
"""
    if issues:
        report += "## Issues:\n" + "\n".join(f"- {i}" for i in issues) + "\n"
    if warnings:
        report += "## Warnings:\n" + "\n".join(f"- {w}" for w in warnings) + "\n"

    report += f"""
## Quick Stats
- Milestones: {len(state['milestones'])}
- Backlog: {len(state['backlog'])} items
- Git changes: {len(git_lines)} ({untracked} untracked, {modified} modified)
- Test files: {len(test_files)}
- Python files: {len(list(project_root.rglob('*.py')))}
"""
    return report

def suggest_next_steps() -> str:
    """Suggest the best next steps based on current state."""
    state = session.project_state
    recommendations: list[str] = []

    latched_spec = state.get("builder_spec_path") if isinstance(state, dict) else None
    goal = state.get("goal_verify") if isinstance(state, dict) else None

    stop = {
        "spec", "specs", "with", "from", "over", "this", "that", "goal",
        "verify", "quality", "output", "prioritize", "candidate",
    }
    keywords: set[str] = set()
    if latched_spec:
        for word in re.findall(r"[a-z]{4,}", Path(str(latched_spec)).stem.lower()):
            if word not in stop:
                keywords.add(word)
    if goal:
        for word in re.findall(r"[a-z]{4,}", goal.lower()):
            if word not in stop:
                keywords.add(word)

    if latched_spec:
        recommendations.append(f"Start with latched spec: `{latched_spec}`")
    if goal:
        recommendations.append(f"Keep this verification goal active: {goal}")

    # Find incomplete milestones
    for m in state.get("milestones", []):
        if m.get("status") == "doing" and m.get("tasks"):
            task = m["tasks"][0]
            recommendations.append(f"Finish active milestone task: {task} (Milestone: {m['title']})")
            break

    # Check backlog, preferring entries that match latched spec/goal keywords.
    backlog = state.get("backlog") or []
    if backlog:
        picked = None
        if keywords:
            for item in backlog:
                low = str(item).lower()
                if any(k in low for k in keywords):
                    picked = item
                    break
        if picked is None and not latched_spec:
            picked = backlog[0]
        if picked is not None:
            recommendations.append(f"Pick backlog item: {picked}")

    # Open TODOs, preferring entries related to current spec/goal.
    todos = state.get("open_todos", [])
    if todos:
        picked_todo = None
        if keywords:
            for t in todos:
                txt = str(t.get("text", "")).lower()
                if any(k in txt for k in keywords):
                    picked_todo = t
                    break
        if picked_todo is None and not latched_spec:
            picked_todo = todos[0]
        if picked_todo is not None:
            recommendations.append(f"Address TODO: {picked_todo.get('text', '')[:80]}")

    if not recommendations:
        return "No specific recommendations - project looks good!"

    lines = [f"{idx}. {item}" for idx, item in enumerate(recommendations, start=1)]
    return "## Recommended Next Steps\n\n" + "\n\n".join(lines)


def _git_short_status_for_brief(*, max_lines: int = 18) -> tuple[int, str]:
    """Return (line_count, printable excerpt) for porcelain status."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=8,
        )
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        n = len(lines)
        body = "\n".join(lines[:max_lines])
        if n > max_lines:
            body += f"\n… ({n - max_lines} more lines)"
        return n, body if body else "(clean working tree)"
    except (subprocess.SubprocessError, OSError) as e:
        return -1, f"(git unavailable: {e})"


def _current_focus_excerpt() -> str:
    focus_path = PROJECT_ROOT / "CURRENT_FOCUS.md"
    if not focus_path.is_file():
        return "(no CURRENT_FOCUS.md)"
    try:
        for line in focus_path.read_text().splitlines():
            if line.startswith("## Current Task"):
                return line.strip()
        head = focus_path.read_text().splitlines()[:5]
        return "\n".join(head) if head else "(empty CURRENT_FOCUS.md)"
    except (OSError, UnicodeDecodeError) as e:
        return f"(CURRENT_FOCUS read error: {e})"


def _builder_scope_block(project_state: dict) -> str:
    """Injected into SYSTEM_PROMPT when /spec has latched a file."""
    if not isinstance(project_state, dict):
        return ""
    sp = project_state.get("builder_spec_path")
    if not sp:
        return ""
    p = PROJECT_ROOT / sp
    exists = p.is_file()
    return (
        "\n--- SESSION SPEC LATCH ---\n"
        f"Approved spec file (relative to repo): {sp}\n"
        f"Exists on disk: {exists}\n"
        "Stay aligned with this spec; do not broaden scope unless Jacob clears `/spec` or explicitly redirects.\n"
    )


def builder_session_start_brief() -> str:
    """One-screen session opener: git, focus, optional latched spec, budget, next steps."""
    update_project_from_scan()
    dirty_n, dirty_body = _git_short_status_for_brief()
    focus = _current_focus_excerpt()
    spec_note = ""
    if isinstance(session.project_state, dict):
        sp = session.project_state.get("builder_spec_path")
        if sp:
            spec_note = f"\n**Latched spec:** `{sp}`  (clear with `/spec clear`)\n"

    nxt = suggest_next_steps()

    lines = [
        "# Builder session start",
        "",
        f"**Budget:** {budget.summary()}",
        "",
        f"**CURRENT_FOCUS:** {focus}",
        spec_note.strip(),
        "",
        f"**Git:** {dirty_n} changed path(s) when counted via porcelain.",
        "```",
        dirty_body,
        "```",
        "",
        nxt,
        "",
        "Tip: run **`run_project_gates`** tool or `/gates` before claiming green.",
    ]
    return "\n".join(x for x in lines if x is not None)


def run_project_gates() -> str:
    """Run ``scripts/run_gates.sh`` (trusted bash). Returns PASS/FAIL headline + output tail."""
    raw = run_trusted_bash_script("scripts/run_gates.sh")
    m = re.search(r"Command exited with code (\d+):", raw)
    code = int(m.group(1)) if m else None
    ok = code == 0 if code is not None else not raw.startswith("Error:")
    headline = "PASS — project gates completed (exit 0)." if ok else (
        f"FAIL — gates exited with code {code}." if code is not None else "FAIL — could not run gates."
    )
    tail = raw if len(raw) <= 12_000 else raw[-12_000:]
    return f"{headline}\n\n--- output (tail) ---\n{tail}"


def _delegate_git_diff_stat_suffix() -> str:
    """Append after delegate so Jacob sees tree movement without reading full worker logs."""
    if os.environ.get("KITTY_BUILDER_DELEGATE_DIFF", "1").strip().lower() in (
        "0", "false", "no", "off",
    ):
        return ""
    try:
        r = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )
        out = (r.stdout or "").strip()
        if not out:
            return ""
        cap = 6000
        if len(out) > cap:
            out = out[:cap] + "\n… (truncated)"
        return f"\n\n--- git diff --stat ---\n{out}"
    except (subprocess.SubprocessError, OSError) as e:
        return f"\n\n--- git diff --stat ---\n(unavailable: {e})"


def kitty_self_improve() -> str:
    """Run comprehensive self-improvement loop: test, audit, grade, fix, improve."""
    print("\n" + "="*60)
    print("🐱 KITTY SELF-IMPROVEMENT LOOP")
    print("="*60)

    results = {
        "test_results": {},
        "audit_findings": [],
        "grade": "N/A",
        "fixes_applied": [],
        "feedback": [],
    }

    # Step 1: Run tests (no shell pipe — sanitize_command blocks ``|``)
    print("\n[1/6] Running test suite...")
    test_output = run_command(f"{sys.executable} -m pytest tests/ -q --tb=short")
    results["test_results"]["output"] = test_output
    # Pytest summary uses ``N failed``; substring `` failed`` false-negatives on ``0 failed``.
    fail_m = re.search(r"(\d+)\s+failed", test_output, re.IGNORECASE)
    failed_count = int(fail_m.group(1)) if fail_m else 0
    err_m = re.search(r"(\d+)\s+error", test_output, re.IGNORECASE)
    error_count = int(err_m.group(1)) if err_m else 0
    test_passed = failed_count == 0 and error_count == 0 and (
        "passed" in test_output.lower() or "no tests ran" in test_output.lower()
    )
    results["test_results"]["passed"] = test_passed

    # Step 2: Run self-review
    print("[2/6] Running code audit...")
    all_code = ""
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'node_modules')]
        for f in files:
            if f.endswith('.py') and len(all_code) < 8000:
                try:
                    with open(os.path.join(root, f)) as src:
                        all_code += f"\n# {f}\n{src.read(1500)}"
                except OSError:
                    continue

    prompt = f"Audit this code for bugs, security issues, and logic flaws. List ONLY the top 5 most critical issues in this format:\n1. [file:line] - issue description\n\nCode:\n{all_code[:6000]}"

    if USE_OPENROUTER and OPENROUTER_API_KEY:
        audit_result = generate_openrouter(prompt, max_tokens=800, temp=0.3)
    else:
        model, tok = get_model(MODEL_BUILDER, force_local=True)
        messages = [{"role": "user", "content": prompt}]
        audit_result = generate(model, tok, prompt=_build_prompt(tok, messages),
                               max_tokens=800, sampler=make_sampler(temp=0.3))

    audit_result = audit_result or "[Audit returned no output]"
    results["audit_findings"] = audit_result

    # Step 3: Generate grade
    print("[3/6] Generating grade...")
    grade_factors = []
    if test_passed:
        grade_factors.append("Tests passing")
    else:
        grade_factors.append("Tests failing")

    # Check for critical issues
    critical_count = audit_result.lower().count("critical") + audit_result.lower().count("bug") + audit_result.lower().count("error")
    if critical_count == 0:
        grade_factors.append("No critical bugs")
    else:
        grade_factors.append(f"{critical_count} potential issues")

    # Calculate grade
    score = 100
    if not test_passed:
        score -= 30
    score -= min(critical_count * 10, 40)
    score = max(score, 0)

    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    results["grade"] = grade
    results["score"] = score

    # Step 4: Provide actionable feedback
    print("[4/6] Generating feedback...")
    feedback_items = []
    if not test_passed:
        feedback_items.append("- Fix failing tests first (run pytest for details)")
    if critical_count > 0:
        feedback_items.append(f"- Address {critical_count} critical issues from audit")

    feedback_items.append("- Review backlog and pick next task")
    feedback_items.append("- Consider running /health for project status")

    results["feedback"] = feedback_items

    # Step 5: Summary
    print("[5/6] Summary")
    print("-" * 40)
    print(f"Tests: {'✅ PASS' if test_passed else '❌ FAIL'}")
    print(f"Audit: {critical_count} issues found")
    print(f"Grade: {grade} ({score}/100)")

    # Step 6: Recommendations
    print("\n[6/6] Actionable Feedback:")
    for fb in feedback_items:
        print(f"  {fb}")

    print("\n" + "="*60)
    print(f"FINAL GRADE: {grade}")
    print("="*60)

    return f"""# Kitty Self-Improvement Report

## Test Results: {'✅ PASS' if test_passed else '❌ FAIL'}

## Audit Findings:
{audit_result[:1000]}

## Grade: {grade} ({score}/100)

## Actionable Feedback:
{chr(10).join(feedback_items)}

Run this function periodically to track Kitty's health.
"""

TOOLS = {
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
    "modify_project_tasks": update_project,
    "search_web": search_web,
    "launch_kitty": lambda: run_command(f"{sys.executable} -m pytest tests/ -q --tb=short"),
    "generate_project_brief": get_project_brief,
    "builder_session_start": builder_session_start_brief,
    "run_project_gates": run_project_gates,
    "run_pattern": run_pattern,
    "scan_project_health": scan_project_health,
    "suggest_next_steps": suggest_next_steps,
    "kitty_self_improve": kitty_self_improve,  # defined above
}

# ------------------------------------------------------------
# BUDGET TRACKING
# ------------------------------------------------------------
BUDGET_FILE = PROJECT_ROOT / ".kitty_builder_budget.json"
TOKEN_USAGE_FILE = PROJECT_ROOT / "data" / "kitty_token_log.jsonl"
BUILDER_EVIDENCE_FILE = PROJECT_ROOT / "data" / "builder_evidence.jsonl"

class BudgetManager:
    """Daily spend ledger with atomic persistence + hard-cap enforcement.

    Caps are read from env at construction time:
      KITTY_BUDGET_OR_USD       — daily OpenRouter cap (default: 1.00)
      KITTY_BUDGET_CLAUDE_USD   — daily Claude-CLI cap (default: 5.00)
    """

    DEFAULT_OR_CAP_USD = float(os.environ.get("KITTY_BUDGET_OR_USD", "1.00"))
    DEFAULT_CLAUDE_CAP_USD = float(os.environ.get("KITTY_BUDGET_CLAUDE_USD", "5.00"))

    def __init__(self) -> None:
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.groq_requests = 0
        self.or_spend_usd = 0.0
        self.claude_spend_usd = 0.0
        self.per_model: Dict[str, Dict[str, float]] = {}
        self.or_cap_usd = self.DEFAULT_OR_CAP_USD
        self.claude_cap_usd = self.DEFAULT_CLAUDE_CAP_USD
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not BUDGET_FILE.exists():
            return
        try:
            d = json.loads(BUDGET_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Budget] load failed: {e}", file=sys.stderr)
            return
        if d.get("date") == self.today:
            self.groq_requests = d.get("groq_requests", 0)
            self.or_spend_usd = d.get("or_spend_usd", 0.0)
            self.claude_spend_usd = d.get("claude_spend_usd", 0.0)
            self.per_model = d.get("per_model", {}) or {}

    def save(self) -> None:
        """Atomic write: tmp file + os.replace prevents corruption on crash."""
        payload = {
            "date": self.today,
            "groq_requests": self.groq_requests,
            "or_spend_usd": self.or_spend_usd,
            "claude_spend_usd": self.claude_spend_usd,
            "per_model": self.per_model,
        }
        tmp = BUDGET_FILE.with_suffix(BUDGET_FILE.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2))
            os.replace(tmp, BUDGET_FILE)
        except OSError as e:
            print(f"[Budget] save failed: {e}", file=sys.stderr)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def assert_can_spend(self, *, provider: str, est_usd: float = 0.0) -> None:
        """Raise BudgetExhausted if the projected total would exceed the daily cap."""
        with self._lock:
            if provider == "or":
                if self.or_spend_usd + est_usd > self.or_cap_usd:
                    raise BudgetExhausted(
                        "BUDGET_EXHAUSTED",
                        f"OpenRouter daily cap ${self.or_cap_usd:.2f} would be exceeded "
                        f"(spent ${self.or_spend_usd:.4f}, +${est_usd:.4f}). "
                        f"Raise KITTY_BUDGET_OR_USD or wait for reset.",
                    )
            elif provider == "claude":
                if self.claude_spend_usd + est_usd > self.claude_cap_usd:
                    raise BudgetExhausted(
                        "BUDGET_EXHAUSTED",
                        f"Claude-CLI daily cap ${self.claude_cap_usd:.2f} would be exceeded "
                        f"(spent ${self.claude_spend_usd:.4f}, +${est_usd:.4f}). "
                        f"Raise KITTY_BUDGET_CLAUDE_USD or wait for reset.",
                    )

    def assert_groq_request_allowed(self) -> None:
        """Optional daily Groq cap (free tier abuse guard). 0 = unlimited."""
        cap = int(os.environ.get("KITTY_BUDGET_GROQ_MAX_REQUESTS", "0"))
        if cap <= 0:
            return
        with self._lock:
            if self.groq_requests >= cap:
                raise BudgetExhausted(
                    "GROQ_DAILY_CAP",
                    f"Groq daily request cap ({cap}) reached "
                    f"(KITTY_BUDGET_GROQ_MAX_REQUESTS). Wait for ledger reset or raise the cap.",
                )

    def record_groq(self) -> None:
        with self._lock:
            self.groq_requests += 1
        self.save()

    def record_or(self, cost: float = 0.001, *, model: Optional[str] = None) -> None:
        with self._lock:
            self.or_spend_usd += cost
            if model:
                m = self.per_model.setdefault(model, {"usd": 0.0, "calls": 0})
                m["usd"] += cost
                m["calls"] = m.get("calls", 0) + 1
        self.save()

    def record_claude(self, cost: float) -> None:
        with self._lock:
            self.claude_spend_usd += cost
        self.save()

    def summary(self) -> str:
        return (f"Groq: {self.groq_requests} req (free) | "
                f"OR: ${self.or_spend_usd:.4f}/${self.or_cap_usd:.2f} | "
                f"Claude CLI: ${self.claude_spend_usd:.4f}/${self.claude_cap_usd:.2f}")

    def per_model_summary(self) -> str:
        if not self.per_model:
            return "No per-model spend recorded today."
        rows = sorted(self.per_model.items(), key=lambda kv: kv[1].get("usd", 0.0), reverse=True)
        lines = [f"  {m:<55} ${v.get('usd', 0):.4f}  ({v.get('calls', 0)} calls)"
                 for m, v in rows]
        return "Per-model spend today:\n" + "\n".join(lines)

budget = BudgetManager()


def _extract_usage_dict(usage_obj: Any) -> dict[str, int]:
    """Best-effort usage extraction from OpenAI/Groq SDK response objects."""
    if usage_obj is None:
        return {}
    if isinstance(usage_obj, dict):
        raw = usage_obj
    else:
        raw = {}
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "reasoning_tokens",
            "cached_tokens",
        ):
            value = getattr(usage_obj, key, None)
            if isinstance(value, int):
                raw[key] = value
    out: dict[str, int] = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "reasoning_tokens",
        "cached_tokens",
    ):
        value = raw.get(key)
        if isinstance(value, int):
            out[key] = value
    # OpenAI-style nested prompt token details.
    details = raw.get("prompt_tokens_details") if isinstance(raw, dict) else None
    if isinstance(details, dict):
        cached = details.get("cached_tokens")
        if isinstance(cached, int):
            out.setdefault("cached_tokens", cached)
    return out


def log_token_usage(
    *,
    provider: str,
    model: str,
    operation: str,
    usage: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a per-call token usage row to local JSONL telemetry."""
    TOKEN_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "provider": provider,
        "model": model,
        "operation": operation,
        "usage": usage or {},
        "metadata": metadata or {},
    }
    try:
        with open(TOKEN_USAGE_FILE, "a") as f:
            f.write(json.dumps(row) + "\n")
    except OSError as e:
        print(f"[TokenUsage] write failed: {e}", file=sys.stderr)


def _today_token_usage_summary() -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    totals = {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cached_tokens": 0,
        "completion_chars": 0,
    }
    per_model: dict[str, dict[str, int]] = {}
    if not TOKEN_USAGE_FILE.exists():
        return {"totals": totals, "per_model": per_model}
    try:
        with open(TOKEN_USAGE_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("date") != today:
                    continue
                totals["calls"] += 1
                usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
                md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                for key in (
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "reasoning_tokens",
                    "cached_tokens",
                ):
                    val = usage.get(key, 0)
                    if isinstance(val, int):
                        totals[key] += val
                comp_chars = md.get("completion_chars", 0)
                if isinstance(comp_chars, int):
                    totals["completion_chars"] += comp_chars

                model = row.get("model", "unknown")
                slot = per_model.setdefault(
                    model,
                    {
                        "calls": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                )
                slot["calls"] += 1
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    val = usage.get(key, 0)
                    if isinstance(val, int):
                        slot[key] += val
    except OSError as e:
        print(f"[TokenUsage] read failed: {e}", file=sys.stderr)
    return {"totals": totals, "per_model": per_model}


def get_builder_token_usage() -> str:
    """Return today's per-call token usage summary from local JSONL telemetry."""
    summary = _today_token_usage_summary()
    totals = summary["totals"]
    if totals["calls"] == 0:
        return "No token telemetry rows recorded today."
    lines = [
        "Token usage today:",
        f"  calls: {totals['calls']}",
        f"  prompt_tokens: {totals['prompt_tokens']}",
        f"  completion_tokens: {totals['completion_tokens']}",
        f"  total_tokens: {totals['total_tokens']}",
        f"  reasoning_tokens: {totals['reasoning_tokens']}",
        f"  cached_tokens: {totals['cached_tokens']}",
        f"  completion_chars: {totals['completion_chars']}",
    ]
    per_model = summary["per_model"]
    if per_model:
        lines.append("")
        lines.append("Per-model token usage:")
        rows = sorted(per_model.items(), key=lambda kv: kv[1].get("total_tokens", 0), reverse=True)
        for model, stats in rows:
            lines.append(
                f"  {model:<55} total={stats['total_tokens']} "
                f"prompt={stats['prompt_tokens']} completion={stats['completion_tokens']} "
                f"calls={stats['calls']}"
            )
    return "\n".join(lines)


def get_builder_budget() -> str:
    """Return today's recorded Builder ledger — same data as the ``/budget`` slash command.

    Groq request count, OpenRouter USD (vs cap), Claude CLI USD (vs cap), and per-model OR rows.
    Does not include subscriptions or external tools; never extrapolate hourly rates from this.
    """
    return (
        f"{budget.summary()}\n\n"
        f"{budget.per_model_summary()}\n\n"
        "---\n"
        "Ledger scope: in-process KittyBuilder counters only (not full Jacob-wide cloud bills)."
    )


def compile_builder_request(text: str) -> str:
    """Compile a raw request into a structured brief without writing files."""
    from src.builder.intent_compiler import compile_intent

    brief = compile_intent(PROJECT_ROOT, text)
    return json.dumps(brief.to_dict(), indent=2)


def worker_health_summary() -> str:
    """Return a read-only health summary for configured delegate workers."""
    from src.builder.worker_health import check_worker_health

    lines = ["Worker health:"]
    for name in _DELEGATE_ORDER:
        result = check_worker_health(name)
        state = "available" if result.available else "missing"
        detail = result.path or result.reason or "unknown"
        lines.append(f"- {result.name}: {state} ({detail})")
    return "\n".join(lines)


def record_builder_recommendation(
    *,
    raw_input: str,
    outcome: str,
    workers: list[str],
    commands_run: list[str],
    risks: list[str],
    next_agent_packet: dict[str, object] | None = None,
) -> None:
    """Append a minimal recommendation row to the builder evidence ledger."""
    from src.builder.evidence_ledger import append_evidence

    append_evidence(
        BUILDER_EVIDENCE_FILE,
        run_id=datetime.now().strftime("builder-%Y%m%dT%H%M%S"),
        raw_input_hash=hashlib.sha256(raw_input.encode("utf-8")).hexdigest(),
        outcome=outcome,
        workers=workers,
        files_changed=[],
        commands_run=commands_run,
        risks=risks,
        next_agent_packet=next_agent_packet or {},
    )


TOOLS["get_builder_budget"] = get_builder_budget
TOOLS["get_builder_token_usage"] = get_builder_token_usage
TOOLS["compile_builder_request"] = compile_builder_request
TOOLS["worker_health_summary"] = worker_health_summary

# ------------------------------------------------------------
# BRAIN — configurable tier order (KITTY_BUILDER_BRAIN_ORDER)
# ------------------------------------------------------------


def _brain_tier_groq(messages: list, response_parts: list[str]) -> bool:
    if not _groq_client:
        return False
    try:
        budget.assert_groq_request_allowed()
    except BudgetExhausted as e:
        print(f"\n[Groq cap] {e} → next tier…", file=sys.stderr)
        return False
    try:
        resp = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=1500,
            temperature=0.7,
            stream=True,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
                response_parts.append(delta)
        budget.record_groq()
        log_token_usage(
            provider="groq",
            model=GROQ_MODEL,
            operation="chat.completions.create",
            usage={},
            metadata={"stream": True, "completion_chars": len("".join(response_parts))},
        )
        print()
        return True
    except Exception as e:
        print(f"\n[Groq failed: {str(e)[:70]}] → next tier…", file=sys.stderr)
        response_parts.clear()
        return False


def _brain_tier_openrouter(messages: list, response_parts: list[str]) -> bool:
    if not (USE_OPENROUTER and _openrouter_client):
        return False
    try:
        budget.assert_can_spend(provider="or", est_usd=0.0)
        current_model: Optional[str] = None
        for model_id, delta in stream_openrouter(
            messages, max_tokens=1500, temperature=0.7
        ):
            if model_id != current_model:
                if current_model is not None:
                    print()
                print(f"[{model_id}]", flush=True)
                current_model = model_id
            print(delta, end="", flush=True)
            response_parts.append(delta)
        print()
        return True
    except BudgetExhausted as e:
        print(f"\n[Budget] {e} → next tier…", file=sys.stderr)
        response_parts.clear()
        return False
    except BuilderError as e:
        print(f"\n[OpenRouter {e.code}] {e} → next tier…", file=sys.stderr)
        response_parts.clear()
        return False


def _brain_tier_mlx(messages: list, response_parts: list[str]) -> bool:
    if load is None:
        return False
    try:
        model, tok = get_model(MODEL_BUILDER, force_local=True)
        prompt = _build_prompt(tok, messages, thinking=False)
        for r in stream_generate(
            model,
            tok,
            prompt,
            max_tokens=1500,
            sampler=make_sampler(temp=0.7),
        ):
            print(r.text, end="", flush=True)
            response_parts.append(r.text)
        log_token_usage(
            provider="mlx",
            model=MODEL_BUILDER,
            operation="stream_generate",
            usage={},
            metadata={"stream": True, "completion_chars": len("".join(response_parts))},
        )
        print()
        return True
    except Exception as e:
        print(f"\n[MLX failed: {e}] → next tier…", file=sys.stderr)
        response_parts.clear()
        return False


def _stream_brain(messages: list) -> str:
    """Run tiers in ``KITTY_BUILDER_BRAIN_ORDER`` until one completes."""
    order = _parse_brain_order()
    runners = {
        "groq": _brain_tier_groq,
        "openrouter": _brain_tier_openrouter,
        "mlx": _brain_tier_mlx,
    }
    response_parts: list[str] = []
    for name in order:
        fn = runners.get(name)
        if fn is None:
            continue
        if not fn(messages, response_parts):
            continue
        text = "".join(response_parts)
        if name == "mlx":
            return text.strip()
        return text
    return "Error: all brain tiers unavailable."


# ------------------------------------------------------------
# WORKER DISPATCH — stream any CLI to Jacob's terminal
# ------------------------------------------------------------

_DELEGATE_ALIASES = ("claude", "gemini", "opencode", "aider", "crush", "agent", "goose")
_policy_delegate_order = tuple(
    c for c in ORCHESTRATOR_POLICY.get("delegate_order", []) if c in _DELEGATE_ALIASES
)
_DELEGATE_ORDER = _policy_delegate_order or _DELEGATE_ALIASES


def _delegate_argv(cli: str, ctx: str) -> Optional[list[str]]:
    """Build argv for worker CLI; binaries resolved via ``*_BIN`` env then PATH."""
    bh = str(Path.home() / ".local/bin")
    rows: dict[str, tuple[str, tuple[str, ...]]] = {
        "claude": ("KITTY_CLAUDE_BIN", ("/opt/homebrew/bin/claude",)),
        "gemini": ("KITTY_GEMINI_BIN", ("/opt/homebrew/bin/gemini",)),
        "opencode": ("KITTY_OPENCODE_BIN", ("/opt/homebrew/bin/opencode",)),
        "aider": ("KITTY_AIDER_BIN", ("/opt/homebrew/bin/aider",)),
        "crush": ("KITTY_CRUSH_BIN", ("/opt/homebrew/bin/crush",)),
        "agent": ("KITTY_AGENT_BIN", (f"{bh}/agent",)),
        "goose": ("KITTY_GOOSE_BIN", (f"{bh}/goose",)),
    }
    if cli not in rows:
        return None
    env_key, defaults = rows[cli]
    exe = _resolve_tool_bin(env_key, *defaults)
    if not exe:
        return None
    if cli == "claude":
        return [exe, "-p", "--no-session-persistence", ctx]
    if cli == "gemini":
        return [exe, "-p", ctx]
    if cli == "opencode":
        return [exe, "run", ctx]
    if cli == "aider":
        return [exe, "--message", ctx, "--yes-always", "--no-auto-commits"]
    if cli == "crush":
        return [exe, "run", ctx]
    if cli == "agent":
        return [exe, "-p", ctx]
    if cli == "goose":
        return [exe, "run", "-t", ctx]
    return None


def _git_snapshot() -> set:
    try:
        r = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                           text=True, cwd=PROJECT_ROOT, timeout=5)
        return {line[3:].strip() for line in r.stdout.splitlines() if line.strip()}
    except (subprocess.SubprocessError, OSError) as e:
        print(f"[Worker] git snapshot failed: {e}", file=sys.stderr)
        return set()

def _worker_context(task: str) -> str:
    lines = [f"Project: {PROJECT_ROOT}"]
    focus_path = PROJECT_ROOT / "CURRENT_FOCUS.md"
    if focus_path.exists():
        try:
            for line in focus_path.read_text().splitlines():
                if line.startswith("## Current Task"):
                    lines.append(f"Focus: {line}")
                    break
        except (OSError, UnicodeDecodeError) as e:
            print(f"[Worker] focus read failed: {e}", file=sys.stderr)
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True,
                           text=True, cwd=PROJECT_ROOT, timeout=5)
        if r.stdout.strip():
            n = len(r.stdout.strip().splitlines())
            lines.append(f"Dirty: {n} files modified")
    except (subprocess.SubprocessError, OSError) as e:
        print(f"[Worker] git status failed: {e}", file=sys.stderr)
    lines.append(f"\nTask: {task}")
    return "\n".join(lines)


def _delegate_packet_enabled() -> bool:
    raw = os.environ.get("KITTY_BUILDER_DELEGATE_PACKET", "1").strip().lower()
    return raw not in ("0", "false", "no")


def _delegate_packet_for_task(task: str) -> dict[str, object]:
    if not _delegate_packet_enabled():
        return {}
    try:
        from src.builder.intent_compiler import compile_intent

        brief = compile_intent(PROJECT_ROOT, task)
        packet = brief.next_agent_packet if isinstance(brief.next_agent_packet, dict) else {}
        return packet
    except Exception as e:
        print(f"[Worker] delegate packet compile failed: {e}", file=sys.stderr)
        return {}


def _delegate_context_with_packet(base_ctx: str, packet: dict[str, object]) -> str:
    if not packet:
        return base_ctx
    # Keep packet compact and deterministic for downstream workers.
    slim: dict[str, object] = {
        "schema_version": packet.get("schema_version", "builder_handoff.v1"),
        "stage": packet.get("stage", "intent_compiled"),
        "objective": packet.get("objective", ""),
        "recommended_mode": packet.get("recommended_mode", ""),
        "must_do": packet.get("must_do", []),
        "must_not_do": packet.get("must_not_do", []),
        "context_targets": packet.get("context_targets", []),
        "validation_commands": packet.get("validation_commands", []),
        "blocking_question": packet.get("blocking_question", ""),
        "output_contract": packet.get("output_contract", []),
        "next_prompt": packet.get("next_prompt", ""),
    }
    blob = json.dumps(slim, sort_keys=True)
    return (
        f"{base_ctx}\n\n"
        "---\n"
        "NEXT_AGENT_PACKET_JSON:\n"
        f"{blob}\n"
    )

def delegate(cli: str, task: str) -> str:
    if cli not in _DELEGATE_ORDER:
        return f"Unknown worker '{cli}'. Available: {', '.join(_DELEGATE_ORDER)}"

    # Scout before build tasks
    build_kws = ("build", "implement", "create", "write", "add", "make", "develop")
    if any(kw in task.lower() for kw in build_kws):
        scout = github_scout(task)
        if scout:
            print(f"\n[Scout] Potentially relevant:\n{scout}\n")

    packet = _delegate_packet_for_task(task)
    ctx = _delegate_context_with_packet(_worker_context(task), packet)
    cmd = _delegate_argv(cli, ctx)
    if cmd is None:
        record_builder_recommendation(
            raw_input=task,
            outcome="delegate_missing_binary",
            workers=[cli],
            commands_run=[],
            risks=["worker binary missing"],
            next_agent_packet=packet,
        )
        return (
            f"[{cli.upper()}] CLI binary not found. Install it or set the matching "
            f"KITTY_*_BIN environment variable (see `scripts/kitty_builder.py` probe)."
        )
    exe = cmd[0]
    ctx_blob = cmd[-1] if len(cmd) > 1 else ""
    preview = ctx_blob[:160].replace("\n", "\\n")
    if len(ctx_blob) > 160:
        preview += "…"
    log.info(
        "delegate start cli=%s exe=%s argc=%d ctx_chars=%d",
        cli, exe, len(cmd), len(ctx_blob),
    )
    print(
        f"\n[delegate:{cli}] REAL subprocess — executable={exe!r} argc={len(cmd)} "
        f"context_chars={len(ctx_blob)}",
        file=sys.stderr,
        flush=True,
    )
    print(f"[delegate:{cli}] context preview: {preview!r}", file=sys.stderr, flush=True)
    print(f"\n[{cli.upper()}] Launching worker…")
    pre = _git_snapshot()

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, cwd=PROJECT_ROOT)
        output_lines: list[str] = []
        try:
            for line in proc.stdout:
                print(line, end="", flush=True)
                output_lines.append(line)
        except KeyboardInterrupt:
            proc.terminate()
            print(f"\n[{cli.upper()}] Interrupted.")
            record_builder_recommendation(
                raw_input=task,
                outcome="delegate_interrupted",
                workers=[cli],
                commands_run=[cmd[0]],
                risks=["worker interrupted"],
                next_agent_packet=packet,
            )
            return "Worker interrupted." + _delegate_git_diff_stat_suffix()
        try:
            proc.wait(timeout=DELEGATE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.warning("delegate timeout cli=%s after %ss", cli, DELEGATE_TIMEOUT_SEC)
            record_builder_recommendation(
                raw_input=task,
                outcome="delegate_timeout",
                workers=[cli],
                commands_run=[cmd[0]],
                risks=[f"worker timed out after {DELEGATE_TIMEOUT_SEC:.0f}s"],
                next_agent_packet=packet,
            )
            return (
                f"[{cli.upper()}] Timed out after {DELEGATE_TIMEOUT_SEC:.0f}s — process killed."
                + _delegate_git_diff_stat_suffix()
            )

        rc = proc.returncode if proc.returncode is not None else -1
        log.info(
            "delegate done cli=%s returncode=%s stdout_lines=%s",
            cli, rc, len(output_lines),
        )
        print(
            f"[delegate:{cli}] subprocess finished returncode={rc} stdout_lines={len(output_lines)}",
            file=sys.stderr,
            flush=True,
        )

        # Track Claude cost from JSON output
        if cli == "claude":
            raw = "".join(output_lines)
            m = re.search(r'"total_cost_usd":\s*([\d.]+)', raw)
            if m:
                budget.record_claude(float(m.group(1)))

        changed = _git_snapshot() - pre
        if rc != 0:
            summary = f"[{cli.upper()}] FAILED (exit code {rc})."
        else:
            summary = f"[{cli.upper()}] Done (exit {rc})."
        if changed:
            summary += f" Changed: {', '.join(sorted(changed)[:5])}"
        record_builder_recommendation(
            raw_input=task,
            outcome="delegate_success" if rc == 0 else "delegate_failed",
            workers=[cli],
            commands_run=[" ".join(cmd[:2]) if len(cmd) >= 2 else cmd[0]],
            risks=[] if rc == 0 else [f"worker exit code {rc}"],
            next_agent_packet=packet,
        )
        budget.save()
        return summary + _delegate_git_diff_stat_suffix()
    except FileNotFoundError:
        record_builder_recommendation(
            raw_input=task,
            outcome="delegate_not_found",
            workers=[cli],
            commands_run=[],
            risks=["worker executable not found"],
            next_agent_packet=packet,
        )
        return f"[{cli.upper()}] Not found — check installation."
    except Exception as e:
        record_builder_recommendation(
            raw_input=task,
            outcome="delegate_error",
            workers=[cli],
            commands_run=[],
            risks=[str(e)],
            next_agent_packet=packet,
        )
        return f"[{cli.upper()}] Error: {e}"

# ------------------------------------------------------------
# GITHUB SCOUT — find existing tools before writing from scratch
# ------------------------------------------------------------
def github_scout(task: str) -> str:
    query = f"site:github.com {task[:120]} open source tool"
    return search_web(query)

# Register new tools after delegate/github_scout are defined
TOOLS["delegate"] = delegate
TOOLS["github_scout"] = github_scout

# ------------------------------------------------------------
# STARTUP PROBE — verify each tier before accepting input
# ------------------------------------------------------------
def probe_tools() -> dict:
    log.info("Probing available tools…")
    print("[Startup] Probing available tools…")
    status: dict[str, str] = {}

    if _groq_client:
        try:
            budget.assert_groq_request_allowed()
        except BudgetExhausted as e:
            status["groq"] = f"⚠️ Groq capped: {e}"
        else:
            try:
                _groq_client.chat.completions.create(
                    model=GROQ_MODEL, messages=[{"role": "user", "content": "ok"}], max_tokens=3
                )
                status["groq"] = f"✅ Groq {GROQ_MODEL}"
                budget.record_groq()
            except Exception as e:
                status["groq"] = f"❌ Groq: {str(e)[:60]}"
    elif _GROQ_DISABLED and GROQ_API_KEY:
        status["groq"] = "⚠️ Groq off (KITTY_BUILDER_DISABLE_GROQ=1)"
    else:
        status["groq"] = "⚠️ Groq: no GROQ_API_KEY"

    bh = str(Path.home() / ".local/bin")
    for name, env_key, default in (
        ("claude", "KITTY_CLAUDE_BIN", "/opt/homebrew/bin/claude"),
        ("gemini", "KITTY_GEMINI_BIN", "/opt/homebrew/bin/gemini"),
        ("agent", "KITTY_AGENT_BIN", f"{bh}/agent"),
    ):
        exe = _resolve_tool_bin(env_key, default)
        if not exe:
            status[name] = f"❌ {name}: not found (set {env_key} or install)"
            continue
        try:
            r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5)
            status[name] = f"✅ {name} ({Path(exe).name}) {r.stdout.strip()[:30]}"
        except Exception as e:
            status[name] = f"❌ {name}: {e}"

    if OPENROUTER_API_KEY:
        try:
            import requests as _req
            r = _req.get("https://openrouter.ai/api/v1/key",
                         headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, timeout=5)
            if r.status_code == 200:
                used = r.json().get("data", {}).get("usage", 0)
                status["openrouter"] = f"✅ OpenRouter (${used:.2f} used today)"
            else:
                status["openrouter"] = f"⚠️  OpenRouter: HTTP {r.status_code}"
        except Exception:
            status["openrouter"] = "⚠️  OpenRouter: probe failed"

    for v in status.values():
        print(f"  {v}")
    print(f"  Budget: {budget.summary()}\n")
    return status

# ------------------------------------------------------------
# STANDUP WRITER — appends session entry on exit
# ------------------------------------------------------------
def write_standup_entry(summary: str):
    standup = PROJECT_ROOT / "docs" / "STANDUP.md"
    try:
        git_status = subprocess.run(["git", "status", "--short"], capture_output=True,
                                    text=True, cwd=PROJECT_ROOT, timeout=5).stdout.strip()
        if summary.strip() == "Session (no actions logged)." and not git_status:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n\n---\n## KittyBuilder — {now}\n\n{summary}\n"
        if git_status:
            entry += f"\n**Dirty tree:**\n```\n{git_status[:400]}\n```\n"
        entry += f"\n**Budget:** {budget.summary()}\n"
        KITTYBUILDER_SESSION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(KITTYBUILDER_SESSION_LOG, "a") as f:
            f.write(entry)
        if APPEND_STANDUP and standup.exists():
            thin = (
                f"\n\n---\n## KittyBuilder — {now}\n\n{summary}\n"
                f"\n**Budget:** {budget.summary()}\n"
                f"\n**Session log:** `docs/handoffs/kittybuilder-session-log.md`\n"
            )
            with open(standup, "a") as f:
                f.write(thin)
            print("[Standup] Entry written to docs/STANDUP.md (append enabled)")
        else:
            print("[Standup] Session log written to docs/handoffs/kittybuilder-session-log.md")
    except Exception as e:
        print(f"[Standup] Write failed: {e}")

# ------------------------------------------------------------
# CORE MODES
# ------------------------------------------------------------
def council(question: str):
    """Run two independent reasoning passes then synthesize — single model, two prompts."""
    print("\n--- Council Deliberation ---")
    opinions = []
    for name, framing in [
        ("Pragmatist", "You are a pragmatic engineer focused on what works right now. Be direct and brief."),
        ("Critic",     "You are a critical reviewer focused on risks, edge cases, and flaws. Be direct and brief."),
    ]:
        print(f"[{name}] Thinking...")
        try:
            if USE_OPENROUTER and OPENROUTER_API_KEY:
                resp = call_openrouter(
                    [{"role": "system", "content": framing},
                     {"role": "user", "content": question}],
                    max_tokens=200, temperature=0.7,
                )
            else:
                model, tok = get_model(MODEL_BUILDER, force_local=True)
                sampler = make_sampler(temp=0.7)
                messages = [{"role": "system", "content": framing}, {"role": "user", "content": question}]
                resp = generate(model, tok, prompt=_build_prompt(tok, messages),
                                max_tokens=200, sampler=sampler)
            opinions.append(f"{name}: {resp.strip()}")
        except BuilderError as e:
            print(f"[Error in {name}: {e.code} — {e}]")
            opinions.append(f"{name}: [Error - {e.code}: {e}]")
        except Exception as e:
            print(f"[Error in {name}: {e}]")
            opinions.append(f"{name}: [Error - {e}]")

    print("[Chairman] Synthesizing...")
    synth_text = (
        f"Synthesize these two perspectives on: {question!r}\n\n"
        + "\n\n".join(opinions)
        + "\n\nGive a final recommendation in 2-3 sentences."
    )
    try:
        if USE_OPENROUTER and OPENROUTER_API_KEY:
            final = call_openrouter(
                [{"role": "user", "content": synth_text}],
                max_tokens=300, temperature=0.7,
            )
        else:
            model, tok = get_model(MODEL_BUILDER, force_local=True)
            sampler = make_sampler(temp=0.7)
            synth_msg = [{"role": "user", "content": synth_text}]
            final = generate(model, tok, prompt=_build_prompt(tok, synth_msg),
                             max_tokens=300, sampler=sampler)
        print(f"\nFinal Verdict:\n{final}\n")
    except BuilderError as e:
        print(f"\n[Synthesis Error: {e.code} — {e}]")
        print("Opinions gathered:")
        for o in opinions:
            print(o)
    except Exception as e:
        print(f"\n[Synthesis Error: {e}]")
        print("Opinions gathered:")
        for o in opinions:
            print(o)

def self_review():
    print("\n" + "="*40 + "\nKITTY SELF-AUDIT FOR JACOB\n" + "="*40)

    import subprocess

    # Run real analysis instead of just feeding truncated code to LLM
    print("\n[1/4] Running code analysis...")
    findings = []

    # Check for generic error/exception patterns that swallow issues
    bare_excepts = subprocess.run(
        ["rg", "-n", "except:\\s*$|except\\s+Exception\\s*:\\s*pass", "--include", "*.py", "-l"],
        capture_output=True, text=True, timeout=30
    ).stdout.strip().split("\n")
    if bare_excepts and bare_excepts[0]:
        findings.append(f"Bare except/pass found in: {bare_excepts[:5]}")

    # Check for stale root-level files
    stale = []
    for f in PROJECT_ROOT.iterdir():
        if f.is_file() and f.name in ("CURRENT_PROJECT_STATE.json",):
            stale.append(f.name)
    if stale:
        findings.append(f"Stale root files: {stale}")

    # Check for duplicate code patterns
    if (PROJECT_ROOT / "model_loader.py").exists() and (PROJECT_ROOT / "model_preloader.py").exists():
        findings.append("model_loader.py and model_preloader.py overlap in purpose")

    # Check test count vs source files
    src_files = len(list(PROJECT_ROOT.rglob("src/**/*.py")))
    test_files = len(list(PROJECT_ROOT.rglob("tests/**/test_*.py")))
    if test_files < src_files * 0.3:
        findings.append(f"Low test ratio: {test_files} tests for {src_files} source files")

    # Check import issues
    unused_imports = subprocess.run(
        ["rg", "-n", "import\\s+socket", "web.py"],
        capture_output=True, text=True, timeout=10
    ).stdout.strip()

    if findings:
        print("\nFindings:")
        for f in findings:
            print(f"  ⚠ {f}")
    else:
        print("  No issues found via static analysis")

    # Now ask LLM for deeper review (only key files, not truncated)
    print("\n[2/4] Reading key files for LLM review...")
    key_files = [
        "web.py", "scripts/kitty_builder.py", "kitty_v2.py",
        "model_preloader.py", "model_loader.py",
        "src/space_kitty/llm_client.py", "src/core/specialist_framework.py",
    ]

    code_samples = []
    for fname in key_files:
        fpath = PROJECT_ROOT / fname
        if fpath.exists():
            code_samples.append(f"\n# --- {fname} (full) ---\n{fpath.read_text()[:6000]}")

    all_code = "\n".join(code_samples)
    print(f"  Loaded {len(key_files)} key files ({len(all_code)} chars)")

    prompt = f"""Review these key files for REAL bugs, security issues, and logic flaws.
IMPORTANT: Files are complete (not truncated). Only report actual bugs, not style issues.
For each finding, give: file, line, severity (HIGH/MED/LOW), and the fix.

{all_code}"""

    print("\n[3/4] Running LLM review...")
    if USE_OPENROUTER and OPENROUTER_API_KEY:
        report = generate_openrouter(prompt, max_tokens=1000, temp=0.2)
    else:
        model, tok = get_model(MODEL_CODE, force_local=True)
        messages = [{"role": "user", "content": prompt}]
        report = generate(model, tok, prompt=_build_prompt(tok, messages),
                          max_tokens=1000, sampler=make_sampler(temp=0.2))

    print("\n" + "="*40)
    print("LLM REVIEW FINDINGS")
    print("="*40)
    print(report)

    print("\n[4/4] Static analysis findings summary:")
    for f in findings:
        print(f"  ⚠ {f}")

# ------------------------------------------------------------
# AGENT LOGIC
# ------------------------------------------------------------
SYSTEM_PROMPT = """You are KittyBuilder, Jacob's AI Project Manager and Builder.
You manage the Kitty AI Router project in: {root}

Your job is to:
1. Know the current project state (progress, tasks, milestones)
2. Start every work session by loading the Layer 0 control plane and dirty-tree state
3. Track what's done vs remaining
4. Route architecture/review decisions to the CTO agent rather than making them silently
5. Launch tools to execute approved plans
6. Give Jacob honest estimates of progress

--- TOOLS AVAILABLE ---
- builder_session_start() - Session opener: git snapshot, CURRENT_FOCUS line, budget, recommended next steps (call when Jacob starts work)
- run_project_gates() - Run scripts/run_gates.sh; returns PASS/FAIL headline plus log tail — use before claiming tests/gates are green
- run_command(command) - Execute safe shell commands
- read_file(path) - Read any project file
- write_file(path, content) - Create/update files
- modify_project_tasks(action, milestone_id, task, note, title) - Manage tasks
- search_web(query) - Search the web
- launch_kitty() - Run pytest on tests/
- generate_project_brief() - Refresh your knowledge of project state
- get_builder_budget() - **Spend questions:** today's recorded ledger (Groq / OpenRouter / Claude CLI) — call this instead of guessing dollars
- delegate(cli, task) - Stream a coding task to a CLI worker (cli: claude, gemini, opencode, aider, crush, agent, goose)
- github_scout(task) - Search GitHub for existing tools before building from scratch

--- HOW YOU OPERATE ---
1. You ALWAYS know the full project state - use generate_project_brief() at session start
2. When Jacob asks about progress, give specific numbers (% complete, tasks remaining)
3. When Jacob starts work, identify the current control plane, dirty files, and the next gated action
4. When a decision needs architecture judgment, prepare a concise CTO handoff instead of burying it
5. When Jacob wants to proceed, suggest specific next steps and offer to execute
6. If something is unclear, ask clarifying questions

--- HONESTY — COSTS, DELEGATION, PARALLEL TASKS (NON-NEGOTIABLE) ---
- Never invent dollar amounts, hourly rates, project budgets, or "total incurred costs." You do not see Jacob's subscriptions or invoices.
- Recorded spend in *this* app is only what the BudgetManager tracks. When Jacob asks about money, caps, or "what did we spend", **call `get_builder_budget()`** (tool JSON) so the answer is grounded. You may also tell him he can type **`/budget`** in this REPL for the same snapshot.
- Do not estimate or annualize costs. If the ledger is empty/zero, say so plainly.
- Never narrate fake CLI outcomes ("Crush accepted…", "Goose will benchmark…") unless you are **quoting verbatim output** from an actual `delegate()` tool result shown in this conversation. If delegation was not executed, say so and offer to call `delegate` with real JSON.
- Real runs print **`[delegate:<cli>]`** lines to **stderr** when the subprocess starts/finishes — if Jacob does not see those, delegation did not run in this terminal.
- Do not invent numbered parallel tasks (Task 1–N), fake assignees (claude/gemini/…), or imaginary percent-complete bars unless they match **project state below** or a tool you just ran. Prefer reading `project.json` / brief over storytelling.

{scope}
--- PROJECT STATE ---
{project}
"""

def _build_prompt(tok, messages: list[dict], thinking: bool = False) -> str:
    """Apply Qwen3 chat template; gracefully degrades if enable_thinking unsupported."""
    try:
        return tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=thinking,
        )
    except TypeError:
        return tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )


def _format_project(proj: dict) -> str:
    p = proj.get("progress", {})
    lines = [
        f"Name: {proj.get('project_name', '')}",
        f"Progress: {p.get('task_completion_pct', 0)}% tasks, {p.get('milestone_completion_pct', 0)}% milestones",
        f"Remaining: {p.get('remaining_tasks', 0)} tasks, {p.get('open_todos', 0)} TODOs",
    ]

    for m in proj.get('milestones', []):
        lines.append(f"\nMilestone [{m.get('id')}]: {m.get('title')} [{m.get('status')}]")
        for t in m.get("tasks", []):
            lines.append(f"  → {t}")
        for t in m.get("done_tasks", []):
            lines.append(f"  ✓ {t}")

    lines.append(f"\nBacklog ({len(proj.get('backlog', []))} items):")
    for b in proj.get("backlog", [])[:5]:
        lines.append(f"  - {b}")
    if len(proj.get("backlog", [])) > 5:
        lines.append(f"  ... and {len(proj.get('backlog', [])) - 5} more")

    # Git info
    if proj.get("git_info", {}).get("status"):
        lines.append(f"\nGit: {proj['git_info']['status'][:200]}")

    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    """Extract first JSON object from LLM response.

    Uses json.JSONDecoder to track nesting depth correctly — closing braces
    inside quoted strings are handled automatically by the JSON parser.

    Tries multiple patterns:
    1. ```json ... ``` block
    2. ``` ... ``` any code block
    3. Raw JSON-like text starting with {
    """
    # Pattern 1: JSON code block
    block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if block:
        raw = block.group(1)
    else:
        # Pattern 2: Any code block
        block = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        raw = block.group(1) if block else text

    # Find JSON start
    start = raw.find('{')
    if start == -1:
        return None

    try:
        decoder = json.JSONDecoder()
        obj, end = decoder.raw_decode(raw[start:])
        return obj
    except json.JSONDecodeError:
        return None


# ── Model-stats sink (MCP-ready JSONL) ───────────────────────────────────────
#
# Writes per-flush observations of free-pool model health. Each row is shaped
# as an MCP memory-server "entity observation" so a future ingester can push
# them into @modelcontextprotocol/server-memory without re-shaping. Per
# CLAUDE.md storage routing, this is the right home for "lessons learned"
# about which models work — JournalDB is for journal entries, LightRAG is for
# KB content; model-performance metadata is MCP entity territory.

MODEL_STATS_FILE = PROJECT_ROOT / ".kitty_builder_model_stats.jsonl"


def flush_model_stats() -> None:
    """Append one observation row per known free-pool model. Best-effort."""
    stats = free_pool.stats()
    if not stats:
        return
    now_iso = datetime.now().isoformat(timespec="seconds")
    rows = []
    cooldowns = dict(free_pool._cooldowns)
    now = time.time()
    for model, sv in stats.items():
        ok = int(sv.get("ok", 0))
        fail = int(sv.get("fail", 0))
        total = ok + fail
        rate = (ok / total) if total else None
        cooldown_s = max(0.0, cooldowns.get(model, 0.0) - now)
        rows.append({
            "ts": now_iso,
            "entity_type": "openrouter_model",
            "name": model,
            "observations": [
                {"ok": ok, "fail": fail, "success_rate": rate,
                 "cooldown_remaining_s": round(cooldown_s, 1)},
            ],
        })
    try:
        with open(MODEL_STATS_FILE, "a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    except OSError as e:
        print(f"[ModelStats] write failed: {e}", file=sys.stderr)


# ── Optional LightRAG KB query (opt-in) ──────────────────────────────────────
#
# Per CLAUDE.md routing, KB queries go to LightRAG. We import lazily so the
# builder still runs when LightRAG service / deps are absent.

USE_LIGHTRAG = os.environ.get("KITTY_BUILDER_USE_LIGHTRAG", "0").strip() == "1"
_lightrag_wrapper = None


def _get_lightrag():
    global _lightrag_wrapper
    if _lightrag_wrapper is not None:
        return _lightrag_wrapper
    if not USE_LIGHTRAG:
        return None
    try:
        from src.tools.lightrag_wrapper import LightRAGWrapper
        _lightrag_wrapper = LightRAGWrapper()
        return _lightrag_wrapper
    except Exception as e:
        print(f"[LightRAG] init failed: {e} — disabling kb_query", file=sys.stderr)
        return None


def kb_query(query: str, top_k: int = 5) -> str:
    """Query the LightRAG KB. Opt-in via KITTY_BUILDER_USE_LIGHTRAG=1."""
    if not USE_LIGHTRAG:
        return "Error: LightRAG disabled (set KITTY_BUILDER_USE_LIGHTRAG=1 to enable)."
    lr = _get_lightrag()
    if lr is None:
        return "Error: LightRAG unavailable (init failed)."
    try:
        results = lr.search(query, top_k=top_k)
    except Exception as e:
        return f"Error: LightRAG search failed: {e}"
    if not results:
        return "No KB results."
    if isinstance(results, str):
        return results[:4000]
    if isinstance(results, list):
        return "\n".join(str(r)[:500] for r in results[:top_k])
    return str(results)[:4000]


# Register kb_query as a tool the agent can call (no-op call still safe when disabled).
TOOLS["kb_query"] = kb_query


# ── Prompt cache (opt-in, off by default) ────────────────────────────────────

CACHE_FILE = PROJECT_ROOT / ".kitty_builder_cache.sqlite3"


class PromptCache:
    """Tiny SQLite cache keyed by sha256 of (model + messages + kwargs).

    Disabled unless env KITTY_BUILDER_CACHE=1. Only useful for deterministic
    (low-temp) calls — random sampling poisons the cache for everyone else.
    """

    def __init__(self, path: Path, enabled: bool) -> None:
        self.enabled = enabled
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        if not enabled:
            return
        try:
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS responses "
                "(key TEXT PRIMARY KEY, response TEXT, ts REAL)"
            )
            self._conn.commit()
        except sqlite3.Error as e:
            print(f"[Cache] init failed: {e}", file=sys.stderr)
            self.enabled = False

    @staticmethod
    def make_key(model: str, messages: list, **kw) -> str:
        h = hashlib.sha256()
        h.update(model.encode("utf-8"))
        h.update(json.dumps(messages, sort_keys=True).encode("utf-8"))
        for k in sorted(kw):
            h.update(f"{k}={kw[k]}".encode("utf-8"))
        return h.hexdigest()

    def get(self, key: str) -> Optional[str]:
        if not self.enabled or self._conn is None:
            return None
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT response FROM responses WHERE key=?", (key,)
                ).fetchone()
            except sqlite3.Error as e:
                print(f"[Cache] get failed: {e}", file=sys.stderr)
                return None
        return row[0] if row else None

    def put(self, key: str, response: str) -> None:
        if not self.enabled or self._conn is None:
            return
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO responses (key, response, ts) VALUES (?, ?, ?)",
                    (key, response, time.time()),
                )
                self._conn.commit()
            except sqlite3.Error as e:
                print(f"[Cache] put failed: {e}", file=sys.stderr)

    def stats(self) -> Dict[str, int]:
        if not self.enabled or self._conn is None:
            return {"enabled": 0, "rows": 0}
        with self._lock:
            try:
                row = self._conn.execute("SELECT COUNT(*) FROM responses").fetchone()
            except sqlite3.Error:
                return {"enabled": 1, "rows": -1}
        return {"enabled": 1, "rows": int(row[0])}


prompt_cache = PromptCache(
    CACHE_FILE,
    enabled=os.environ.get("KITTY_BUILDER_CACHE", "0").strip() == "1",
)


# ── Tool execution & optimize loop ───────────────────────────────────────────

_TOOL_ERROR_PATTERNS = (
    re.compile(r"^\s*Error[: ]", re.IGNORECASE),
    re.compile(r"\bSecurity scan blocked\b", re.IGNORECASE),
    re.compile(r"\bCommand exited with code [1-9]", re.IGNORECASE),
    re.compile(r"\b(failed|traceback)\b", re.IGNORECASE),
)


def _looks_like_failure(result: object) -> bool:
    if not isinstance(result, str):
        return False
    head = result[:300]
    return any(p.search(head) for p in _TOOL_ERROR_PATTERNS)


def _execute_tool_call(data: dict) -> tuple[bool, str]:
    """Run a tool referenced in extracted JSON. Returns (succeeded, result_text)."""
    tool = data.get("tool")
    args = data.get("args", {})
    if tool not in TOOLS:
        return False, f"Error: Tool '{tool}' not found."
    if PLAN_ONLY_MODE and tool in PLAN_ONLY_BLOCKED_TOOLS:
        return False, (
            f"Error: Tool '{tool}' is blocked in plan-only mode "
            f"(restart without --plan-only / KITTY_BUILDER_PLAN_ONLY)."
        )
    log.info("Executing tool: %s", tool)
    try:
        result = TOOLS[tool](**args) if isinstance(args, dict) else TOOLS[tool](args)
    except Exception as e:
        return False, f"Error executing tool {tool}: {e}"
    text = result if isinstance(result, str) else str(result)
    return (not _looks_like_failure(text)), text


def _check_goal(verify_cmd: str) -> tuple[bool, str]:
    """Run the goal verification command (e.g. 'pytest tests/test_x.py -q'). Sandboxed."""
    if not sanitize_command(verify_cmd):
        return False, f"goal verify command rejected by sanitize_command: {verify_cmd}"
    try:
        proc = subprocess.run(
            shlex.split(verify_cmd),
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120,
        )
    except (subprocess.SubprocessError, OSError) as e:
        return False, f"goal verify failed to run: {e}"
    tail = (proc.stdout + proc.stderr)[-400:]
    return proc.returncode == 0, tail


def chat(user_input: str, *, max_iters: int = 1) -> str:
    """Single-turn chat. With max_iters>1, retries on tool failure (optimize loop).

    The optimize loop appends the failure context to the conversation and asks
    Kitty to try again, up to max_iters total assistant turns. A goal verifier
    set via /goal will be run after each successful tool execution and, if it
    passes, ends the loop early.
    """
    sys_msg = SYSTEM_PROMPT.format(
        root=PROJECT_ROOT,
        project=_format_project(session.project_state),
        scope=_builder_scope_block(session.project_state),
    )

    if not session.history:
        session.history.append({"role": "system", "content": sys_msg})
    else:
        session.history[0]["content"] = sys_msg

    session.history.append({"role": "user", "content": user_input})
    _apply_history_cap(session.history, HISTORY_MAX_MESSAGES)

    last_response = ""
    for iter_no in range(1, max(1, max_iters) + 1):
        try:
            if iter_no == 1:
                print("[Kitty] ", end="", flush=True)
            else:
                print(f"\n[Kitty iter {iter_no}/{max_iters}] ", end="", flush=True)
            last_response = _stream_brain(session.history)
            session.history.append({"role": "assistant", "content": last_response})

            data = _extract_json(last_response)
            if data is None or "tool" not in data:
                # No tool call — nothing to retry. Done.
                break

            ok, result = _execute_tool_call(data)
            print(f"[Tool Result] {result[:1000]}{'…' if len(result) > 1000 else ''}")
            session.history.append({
                "role": "system",
                "content": f"Tool '{data.get('tool')}' executed (success={ok}). Result:\n{result}",
            })

            # Goal check after every successful tool execution
            verify = session.project_state.get("goal_verify") if isinstance(session.project_state, dict) else None
            if ok and verify:
                goal_ok, tail = _check_goal(verify)
                if goal_ok:
                    msg = f"[Goal achieved via `{verify}`]"
                    print(msg)
                    session.history.append({"role": "system", "content": msg})
                    if isinstance(session.project_state, dict):
                        session.project_state.pop("goal_verify", None)
                    break
                else:
                    # Tool succeeded but goal still failing — feed the error back as context
                    msg = (f"Goal verifier `{verify}` still failing.\n"
                           f"Last 400 chars of output:\n{tail}\n"
                           f"Try a different approach.")
                    session.history.append({"role": "system", "content": msg})
                    # continue iterating
                    continue

            if ok:
                # Tool succeeded and no goal set — we're done.
                break
            if iter_no >= max_iters:
                break
            # Tool failed; nudge Kitty to fix it
            session.history.append({
                "role": "system",
                "content": (
                    f"The previous tool call failed. Diagnose the failure from the "
                    f"result above and try a different approach. You have "
                    f"{max_iters - iter_no} attempt(s) left."
                ),
            })
        finally:
            _apply_history_cap(session.history, HISTORY_MAX_MESSAGES)

    return last_response

def show_models():
    print("\n--- Active Models ---")
    if USE_OPENROUTER and OPENROUTER_API_KEY:
        print(f"  Provider: OpenRouter")
        if OPENROUTER_MODEL_OVERRIDE:
            print(f"  Override: {OPENROUTER_MODEL_OVERRIDE}")
        else:
            now = time.time()
            models = free_pool.all_models()
            cooling = {m: ts for m, ts in free_pool._cooldowns.items() if ts > now}
            print(f"  Free pool ({len(models)} models, {len(cooling)} cooling):")
            for m in models:
                ts = cooling.get(m)
                tag = f" [cool {ts - now:.0f}s]" if ts else ""
                stats = free_pool.stats().get(m, {})
                ok, fail = stats.get("ok", 0), stats.get("fail", 0)
                print(f"    - {m}{tag}  (ok={ok} fail={fail})")
            if OPENROUTER_PAID_FALLBACK:
                print(f"  Paid fallback: {OPENROUTER_PAID_FALLBACK}")
    else:
        print(f"  All roles: {MODEL_BUILDER}")
    loaded = list(_model_cache.keys())
    if loaded:
        print(f"\nCurrently loaded in VRAM: {loaded[0]}")
    else:
        print("\nNo models currently in VRAM.")


def show_help():
    delegate_list = " | ".join(_DELEGATE_ORDER)
    brain_default = ",".join(_DEFAULT_BRAIN_ORDER)
    print(
        "\n--- Kitty Builder V3 Commands ---\n"
        "  /start                   Session opener: git + CURRENT_FOCUS + budget + next steps\n"
        "  /spec <path>             Latch an approved spec file for this session (stay-in-scope hint)\n"
        "  /spec show             Show latched spec path\n"
        "  /spec clear            Clear latched spec\n"
        "  /policy                 Show active orchestrator policy (tiers, delegate order, budgets)\n"
        "  /help                    Show this help\n"
        "  /health                  Scan project health\n"
        "  /next                    Suggest next steps\n"
        "  /budget / budget        REAL ledger (Groq/OR/Claude CLI caps) — same data as get_builder_budget()\n"
        "  /tokens                 Today's token telemetry summary from data/kitty_token_log.jsonl\n"
        "  /compile <request>      Compile raw request into a structured BuilderBrief (read-only)\n"
        "  /workers                Check delegate worker binary health (read-only)\n"
        "  /probe                   Re-probe all tools / auth status\n"
        "  /test  /gates            Run scripts/run_gates.sh (tests)\n"
        "  /delegate <cli> <task>   Stream task to CLI worker\n"
        f"                           cli: {delegate_list}\n"
        "  /scout <query>           Search GitHub for existing tools first\n"
        "  /improve                 Self-improvement: test, audit, grade, feedback\n"
        "  /models                  Show active Brain model and VRAM state\n"
        "  /council <q>             Two-perspective deliberation on a question\n"
        "  /selfreview              Code audit across the project\n"
        "  /patterns                List available text patterns\n"
        "  /freepool                Show free-model pool + cooldowns + stats\n"
        "  /goal <verify-cmd>       Set goal verifier (e.g. `/goal pytest tests/test_x.py -q`)\n"
        "  /goal clear              Clear current goal\n"
        "  /optimize <prompt>       Multi-iteration chat (retry on tool failure, up to 3)\n"
        "  /race <prompt>           Race two free models in parallel; first valid wins\n"
        "  /cache                   Prompt-cache stats (set KITTY_BUILDER_CACHE=1 to enable)\n"
        "  /stats                   Flush per-model stats to .kitty_builder_model_stats.jsonl\n"
        "  /kb <query>              Query LightRAG KB (needs KITTY_BUILDER_USE_LIGHTRAG=1)\n"
        "  /exit                    Quit + write standup entry\n"
        "\nCLI flags: --plan-only (or KITTY_BUILDER_PLAN_ONLY=1) for read-only interactive sessions.\n"
        "Env: KITTY_*_BIN for worker paths, KITTY_BUILDER_DELEGATE_TIMEOUT_SEC, KITTY_BUILDER_HISTORY_MAX; "
        "KITTY_BUILDER_DELEGATE_DIFF=0 disables git diff --stat after delegate.\n"
        f"Brain: KITTY_BUILDER_BRAIN_ORDER={brain_default} (default/policy). Put mlx first for local-first; "
        "use groq,openrouter,mlx only if Groq is stable for you.\n"
        "Groq: set KITTY_BUILDER_DISABLE_GROQ=1 to skip Groq (no probe spam) while keeping GROQ_API_KEY.\n"
        "Budget: KITTY_BUDGET_OR_ESTIMATE_USD (preflight per paid OpenRouter call, default 0.002); "
        "KITTY_BUDGET_GROQ_MAX_REQUESTS (optional daily Groq cap, 0=unlimited).\n"
        "\nBrain tiers (default order): OpenRouter → local MLX → Groq (last)\n"
        "Free pool rotates on 429/503. Set OPENROUTER_FREE_MODELS or OPENROUTER_PAID_FALLBACK to customize.\n"
        f"Workers priority order: {' → '.join(_DELEGATE_ORDER)}\n"
        f"Policy file: {POLICY_FILE}\n"
    )

# ------------------------------------------------------------
# BUILDER CONTRACT
# ------------------------------------------------------------
def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Controlled Kitty builder entrypoint. Dry-run is the default.",
    )
    parser.add_argument("--brief", action="store_true", help="Print a read-only project manager brief for session start.")
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Launch the legacy interactive builder (otherwise --project/--spec or --brief is required).",
    )
    parser.add_argument("--plan-only", action="store_true",
                        help="Interactive mode only: block write/run/delegate/shell tools (read-only planning). "
                             "Or set KITTY_BUILDER_PLAN_ONLY=1.")
    parser.add_argument("--project", type=Path, help="Path to the Kitty app checkout.")
    parser.add_argument("--spec", type=Path, help="Path to the approved spec markdown file.")
    parser.add_argument("--execute", action="store_true", help="Allow future write-capable builder execution.")
    parser.add_argument("--dry-run", action="store_true", help="Print contract checks only. This is the default.")
    return parser


def validate_builder_contract(project: Path, spec: Path) -> list[str]:
    errors: list[str] = []
    project = project.expanduser().resolve()
    spec = spec.expanduser()
    spec_path = spec if spec.is_absolute() else project / spec
    spec_path = spec_path.resolve()

    if not project.exists() or not project.is_dir():
        errors.append(f"Project path does not exist or is not a directory: {project}")
    if not spec_path.exists() or not spec_path.is_file():
        errors.append(f"Spec path does not exist or is not a file: {spec_path}")
    try:
        spec_path.relative_to(project)
    except ValueError:
        errors.append(f"Spec path must live inside the project: {spec_path}")
    return errors


def run_builder_contract(project: Path, spec: Path, *, execute: bool = False) -> int:
    project = project.expanduser().resolve()
    spec_path = spec.expanduser()
    if not spec_path.is_absolute():
        spec_path = project / spec_path
    spec_path = spec_path.resolve()

    errors = validate_builder_contract(project, spec_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    mode = "execute" if execute else "dry-run"
    print("Kitty Builder Contract")
    print(f"Mode: {mode}")
    print(f"Project: {project}")
    print(f"Spec: {spec_path}")
    print("Writes enabled: no" if not execute else "Writes enabled: gated")
    print("Completion report required:")
    print("- files read")
    print("- files changed")
    print("- commands run")
    print("- tests passed/failed")
    print("- gates passed/failed")
    print("- docs updated")
    print("- known risks")
    print("- next smallest action")
    if not execute:
        print("Dry run only. Add --execute after reviewing the spec and allowed files.")
    else:
        print("Execution gate accepted. Legacy interactive builder is not auto-launched.")
    return 0


def interactive_main(plan_only: bool = False):
    global PLAN_ONLY_MODE
    PLAN_ONLY_MODE = bool(plan_only or os.environ.get("KITTY_BUILDER_PLAN_ONLY", "0").strip() == "1")

    print("🐾 Kitty Builder V3 — Online")
    if PLAN_ONLY_MODE:
        print("📋 Plan-only mode: write/run/delegate/launch_kitty/self-improve tools are blocked.\n")

    loaded = load_session()
    if loaded:
        print("[Resumed previous session]")

    probe_tools()
    update_project_from_scan()

    session_actions: list[str] = []

    while True:
        try:
            inp = input("\nJacob > ").strip()
            if not inp:
                continue

            if inp.lower() in ("exit", "/exit", "quit", "/quit"):
                save_session()
                summary = ("Session actions:\n" +
                           "\n".join(f"- {a}" for a in session_actions[-15:])) if session_actions else "Session (no actions logged)."
                write_standup_entry(summary)
                break

            elif inp.lower() in ("/help", "help"):
                show_help()
            elif inp.lower() in ("/start", "start"):
                print(builder_session_start_brief())
                session_actions.append("session start (/start)")
            elif inp.startswith("/spec"):
                arg = inp[5:].strip()
                if not arg or arg.lower() == "show":
                    cur = (
                        (session.project_state or {}).get("builder_spec_path")
                        if isinstance(session.project_state, dict)
                        else None
                    )
                    print(f"Latched spec: {cur or '(none)'}")
                elif arg.lower() == "clear":
                    if isinstance(session.project_state, dict):
                        session.project_state.pop("builder_spec_path", None)
                    print("Spec latch cleared.")
                else:
                    raw = arg
                    candidate = Path(raw).expanduser()
                    if candidate.is_absolute():
                        try:
                            rel = candidate.resolve().relative_to(PROJECT_ROOT.resolve())
                            stored = str(rel).replace("\\", "/")
                        except ValueError:
                            print("Error: spec path must be inside the project root.")
                            continue
                    else:
                        stored = raw.replace("\\", "/").lstrip("./")
                    full = PROJECT_ROOT / stored
                    if not full.is_file():
                        print(f"Error: not a file: {stored}")
                        continue
                    if not isinstance(session.project_state, dict):
                        session.project_state = {}
                    session.project_state["builder_spec_path"] = stored
                    print(f"Latched spec: {stored}")
                    session_actions.append(f"spec latch: {stored}")
            elif inp.lower() in ("/health", "health"):
                print(scan_project_health())
            elif inp.lower() in ("/next", "next"):
                print(suggest_next_steps())
            elif inp.lower() in ("/improve", "improve"):
                print(kitty_self_improve())
            elif inp.lower() in ("/test", "/gates"):
                print("[Running test gate…]")
                result = run_trusted_bash_script("scripts/run_gates.sh")
                print(result)
                session_actions.append("ran test gate")
            elif inp.lower() in ("/budget", "budget"):
                print(f"\n{budget.summary()}")
                print(budget.per_model_summary())
            elif inp.lower() == "/tokens":
                print(get_builder_token_usage())
            elif inp.startswith("/compile "):
                print(compile_builder_request(inp.removeprefix("/compile ").strip()))
            elif inp.lower() in ("/workers", "workers"):
                print(worker_health_summary())
            elif inp.lower() == "/probe":
                probe_tools()
            elif inp.lower() == "/freepool":
                free_pool.discover()
                show_models()
            elif inp.lower() == "/cache":
                s = prompt_cache.stats()
                state = "ON" if s.get("enabled") else "OFF (set KITTY_BUILDER_CACHE=1 to enable)"
                print(f"Prompt cache {state}; rows={s.get('rows', 0)}")
            elif inp.lower() == "/stats":
                flush_model_stats()
                print(f"Flushed model stats to {MODEL_STATS_FILE.name}")
            elif inp.startswith("/kb "):
                q = inp[len("/kb "):].strip()
                print(kb_query(q))
            elif inp.startswith("/goal"):
                arg = inp[len("/goal"):].strip()
                if not arg or arg.lower() == "show":
                    cur = (session.project_state or {}).get("goal_verify") if isinstance(session.project_state, dict) else None
                    print(f"Current goal: {cur or '(none)'}")
                elif arg.lower() == "clear":
                    if isinstance(session.project_state, dict):
                        session.project_state.pop("goal_verify", None)
                    print("Goal cleared.")
                else:
                    if not isinstance(session.project_state, dict):
                        session.project_state = {}
                    session.project_state["goal_verify"] = arg
                    print(f"Goal set: `{arg}` (will run after each tool exec)")
            elif inp.startswith("/optimize "):
                prompt = inp[len("/optimize "):].strip()
                chat(prompt, max_iters=3)
                session_actions.append(f"optimize: {prompt[:60]}")
            elif inp.startswith("/race "):
                prompt = inp[len("/race "):].strip()
                try:
                    text = call_openrouter_race(
                        [{"role": "user", "content": prompt}],
                        n=2, max_tokens=800, temperature=0.5,
                    )
                    print(f"\n{text}\n")
                    session_actions.append(f"race: {prompt[:60]}")
                except BuilderError as e:
                    print(f"[Race {e.code}] {e}")
            elif inp.lower() in ("/patterns", "patterns"):
                try:
                    with open(PROJECT_ROOT / "config" / "patterns.json") as f:
                        patterns = json.load(f)
                    print("\n--- Available Patterns ---\n")
                    for name, info in patterns.items():
                        print(f"  {name}: {info['description']}")
                except (json.JSONDecodeError, OSError, KeyError) as e:
                    print(f"patterns.json unavailable: {e}")
            elif inp.startswith("/delegate "):
                parts = inp[10:].split(" ", 1)
                if len(parts) == 2:
                    cli_name, task = parts[0].strip(), parts[1].strip()
                    result = delegate(cli_name, task)
                    session_actions.append(f"delegated to {cli_name}: {task[:60]}")
                    print(result)
                else:
                    print("Usage: /delegate <cli> <task>  (cli: claude, gemini, opencode, aider, crush, agent, goose)")
            elif inp.startswith("/scout "):
                query = inp[7:].strip()
                print(f"\n[Scouting: {query}]")
                print(github_scout(query))
            elif inp.startswith("/council "):
                council(inp[9:])
            elif inp.startswith("/selfreview"):
                self_review()
            elif inp.startswith("/models"):
                show_models()
            else:
                chat(inp)
                session_actions.append(f"chat: {inp[:70]}")

        except (KeyboardInterrupt, EOFError):
            save_session()
            print("\nSession saved (interrupted).")
            break
        except Exception:
            traceback.print_exc()

    print(f"\nBudget used: {budget.summary()}")


def main(argv: list[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    if args.brief:
        print(generate_project_brief())
        return 0
    if args.interactive:
        interactive_main(plan_only=args.plan_only)
        return 0
    if args.project is None and args.spec is None:
        parser.error(
            "--project and --spec are required unless you pass --brief or --interactive."
        )
    if args.project is None or args.spec is None:
        parser.error("--project and --spec are required unless --brief or --interactive is used")
    return run_builder_contract(args.project, args.spec, execute=args.execute)


if __name__ == "__main__":
    sys.exit(main())
