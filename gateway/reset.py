import os
import requests
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("kitty.reset")

def generate_reset_prompt() -> str:
    """
    Generate a character-driven prompt for the 9 PM Nightly Reset.
    """
    from gateway.brief import get_tasks_summary
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    task_summary = get_tasks_summary()
    
    from gateway.context_builder import build_worker_context

    task_desc = f"""It is 9:00 PM. The day is winding down. 
The main task we were looking at was: {task_summary}

TASK:
Write a very short, warm evening check-in for Jacob (2 sentences max). 
1. Ask what 'proof' he built today (what actually got done).
2. Ask if anything stopped him, or what the first move for tomorrow is.

Rules: Use contractions. No fluff. Focus on 'Resume, don't restart'. Speak Canadian."""

    prompt = build_worker_context("reset", task_desc=task_desc)

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/jacobbrizinski/kitty",
                "X-Title": "Kitty Nightly Reset",
            },
            json={
                "model": "google/gemini-2.0-flash-exp:free" if not api_key else "deepseek/deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.7,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Nightly Reset Prompt generation failed: {e}")
        return "Hey Jacob. What was the proof we built today? What's the one move for tomorrow?"

def send_nightly_reset():
    """Triggers the nightly reset notification."""
    from gateway.notify import send_pushover
    
    message = generate_reset_prompt()
    success = send_pushover(message, title="Kitty: Nightly Reset")
    if success:
        logger.info("Nightly reset notification sent.")
    return success
