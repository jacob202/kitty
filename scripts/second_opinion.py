#!/usr/bin/env python3
"""Run a question meant for Jacob through a second LLM before he sees it.

Jacob pastes Claude's questions into another model anyway — this automates it.
Given the question (and optional context), a second, independent model returns:
  1. a plain-English translation of what's being asked,
  2. what each option means in practice,
  3. one clear recommendation and why.

Usage:
    python3 scripts/second_opinion.py "Question text with options A/B/C"
    echo "long question" | python3 scripts/second_opinion.py

Provider order mirrors the gateway fallback chain (cheap first): OpenRouter →
Gemini → NVIDIA. Keys come from the environment or .env.

Exit codes are a contract the caller relies on (see
.claude/skills/second-opinion/SKILL.md):
  0  an opinion was produced
  2  expected unavailability — no key set, or every provider unreachable:
     transport failure, 401/403, 408, 429, or 5xx. Retrying later or fixing
     a key resolves these.
  3  a defect in this script or its config — a malformed provider payload,
     or a deterministic 4xx such as a bad model name. These fail identically
     forever, so they must never be skipped as if a provider were merely
     down.
"""

import os
import sys
import traceback
from pathlib import Path

try:
    import requests
except ImportError as exc:  # interpreter without the venv — caller skips on exit 2
    print(
        f"second opinion unavailable — requests not importable under {sys.executable}: {exc}",
        file=sys.stderr,
    )
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent

SYSTEM_PROMPT = """You are a plain-English advisor for Jacob, a curious generalist who is
not a software engineer. An AI coding assistant is about to ask him the question below.
Your job, in under 200 words, no jargon:
1. TRANSLATION: what is actually being asked, in one or two plain sentences.
2. OPTIONS: what each option means in practice for him (skip if there are none).
3. RECOMMENDATION: pick ONE option and say why in plain language.
Be direct. If the question is unnecessary or answerable from common sense, say so."""


class ProviderUnavailable(RuntimeError):
    """No provider could be reached — missing key, network, or HTTP failure.

    Deliberately narrow: a malformed response is a defect, not unavailability,
    and must not be squashed into the same exit code.
    """


def _load_dotenv() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _is_unavailability(exc: "requests.RequestException") -> bool:
    """True when the provider is unreachable or temporarily unusable.

    Transport errors (no response at all), auth rejections, rate limits, and
    5xx are unavailability — retrying later or fixing a key resolves them.

    A deterministic 4xx (bad model name, malformed request schema) is a defect
    in this script or its config: it will fail identically forever. Skipping
    that silently would hide a permanently broken integration behind the same
    exit code as "no API key", so it must reach exit 3.
    """
    resp = getattr(exc, "response", None)
    status = getattr(resp, "status_code", None)
    if status is None:
        return True  # no response: connection, DNS, timeout
    if status in (401, 403, 408, 429) or status >= 500:
        return True
    return False


def _openai_compatible(base: str, key: str, model: str, question: str) -> str:
    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                "max_tokens": 500,
            },
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        if not _is_unavailability(exc):
            raise
        raise ProviderUnavailable(str(exc)) from exc
    # Decoding is deliberately outside the try: requests.exceptions.JSONDecodeError
    # subclasses RequestException, and a malformed body is a defect, not an
    # unreachable provider. It must reach exit 3, not be skipped as exit 2.
    return resp.json()["choices"][0]["message"]["content"].strip()


def _gemini(key: str, question: str) -> str:
    model = os.environ.get("KITTY_GEMINI_MODEL", "gemini-2.5-flash")
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": question}]}],
            },
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        if not _is_unavailability(exc):
            raise
        raise ProviderUnavailable(str(exc)) from exc
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def get_second_opinion(question: str) -> tuple[str, str]:
    """Return (provider_label, opinion).

    Raises ``ProviderUnavailable`` when no provider answers. Any other
    exception is a real defect and is left to propagate.
    """
    _load_dotenv()
    errors = []

    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        model = os.environ.get("KITTY_OPENROUTER_CHEAP", "deepseek/deepseek-v4-flash")
        try:
            return f"openrouter/{model}", _openai_compatible(
                "https://openrouter.ai/api/v1", key, model, question
            )
        except ProviderUnavailable as exc:
            errors.append(f"openrouter: {exc}")

    key = os.environ.get("GEMINI_API_KEY")
    if key:
        try:
            return "gemini", _gemini(key, question)
        except ProviderUnavailable as exc:
            errors.append(f"gemini: {exc}")

    key = os.environ.get("NVIDIA_API_KEY")
    if key:
        base = os.environ.get("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")
        model = os.environ.get("NVIDIA_CHAT_MODEL", "deepseek-ai/deepseek-v4-pro")
        try:
            return f"nvidia/{model}", _openai_compatible(base, key, model, question)
        except ProviderUnavailable as exc:
            errors.append(f"nvidia: {exc}")

    if errors:
        raise ProviderUnavailable("all providers unreachable: " + "; ".join(errors))
    raise ProviderUnavailable(
        "no provider key set (OPENROUTER_API_KEY / GEMINI_API_KEY / NVIDIA_API_KEY)"
    )


def main() -> int:
    question = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not question:
        print("usage: second_opinion.py <question for Jacob>", file=sys.stderr)
        return 1
    try:
        provider, opinion = get_second_opinion(question)
    except ProviderUnavailable as exc:
        print(f"second opinion unavailable — {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("second opinion FAILED — defect in this script, not unavailability:", file=sys.stderr)
        traceback.print_exc()
        return 3
    print(f"[second opinion via {provider}]\n\n{opinion}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
