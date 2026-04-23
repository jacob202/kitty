"""
Pillar 1: Intake Agent - Clarity Scorer & Self-Prompter
Harnesses messy user input into structured commands.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_API_URL = "http://localhost:11434/api/generate"


def _check_ollama_available() -> bool:
    """Quick check if Ollama is running."""
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(("localhost", 11434))
        sock.close()
        return result == 0
    except Exception:
        return False


@dataclass
class ClarityResult:
    intent: str
    clarity_score: int
    needs_clarification: bool
    original_prompt: str
    warnings: list[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "clarity_score": self.clarity_score,
            "needs_clarification": self.needs_clarification,
            "original_prompt": self.original_prompt,
            "warnings": self.warnings or [],
        }


class IntakeAgent:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._openrouter_key = self._get_api_key()
        self._use_openrouter = bool(self._openrouter_key)

    def _get_api_key(self) -> str | None:
        return os.environ.get("OPENROUTER_API_KEY") or self.config.get(
            "openrouter_api_key", ""
        )

    def _call_openrouter(
        self, model: str, messages: list[dict[str, str]], **kwargs
    ) -> str:
        import requests

        headers = {
            "Authorization": f"Bearer {self._openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kitty.local",
            "X-Title": "Kitty Intake Agent",
        }
        payload = {"model": model, "messages": messages, **kwargs}
        response = requests.post(
            OPENROUTER_API_URL, headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _call_ollama(self, model: str, prompt: str, system: str = "") -> str:
        import requests

        payload = {"model": model, "prompt": prompt, "system": system, "stream": False}
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["response"]

    def _generate_prompt(self, prompt: str) -> tuple[str, str]:
        system = """You are a clarity analyzer for an AI coding assistant.
Rate the clarity of user prompts on a scale of 1-10.
Return JSON only: {"score": N, "intent": "...", "needs_clarification": bool, "warnings": [...]}
- Score 8-10: Clear, specific request
- Score 5-7: Partially clear, some ambiguity
- Score 1-4: Very unclear, needs major clarification
Consider: specificity, completeness, actionability, context."""

        user = f"Analyze this prompt:\n{prompt}"
        return system, user


def score_clarity(prompt: str) -> dict[str, Any]:
    """
    Score the clarity of a user prompt (1-10).
    Returns dict with score and analysis.
    """
    try:
        clean_prompt = re.sub(r'[^a-zA-Z\s]', '', prompt.lower()).strip()
        if clean_prompt in ["hi", "hello", "hey", "yo", "sup", "greetings", "good morning", "good afternoon", "good evening"]:
            return {
                "score": 10,
                "intent": prompt.strip(),
                "needs_clarification": False,
                "warnings": []
            }

        agent = IntakeAgent()

        # Fast path: skip API calls if no OpenRouter key
        # (only call Ollama if explicitly requested via env var)
        if not agent._openrouter_key:
            return _fallback_score(prompt)

        system_prompt, user_prompt = agent._generate_prompt(prompt)

        if agent._use_openrouter:
            try:
                response = agent._call_openrouter(
                    model="deepseek/deepseek-chat-v3",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
            except Exception as e:
                logger.warning(f"OpenRouter failed ({e}), trying cheap model...")
                response = agent._call_openrouter(
                    model="deepseek/deepseek-r1",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
        else:
            try:
                ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
                response = agent._call_ollama(
                    model=ollama_model, prompt=user_prompt, system=system_prompt
                )
            except Exception as e:
                logger.error(f"Ollama fallback failed: {e}")
                return _fallback_score(prompt)

        result = _parse_clarity_response(response, prompt)
        return result

    except Exception as e:
        logger.error(f"Clarity scoring failed: {e}")
        return _fallback_score(prompt)


def sanitize_prompt(prompt: str) -> dict[str, Any]:
    """
    Reframe messy input into structured command.
    Returns: {"intent": "...", "clarity_score": N, "needs_clarification": bool}
    """
    try:
        clean_prompt = re.sub(r'[^a-zA-Z\s]', '', prompt.lower()).strip()
        if clean_prompt in ["hi", "hello", "hey", "yo", "sup", "greetings", "good morning", "good afternoon", "good evening"]:
            return {
                "intent": prompt.strip(),
                "clarity_score": 10,
                "needs_clarification": False,
                "original_prompt": prompt,
                "warnings": []
            }

        agent = IntakeAgent()

        # Fast path: skip API calls if no OpenRouter key
        if not agent._openrouter_key:
            return _fallback_sanitize(prompt)

        system_prompt = """You are a prompt sanitizer for an AI coding assistant.
Transform messy/conversational prompts into clear, structured commands.
Return JSON: {"intent": "...", "score": N, "needs_clarification": bool, "warnings": [...]}
- intent: Clear, actionable restatement of the user's goal
- score: Clarity score 1-10
- needs_clarification: true if score < 8
- warnings: List of ambiguous aspects if any"""

        user_prompt = f"Sanitize this prompt:\n{prompt}"

        if agent._use_openrouter:
            try:
                response = agent._call_openrouter(
                    model="deepseek/deepseek-chat-v3",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=300,
                )
            except Exception:
                try:
                    response = agent._call_openrouter(
                        model="deepseek/deepseek-r1",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.2,
                        max_tokens=300,
                    )
                except Exception as e:
                    logger.error(f"OpenRouter failed: {e}")
                    return _fallback_sanitize(prompt)
        else:
            try:
                ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
                response = agent._call_ollama(
                    model=ollama_model, prompt=user_prompt, system=system_prompt
                )
            except Exception as e:
                logger.error(f"Ollama fallback failed: {e}")
                return _fallback_sanitize(prompt)

        result = _parse_sanitize_response(response, prompt)
        return result

    except Exception as e:
        logger.error(f"Prompt sanitization failed: {e}")
        return _fallback_sanitize(prompt)


def _parse_clarity_response(response: str, original: str) -> dict[str, Any]:
    try:
        json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "score": data.get("score", 5),
                "intent": data.get("intent", original),
                "needs_clarification": data.get(
                    "needs_clarification", data.get("score", 5) < 8
                ),
                "warnings": data.get("warnings", []),
            }
    except (json.JSONDecodeError, AttributeError):
        pass
    return _fallback_score(original)


def _parse_sanitize_response(response: str, original: str) -> dict[str, Any]:
    try:
        json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "intent": data.get("intent", original),
                "clarity_score": data.get("score", data.get("clarity_score", 5)),
                "needs_clarification": data.get(
                    "needs_clarification", data.get("score", 5) < 8
                ),
                "original_prompt": original,
                "warnings": data.get("warnings", []),
            }
    except (json.JSONDecodeError, AttributeError):
        pass
    return _fallback_sanitize(original)


def _fallback_score(prompt: str) -> dict[str, Any]:
    filler_words = [
        "like",
        "maybe",
        "um",
        "uh",
        "you know",
        "sort of",
        "kind of",
        "basically",
        "actually",
        "u",
        "ur",
        "tbh",
        "idk",
    ]
    vague_words = ["something", "stuff", "things", "help", "code", "it", "this", "that"]
    words = prompt.lower().replace("?", " ").replace(".", " ").split()
    filler_count = sum(1 for w in words if w in filler_words)
    vague_count = sum(1 for w in words if w in vague_words)
    length = len(words)

    score = 10
    if filler_count >= 1:
        score -= 3
    if vague_count >= 3:
        score -= 3
    if length < 8:
        score -= 4
    elif length < 12:
        score -= 2

    return {
        "score": max(1, score),
        "intent": prompt.strip(),
        "needs_clarification": score < 8,
        "warnings": ["Fallback scoring - API unavailable"] if score < 8 else [],
    }


def _fallback_sanitize(prompt: str) -> dict[str, Any]:
    cleaned = re.sub(
        r"\b(like|maybe|um|uh|you know|sort of|kind of|basically|actually|hey|hi|hello)\b",
        "",
        prompt,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    score_result = _fallback_score(cleaned)

    return {
        "intent": cleaned,
        "clarity_score": score_result["score"],
        "needs_clarification": score_result["needs_clarification"],
        "original_prompt": prompt,
        "warnings": score_result["warnings"],
    }
