import logging

logger = logging.getLogger("kitty.reset")


def generate_reset_prompt() -> str:
    """
    Generate a character-driven prompt for the 9 PM Nightly Reset.
    """
    from gateway.brief import get_tasks_summary
    from gateway.context_builder import build_worker_context
    from gateway.llm_client import call_llm

    task_summary = get_tasks_summary()

    task_desc = f"""It is 9:00 PM. The day is winding down.
The main task we were looking at was: {task_summary}

TASK:
Write a very short, warm evening check-in for Jacob (2 sentences max).
1. Ask what 'proof' he built today (what actually got done).
2. Ask if anything stopped him, or what the first move for tomorrow is.

Rules: Use contractions. No fluff. Focus on 'Resume, don't restart'. Speak Canadian."""

    prompt = build_worker_context("reset", task_desc=task_desc)

    try:
        model = "kitty-fallback-or"
        return call_llm(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
            timeout=20,
            operation="nightly.reset",
        )
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
