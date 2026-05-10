"""
Conversation history summarization via local Ollama inference.
"""
import requests

try:
    from src.memory.journal_db import PKAMemoryDB as _PKAMemoryDB
    _JOURNAL_DB_AVAILABLE = True
except ImportError:
    try:
        from scripts.journal_db import PKAMemoryDB as _PKAMemoryDB
        _JOURNAL_DB_AVAILABLE = True
    except ImportError:
        _JOURNAL_DB_AVAILABLE = False

_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = "dolphin-llama3:latest"
_SUMMARY_PROMPT_TEMPLATE = (
    "Summarize this conversation in under 256 tokens, "
    "preserving key facts and decisions:\n\n{history_text}"
)


def _history_to_text(history: list[dict]) -> str:
    parts = []
    for turn in history:
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _fallback_summary(history: list[dict]) -> str:
    for turn in reversed(history):
        content = turn.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        if content:
            return content[:500]
    return ""


def _store_in_journal(summary: str) -> None:
    if not _JOURNAL_DB_AVAILABLE:
        return
    try:
        db = _PKAMemoryDB()
        db.add_entry(summary, entry_type="summary")
    except Exception:
        pass


def summarize_history(history: list[dict], max_tokens: int = 256) -> str:
    history_text = _history_to_text(history)
    prompt = _SUMMARY_PROMPT_TEMPLATE.format(history_text=history_text)

    try:
        response = requests.post(
            _OLLAMA_URL,
            json={
                "model": _OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        summary = payload.get("response", "").strip()
        if not summary:
            raise ValueError("empty response from Ollama")
    except Exception:
        summary = _fallback_summary(history)

    _store_in_journal(summary)
    return summary
