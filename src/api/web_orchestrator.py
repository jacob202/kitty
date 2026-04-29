"""
Web-mode LLM orchestrator — 3-tier routing with optional reasoning layer.

Tier 1 — fast     local MLX (Qwen3.5-4B) by default; falls through to balanced on failure
Tier 2 — balanced OpenRouter free router (openrouter/free) or configured model
Tier 3 — max      OpenRouter DeepSeek-R1 (full chain-of-thought reasoning)

Reasoning toggle (any tier):
  fast      enable_thinking=True on Qwen3.5 → streams <think> as "thinking" events
  balanced  routes to deepseek/deepseek-r1-distill-qwen-7b instead of chat
  max       no-op — R1 always reasons; thinking tokens streamed as "thinking" events

SSE event types emitted to the client queue:
  token     — visible reply text
  thinking  — reasoning / chain-of-thought text (UI can collapse/dim)
  done      — signalled by caller after this returns
  error     — fatal error text
"""

import json
import logging
import os
import threading

import httpx

from src.api.shared import token_broadcaster

logger = logging.getLogger(__name__)

# ── Model identifiers ────────────────────────────────────────────────────────
_MLX_FAST  = os.environ.get("MLX_MODEL",           "mlx-community/Qwen3.5-4B-4bit")
_MLX_ENABLED = os.environ.get("KITTY_ENABLE_LOCAL_MLX", "1").lower() in {
    "1", "true", "yes", "on",
}
_FREE_ROUTER = "deepseek/deepseek-v4-flash"
_OR_BAL    = os.environ.get("KITTY_MODEL",          "deepseek/deepseek-v4-flash")
_OR_MAX    = os.environ.get("KITTY_MAX_MODEL",      "deepseek/deepseek-r1-0528")
_OR_BAL_R  = os.environ.get("KITTY_BALANCED_REASON","deepseek/deepseek-r1-distill-qwen-7b")
_ANTH_MDL  = os.environ.get("KITTY_ANTHROPIC_MODEL","claude-haiku-4-5-20251001")

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_ANTHROPIC_URL  = "https://api.anthropic.com/v1/messages"

_soul_context: str | None = None

def _get_soul() -> str:
    global _soul_context
    if _soul_context is None:
        try:
            from src.space_kitty.personality import KittyPersonality
            _soul_context = KittyPersonality().get_system_context() or ""
        except Exception:
            _soul_context = ""
    return _soul_context

def _prewarm_soul() -> None:
    """Load SOUL.md in a background thread so the first chat has no cold-start penalty."""
    try:
        import threading
        threading.Thread(target=_get_soul, daemon=True, name="soul-prewarm").start()
    except Exception:
        pass

_prewarm_soul()


def _normalize_model_target(model_target: str | None) -> str:
    if model_target in {"free", "configured", "local"}:
        return model_target
    return "free"


def _model_for_target(model_target: str | None) -> str:
    """Return the OpenRouter model ID for a given target.

    "configured" → KITTY_MODEL (paid/configured model)
    "free" / "local" / unknown → free router (local falls here when MLX failed)
    """
    target = _normalize_model_target(model_target)
    if target == "configured":
        return _OR_BAL
    return _FREE_ROUTER

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM = (
    "You are Kitty, a sharp and direct personal AI assistant. "
    "You're warm but not saccharine. You help with hardware repair (Sansui AU-7900 amplifier, "
    "Honda Ridgeline), fitness, software, research, and daily life. "
    "Your job is to reduce friction for the user. When they feel overwhelmed, give brief reassurance "
    "and one concrete next action they can do immediately. For hardware repair, lead with safety "
    "and a physically verifiable step; do not make reading a manual the whole answer unless asked. "
    "Keep responses concise and practical. No filler phrases. "
    "Never invent hardware specifications, fuse ratings, or part numbers — if unsure, say so. "
    "If you don't know something, say so directly."
)

# ── Per-client conversation history ──────────────────────────────────────────
_histories: dict[str, list[dict]] = {}
_histories_lock = threading.Lock()
_MAX_TURNS = 20


def get_history(client_id: str) -> list[dict]:
    with _histories_lock:
        return list(_histories.get(client_id, []))


def clear_history(client_id: str):
    with _histories_lock:
        _histories.pop(client_id, None)


def _append(client_id: str, role: str, content: str):
    with _histories_lock:
        h = _histories.setdefault(client_id, [])
        h.append({"role": role, "content": content})
        if len(h) > _MAX_TURNS * 2:
            _histories[client_id] = h[-(_MAX_TURNS * 2):]


# ── MLX singleton ─────────────────────────────────────────────────────────────
_mlx_model     = None
_mlx_tokenizer = None
_mlx_loaded    = False
_mlx_lock      = threading.Lock()


def _load_mlx() -> bool:
    global _mlx_model, _mlx_tokenizer, _mlx_loaded
    if _mlx_loaded:
        return _mlx_model is not None
    with _mlx_lock:
        if _mlx_loaded:
            return _mlx_model is not None
        try:
            from mlx_lm import load as _mlx_load
            logger.info("Loading MLX model: %s", _MLX_FAST)
            _mlx_model, _mlx_tokenizer = _mlx_load(_MLX_FAST)
            _mlx_loaded = True
            logger.info("MLX ready")
            return True
        except Exception as exc:
            logger.warning("MLX load failed: %s", exc)
            _mlx_loaded = True
            return False


def _stream_mlx(messages: list[dict], client_id: str, reasoning: bool) -> str:
    """Stream from local MLX model. Returns full visible reply text."""
    if not _load_mlx() or _mlx_model is None:
        raise RuntimeError("MLX model not available")

    from mlx_lm import stream_generate

    # Build prompt — Qwen3 supports enable_thinking
    try:
        prompt_text = _mlx_tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=reasoning,
        )
    except TypeError:
        # Older tokenizer — no enable_thinking param
        prompt_text = _mlx_tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    full_reply  = ""
    think_buf   = ""
    in_think    = False
    pending     = ""   # accumulates partial tag chars

    for response in stream_generate(_mlx_model, _mlx_tokenizer,
                                    prompt=prompt_text, max_tokens=2048):
        chunk = response.text if hasattr(response, "text") else str(response)
        if not chunk:
            continue

        pending += chunk

        # State machine: route tokens to "thinking" or "token" events
        while pending:
            if in_think:
                end = pending.find("</think>")
                if end == -1:
                    # Still inside think block — flush as thinking
                    token_broadcaster.put_for(client_id, "thinking", pending)
                    think_buf += pending
                    pending = ""
                else:
                    # Close tag found
                    think_chunk = pending[:end]
                    if think_chunk:
                        token_broadcaster.put_for(client_id, "thinking", think_chunk)
                        think_buf += think_chunk
                    pending = pending[end + len("</think>"):]
                    in_think = False
            else:
                start = pending.find("<think>")
                if start == -1:
                    # No think tag — emit as reply
                    token_broadcaster.put_for(client_id, "token", pending)
                    full_reply += pending
                    pending = ""
                else:
                    # Normal text before the tag
                    before = pending[:start]
                    if before:
                        token_broadcaster.put_for(client_id, "token", before)
                        full_reply += before
                    pending = pending[start + len("<think>"):]
                    in_think = True

    return full_reply


# ── OpenRouter streaming ──────────────────────────────────────────────────────

def _stream_openrouter(messages: list[dict], client_id: str, model: str,
                       reasoning: bool) -> str:
    """Stream from OpenRouter. Handles R1 reasoning_content field."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://kitty.local",
        "X-Title": "Kitty",
    }
    body: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
    }
    # Qwen3 models support explicit reasoning toggle
    if reasoning and "qwen3" in model.lower():
        body["reasoning"] = {"enabled": True}

    full_reply = ""

    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", _OPENROUTER_URL,
                           headers=headers, json=body) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data   = json.loads(chunk)
                    delta  = data["choices"][0]["delta"]

                    # DeepSeek-R1 streams reasoning in a separate field
                    think = delta.get("reasoning_content") or delta.get("thinking", "")
                    if think:
                        token_broadcaster.put_for(client_id, "thinking", think)

                    text = delta.get("content", "")
                    if text:
                        full_reply += text
                        token_broadcaster.put_for(client_id, "token", text)

                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

    return full_reply


# ── Anthropic fallback ────────────────────────────────────────────────────────

def _stream_anthropic(messages: list[dict], client_id: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    anth_msgs = [m for m in messages if m["role"] != "system"]
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": _ANTH_MDL,
        "system": _SYSTEM,
        "messages": anth_msgs,
        "max_tokens": 2048,
        "stream": True,
    }
    full = ""
    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", _ANTHROPIC_URL,
                           headers=headers, json=body) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                    if data.get("type") == "content_block_delta":
                        delta = data["delta"].get("text", "")
                        if delta:
                            full += delta
                            token_broadcaster.put_for(client_id, "token", delta)
                except (json.JSONDecodeError, KeyError):
                    pass
    return full


# ── Public interface ──────────────────────────────────────────────────────────

def stream_response(
    query: str,
    client_id: str,
    mode: str = "fast",
    reasoning: bool = False,
    model_target: str = "free",
) -> str:
    """
    Stream an LLM response into `client_id`'s SSE queue.

    Parameters
    ----------
    query     : user message
    client_id : SSE client identifier
    mode      : "fast" | "balanced" | "max"
    reasoning : enable chain-of-thought reasoning layer
    model_target : "free" | "configured" | "local"

    Routing
    -------
    fast      → selected online target by default
                  → MLX local first when target is "local" or KITTY_ENABLE_LOCAL_MLX=1
    balanced  → selected online target
                  → anthropic on OR failure
    max       → deepseek-r1  (always reasons; reasoning flag is no-op)
                  → anthropic on OR failure
    """
    model_target = _normalize_model_target(model_target)
    history  = get_history(client_id)
    soul = _get_soul()
    system_content = (soul + "\n\n---\n\n" + _SYSTEM) if soul else _SYSTEM
    messages = [{"role": "system", "content": system_content}] + history + [
        {"role": "user", "content": query}
    ]

    try:
        from src.api.emitters import emit_thinking_bubble
        preview = query[:80] + ("…" if len(query) > 80 else "")
        emit_thinking_bubble(f"Processing: {preview}", 0.7)
    except Exception:
        pass

    full = ""

    use_local = model_target == "local" or _MLX_ENABLED
    if mode == "fast" and use_local:
        try:
            full = _stream_mlx(messages, client_id, reasoning=reasoning)
        except Exception as exc:
            logger.warning("MLX failed, falling back to balanced: %s", exc)
            mode = "balanced"   # fall through below
    elif mode == "fast":
        logger.info("Routing fast mode to selected online target: %s", model_target)
        mode = "balanced"

    if mode == "balanced" and not full:
        model = _model_for_target(model_target)
        if model_target == "configured" and reasoning:
            model = _OR_BAL_R
        if os.environ.get("OPENROUTER_API_KEY"):
            try:
                full = _stream_openrouter(messages, client_id, model, reasoning)
            except Exception as exc:
                logger.warning("OpenRouter balanced failed: %s", exc)

    if mode == "max" and not full:
        if os.environ.get("OPENROUTER_API_KEY"):
            try:
                full = _stream_openrouter(messages, client_id, _OR_MAX,
                                          reasoning=True)
            except Exception as exc:
                logger.warning("OpenRouter max failed: %s", exc)

    # Anthropic last resort (any mode)
    if not full and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            full = _stream_anthropic(messages, client_id)
        except Exception as exc:
            logger.warning("Anthropic fallback failed: %s", exc)

    if not full:
        full = (
            "No response — check that OPENROUTER_API_KEY or ANTHROPIC_API_KEY "
            "is set in .env and restart the server."
        )
        token_broadcaster.put_for(client_id, "token", full)

    _append(client_id, "user", query)
    _append(client_id, "assistant", full)
    return full
