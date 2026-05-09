"""Minimal web-safe LLM fallback for streamed chat replies."""

from __future__ import annotations

import json
import logging
import os

import requests

from src.api.shared import token_broadcaster
from src.core.specialist_framework import SpecialistResponse

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = os.getenv("KITTY_MODEL", "deepseek/deepseek-v4-flash")


class WebLLMClient:
    """Direct provider client for the web UI when the orchestrator path fails."""

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()

    def chat(self, message: str, domain: str | None = None, stream: bool = False) -> SpecialistResponse:
        prompt = message.strip()
        if not prompt:
            return self._error_response("No message provided", stream)

        system_prompt = self._system_prompt(domain)
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        errors: list[str] = []

        if openrouter_key:
            try:
                text = self._chat_openrouter(
                    prompt,
                    system_prompt=system_prompt,
                    api_key=openrouter_key,
                    stream=stream,
                )
                return self._success_response(text, provider="openrouter", model=DEFAULT_OPENROUTER_MODEL)
            except Exception as e:
                logger.exception("OpenRouter web fallback failed")
                errors.append(f"OpenRouter: {str(e)}")

        if errors:
            return self._error_response(
                "Provider fallback failed. " + " | ".join(errors),
                stream,
            )

        return self._error_response(
            "No LLM API key configured for web chat. Set OPENROUTER_API_KEY in .env and restart.",
            stream,
        )

    def _chat_openrouter(self, prompt: str, system_prompt: str, api_key: str, stream: bool) -> str:
        model_to_use = os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL
        response = self._session.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/kitty",
            },
            json={
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "stream": stream,
            },
            timeout=(10, 120),
            stream=stream,
        )
        response.raise_for_status()

        if not stream:
            data = response.json()
            return data["choices"][0]["message"]["content"]

        chunks: list[str] = []
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            data_str = raw_line[5:].strip()
            if data_str == "[DONE]":
                break
            payload = json.loads(data_str)
            delta = payload["choices"][0].get("delta", {}).get("content", "")
            if delta:
                chunks.append(delta)
                token_broadcaster.broadcast("token", delta)
        return "".join(chunks)
    def _system_prompt(self, domain: str | None) -> str:
        if domain == "code":
            return "You are Kitty. Be concise, practical, and helpful about code."
        if domain in {"auto", "audio"}:
            return "You are Kitty. Be direct, grounded, and technically useful."
        return "You are Kitty. Be warm, clear, and concise."

    def _success_response(self, text: str, provider: str, model: str) -> SpecialistResponse:
        return SpecialistResponse(
            content=text,
            confidence=0.8,
            sources=[],
            safety_warnings=[],
            suggested_followups=[],
            diagnostics={
                "specialist": "WebLLM",
                "provider": provider,
                "model": model,
            },
        )

    def _error_response(self, text: str, stream: bool) -> SpecialistResponse:
        if stream:
            token_broadcaster.broadcast("error", text)
        return SpecialistResponse(
            content=text,
            confidence=0.0,
            sources=[],
            safety_warnings=[],
            suggested_followups=[],
            diagnostics={"specialist": "WebLLM"},
        )
