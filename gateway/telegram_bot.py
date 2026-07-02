"""Telegram bot bridge — mobile access to Kitty via Telegram.

Uses the Telegram Bot API directly (no extra dependencies). Polling-based:
calls getUpdates in a loop, routes messages through Kitty's LLM pipeline,
and sends responses back.

Public API:
  start_polling() -> asyncio.Task   Start background polling loop
  send_message(chat_id, text) -> bool
  is_configured() -> bool
  stop()

Env: TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger("kitty.telegram_bot")

TELEGRAM_API = "https://api.telegram.org"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

_polling_task: asyncio.Task | None = None
_last_update_id: int = 0


def is_configured() -> bool:
    return bool(TOKEN)


async def send_message(chat_id: int, text: str) -> bool:
    """Send a text message to a Telegram chat."""
    if not TOKEN:
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TELEGRAM_API}/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text[:4096],
                    "parse_mode": "Markdown",
                },
            )
            if resp.status_code == 200:
                return True
            # Retry without Markdown if parse fails
            if resp.status_code == 400 and "parse" in resp.text.lower():
                resp2 = await client.post(
                    f"{TELEGRAM_API}/bot{TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": text[:4096]},
                )
                return resp2.status_code == 200
            logger.warning("Telegram send failed (%d): %s", resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.error("Telegram send error: %s", e)
        return False


async def _process_message(chat_id: int, text: str) -> None:
    """Route a user message through Kitty's pipeline and reply."""
    try:
        from gateway.context_builder import get_system_prompt
        from gateway.domain_router import classify_domain
        from gateway.llm_client import (
            chat_completions_non_stream,
            extract_assistant_text,
            route_model,
        )
        from gateway.voice_gate import filter_response

        domain = classify_domain(text)
        system_prompt = await get_system_prompt(text, domain=domain)
        model = route_model(text)

        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        }

        data = await chat_completions_non_stream(payload)
        reply = extract_assistant_text(data)

        gate = filter_response(reply)
        reply = gate.cleaned

        if reply:
            await send_message(chat_id, reply)

        # Log interaction
        try:
            from gateway.self_review import record_interaction

            record_interaction(text, reply)
        except Exception:
            logger.debug("telegram: failed to record interaction", exc_info=True)

    except Exception:
        logger.exception("Telegram message processing failed")
        await send_message(chat_id, "Sorry, brain fog — try again?")


async def _poll_loop() -> None:
    """Background polling loop — fetches updates and processes messages."""
    global _last_update_id

    if not TOKEN:
        logger.warning("Telegram bot token not configured — polling skipped")
        return

    logger.info("Telegram bot polling started")

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                url = f"{TELEGRAM_API}/bot{TOKEN}/getUpdates"
                params = {"timeout": 30, "offset": _last_update_id + 1}
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    await asyncio.sleep(5)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    update_id = update.get("update_id", 0)
                    if update_id > _last_update_id:
                        _last_update_id = update_id

                    message = update.get("message", {})
                    chat = message.get("chat", {})
                    chat_id = chat.get("id")
                    text = message.get("text", "").strip()

                    if chat_id and text:
                        # Handle / commands
                        if text.startswith("/"):
                            await _handle_command(chat_id, text)
                        else:
                            asyncio.create_task(_process_message(chat_id, text))

            except asyncio.CancelledError:
                logger.info("Telegram polling stopped")
                return
            except Exception:
                logger.exception("Telegram polling error")
                await asyncio.sleep(10)


async def _handle_command(chat_id: int, text: str) -> None:
    """Handle Telegram bot commands."""
    cmd = text.lower().split()[0]

    if cmd == "/start":
        await send_message(
            chat_id,
            "Hey! I'm Kitty. Ask me anything — I'm connected to the same brain as the desktop app.",
        )
    elif cmd == "/brief":
        from gateway.brief import generate_brief

        try:
            brief = generate_brief()
            intention = brief.get("intention", "")[:1500]
            await send_message(
                chat_id, intention or "Brief generated — check the desktop app for full details."
            )
        except Exception:
            logger.exception("telegram: /brief command failed")
            await send_message(chat_id, "Brief generation failed — try again later.")
    elif cmd == "/stuck":
        from gateway.brief import get_tasks_summary

        await send_message(chat_id, get_tasks_summary())
    elif cmd == "/help":
        await send_message(
            chat_id,
            (
                "Kitty Telegram Commands:\n"
                "/brief — Morning brief\n"
                "/stuck — What to work on next\n"
                "/help — This message\n\n"
                "Or just chat — I'll respond like normal."
            ),
        )
    else:
        await _process_message(chat_id, text)


def start_polling() -> asyncio.Task | None:
    """Start the Telegram polling loop. Returns the background task."""
    global _polling_task
    if not TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram disabled")
        return None
    if _polling_task and not _polling_task.done():
        return _polling_task
    _polling_task = asyncio.create_task(_poll_loop())
    return _polling_task


async def stop() -> None:
    """Stop the polling loop."""
    global _polling_task
    if _polling_task and not _polling_task.done():
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    _polling_task = None
