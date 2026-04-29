"""
Task tracker — process 'done' commands and next-task queries.
"""
from src.memory.task_repo import mark_done as _mark_done, get_next_task as _get_next, get_open_tasks as _get_open

def process_done_command(text: str) -> dict:
    """
    Parse 'done [task]' from user message.
    Returns {matched: bool, response: str, next_task: str or None}
    """
    text = text.strip()
    if not text.lower().startswith("done "):
        return {"matched": False, "response": "", "next_task": None}
    task_ref = text[5:].strip()
    result = _mark_done(task_ref)
    if not result["found"]:
        return {
            "matched": True,
            "response": f"No open task matching '{task_ref}'. Check TASKS.md for open tasks.",
            "next_task": None,
        }
    next_t = result.get("next_open")
    next_str = next_t["title"] if next_t else "No open tasks remaining."
    return {
        "matched": True,
        "response": f"Marked done: {result['task']['title']}. Next: {next_str}",
        "next_task": next_str,
    }

def get_next_task_brief() -> str:
    """One-liner for morning brief."""
    nxt = _get_next()
    return f"Next: {nxt['title']}" if nxt else "No open tasks."
