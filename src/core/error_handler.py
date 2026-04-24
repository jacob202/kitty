"""
Error Handler Module - User-friendly error messages and debugging
"""

import json
import random
import traceback
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def _load_ui_strings() -> dict:
    """Load UI strings from config file"""
    config_path = Path(__file__).parent.parent.parent / "config" / "ui_strings.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load ui_strings.json: {e}")
        return {}

_UI_STRINGS = _load_ui_strings()
LOADING_MESSAGES = _UI_STRINGS.get("LOADING_MESSAGES", ["Loading..."])
SUCCESS_MESSAGES = _UI_STRINGS.get("SUCCESS_MESSAGES", ["Success!"])
ERROR_MESSAGES = _UI_STRINGS.get("ERROR_MESSAGES", {
    "unknown": {
        "title": "🐾 Curious Cat-astrophe",
        "user_message": "Something unexpected happened - probably a butterfly I had to chase!",
        "action": "I'm landing on my feet and recovering. Please try again!"
    }
})
CAT_ASCII_ART = _UI_STRINGS.get("CAT_ASCII_ART", {"sad": "\n    /\\_/\\\n   ( o.o )\n    > ^ <\n   \"I'm sorry...\"\n    "})
CAT_FACTS = _UI_STRINGS.get("CAT_FACTS", ["Cats are cute."])
EASTER_EGG_RESPONSES = _UI_STRINGS.get("EASTER_EGG_RESPONSES", {})


def get_random_loading_message() -> str:
    """Get a random cat-themed loading message"""
    return random.choice(LOADING_MESSAGES)


def get_random_success_message() -> str:
    """Get a random cat-themed success message"""
    return random.choice(SUCCESS_MESSAGES)


def get_random_cat_fact() -> str:
    """Get a random cat fact for loading screens"""
    return random.choice(CAT_FACTS)


def display_loading(message: str | None = None, show_fact: bool = False):
    """Display a cute loading message with optional cat fact"""
    msg = message or get_random_loading_message()
    console.print(f"\n🐾 {msg}", style="bold orange3")
    if show_fact:
        console.print(f"   💡 Did you know? {get_random_cat_fact()}", style="dim")


def display_success(message: str | None = None):
    """Display a cute success message"""
    msg = message or get_random_success_message()
    console.print(f"\n{msg}", style="bold green")


def display_cat_ascii(mood: str = "sad"):
    """Display cat ASCII art"""
    art = CAT_ASCII_ART.get(mood, CAT_ASCII_ART.get("sad", "Error"))
    console.print(art, style="orange3")


def classify_error(error: Exception) -> str:
    """Classify error type for user-friendly messaging"""
    error_str = str(error).lower()

    if "api" in error_str or "anthropic" in error_str or "openrouter" in error_str:
        return "api_error"
    elif "network" in error_str or "connection" in error_str or "timeout" in error_str:
        return "network_error"
    elif "unavailable" in error_str or "not found" in error_str:
        return "model_unavailable"
    elif "rate" in error_str or "quota" in error_str or "limit" in error_str:
        return "rate_limit"
    elif "auth" in error_str or "credential" in error_str or "key" in error_str:
        return "auth_error"
    elif "timeout" in error_str:
        return "timeout"
    elif "file" in error_str or "permission" in error_str or "not found" in error_str:
        return "file_error"
    elif "memory" in error_str or "context" in error_str:
        return "memory_error"
    else:
        return "unknown"


def get_user_friendly_error(error: Exception, include_debug: bool = False) -> dict[str, Any]:
    """Get user-friendly error information"""
    error_type = classify_error(error)
    error_info = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES.get("unknown", {
        "title": "Error",
        "user_message": "An error occurred.",
        "action": "Please try again."
    }))

    result = {
        "title": error_info.get("title", "Error"),
        "user_message": error_info.get("user_message", "An error occurred."),
        "action": error_info.get("action", "Please try again."),
        "error_type": error_type,
    }

    if include_debug:
        result["debug"] = {"raw_error": str(error), "traceback": traceback.format_exc()}

    return result


def display_error(error: Exception, include_debug: bool = False):
    """Display user-friendly error message with cat theme"""
    error_info = get_user_friendly_error(error, include_debug)

    # Select appropriate cat mood
    if error_info["error_type"] in ["api_error", "network_error"]:
        cat_mood = "apologetic"
    elif error_info["error_type"] == "timeout":
        cat_mood = "sleepy"
    else:
        cat_mood = "sad"

    # Display cat ASCII art
    display_cat_ascii(cat_mood)

    # User-facing message with cat theme
    console.print(
        Panel(
            f"\n{error_info['user_message']}\n\n🐾 {error_info['action']}",
            title=f"{error_info['title']}",
            border_style="orange3",
        )
    )


def display_error_table(errors: list):
    """Display errors in a formatted table"""
    table = Table(title="Recent Errors")
    table.add_column("Time", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Message", style="white")
    table.add_column("Action", style="green")

    for err in errors:
        table.add_row(
            err.get("time", "N/A"),
            err.get("type", "unknown"),
            err.get("message", ""),
            err.get("action", ""),
        )

    console.print(table)


def log_error(error: Exception, context: dict | None = None):
    """Log error to file for debugging"""
    from datetime import datetime

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "error_type": classify_error(error),
        "error_message": str(error),
        "context": context or {},
    }

    log_path = Path("data/logs/error_log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def get_suggestion_for_error(error: Exception) -> str:
    """Get specific suggestion based on error with cat theme"""
    error_type = classify_error(error)

    suggestions = {
        "api_error": "Check your API keys in .env, or I'll use my secret stash of backups! 🐱",
        "network_error": "Try going 'secret' mode for offline purring! 😺",
        "model_unavailable": "The system will automatically wake up an alternative model! 😼",
        "rate_limit": "Try saying 'cheap' for the budget-friendly tier! More treats for everyone! 🎉",
        "auth_error": "Your API key might need a refresh! Check openrouter.ai/keys 🗝️",
        "timeout": "Try a shorter request or switch to turbo zoomies mode! 🚀",
        "file_error": "Double-check that file path - make sure it's not stuck under the couch! 📁",
        "memory_error": "Try /clear to make room for new toys in my brain! 🧹",
        "unknown": "Try again or restart with /restart - I'll land on my feet! 🐾",
    }

    return suggestions.get(error_type, suggestions["unknown"])


def get_easter_egg_response(command: str) -> str | None:
    """Get a random response for easter egg commands"""
    command = command.lower().strip()

    # Handle /pet and /treat commands
    if command == "/pet":
        return random.choice(EASTER_EGG_RESPONSES.get("/pet", ["*purrs*"])) if EASTER_EGG_RESPONSES.get("/pet") else None
    elif command == "/treat":
        return random.choice(EASTER_EGG_RESPONSES.get("/treat", ["*nom nom*"])) if EASTER_EGG_RESPONSES.get("/treat") else None
    elif command == "meow" or command == "/meow":
        return random.choice(EASTER_EGG_RESPONSES.get("meow", ["Meow!"])) if EASTER_EGG_RESPONSES.get("meow") else None
    elif "sudo" in command:
        return random.choice(EASTER_EGG_RESPONSES.get("sudo", ["Access denied!"])) if EASTER_EGG_RESPONSES.get("sudo") else None
    elif "poke" in command or command == "/poke":
        return random.choice(EASTER_EGG_RESPONSES.get("poke", ["*swats*"])) if EASTER_EGG_RESPONSES.get("poke") else None

    return None


def is_special_date() -> dict:
    """Check if today is a special cat-related date"""
    from datetime import datetime

    today = datetime.now()
    special_dates = {
        (2, 22): {
            "name": "Cat Day (US)",
            "message": "🐱 Happy National Cat Day! Extra treats today!",
        },
        (8, 8): {
            "name": "International Cat Day",
            "message": "🌍 Happy International Cat Day! Purring worldwide!",
        },
        (10, 29): {
            "name": "National Cat Day (US)",
            "message": "🎉 Happy National Cat Day! Time to celebrate!",
        },
    }

    # Check for Caturday (Saturday)
    is_caturday = today.weekday() == 5

    special = special_dates.get((today.month, today.day))

    return {
        "is_caturday": is_caturday,
        "caturday_message": "🐱 It's Caturday! Time to relax and knock things over!"
        if is_caturday
        else None,
        "special_date": special,
    }


if __name__ == "__main__":
    # Test the error handler
    test_error = Exception("API rate limit exceeded")
    display_error(test_error)
    print(f"\n💡 Suggestion: {get_suggestion_for_error(test_error)}")