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

# Loading state messages with cat theme
LOADING_MESSAGES = [
    "🐱 Kitty is sharpening claws...",
    "😺 Chasing the laser pointer...",
    "🐈 Knocking things off the desk...",
    "😸 Sitting in a box that definitely fits...",
    "😹 Staring at invisible ghosts...",
    "😻 Making biscuits on the keyboard...",
    "😼 Hunting the red dot...",
    "😽 Finding the warmest spot on the laptop...",
    "🙀 Getting distracted by a bug...",
    "😿 Knocking over your coffee (oops)...",
    "😾 Judging your code silently...",
    "😺 Counting treats...",
    "🐱 Pouncing on opportunities...",
    "😸 Stretching after a long nap...",
    "🐈 Grooming for the big presentation...",
]

# Success messages with cat theme
SUCCESS_MESSAGES = [
    "🎉 Purrr-fect! Task complete!",
    "✨ Kitty approves! ✓",
    "🐱 Mission accomplished! Time for a nap!",
    "😺 Done! That deserves some cat treats!",
    "🎊 Success! *happy purring noises*",
    "✓ Task finished! Now where's my belly rub?",
    "🌟 All done! You're pawsome!",
    "😸 Complete! That was a good hunt!",
]


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
    art = CAT_ASCII_ART.get(mood, CAT_ASCII_ART["sad"])
    console.print(art, style="orange3")


# Cat-themed error messages - because errors should be cute! 🐱
ERROR_MESSAGES = {
    "api_error": {
        "title": "🙀 API Error",
        "user_message": "Oops! Kitty knocked the server off the table. But don't worry - I'm already landing on my feet!",
        "action": "Your request was automatically re-routed to a backup server. All nine lives intact!",
    },
    "network_error": {
        "title": "😿 Connection Issue",
        "user_message": "The network went into stealth mode like a ninja cat!",
        "action": "Try again in a few moments, or go 'secret' mode for offline purring.",
    },
    "model_unavailable": {
        "title": "🐱 Model Unavailable",
        "user_message": "The AI model is taking a catnap right now...",
        "action": "I've switched to a wide-awake model. Your request is being processed at full zoomies speed!",
    },
    "rate_limit": {
        "title": "😾 Rate Limited",
        "user_message": "Too many requests! Even cats need to stop and groom themselves sometimes.",
        "action": "Take a paws and try again soon, or use a cheaper tier for more treats!",
    },
    "auth_error": {
        "title": "😼 Authentication Issue",
        "user_message": "The API key was hidden too well - even I couldn't find it!",
        "action": "I'm using my secret stash of backup keys. You might want to check yours though!",
    },
    "timeout": {
        "title": "😴 Request Timeout",
        "user_message": "The request curled up and fell asleep before finishing...",
        "action": "Switching to turbo zoomies mode! Don't worry, I'm on it like a cat on a laser pointer!",
    },
    "invalid_input": {
        "title": "🙀 Invalid Input",
        "user_message": "That request made me tilt my head like a confused kitten!",
        "action": "Try rephrasing or use /help to see all the tricks I know!",
    },
    "file_error": {
        "title": "📁 File Error",
        "user_message": "I couldn't bat that file around - it seems to be stuck under the couch!",
        "action": "Check the file path and make sure I have permission to play with it.",
    },
    "memory_error": {
        "title": "🧠 Memory Issue",
        "user_message": "My brain is full of cat memes and can't fit any more!",
        "action": "Try a shorter request or use /clear to make room for new toys!",
    },
    "unknown": {
        "title": "🐾 Curious Cat-astrophe",
        "user_message": "Something unexpected happened - probably a butterfly I had to chase!",
        "action": "I'm landing on my feet and recovering. Please try again!",
    },
}

# Cute cat ASCII art for different error states
CAT_ASCII_ART = {
    "sad": """
    /\\_/\\
   ( o.o )
    > ^ <
   "I'm sorry..."
    """,
    "apologetic": """
      /\\_/\\
     ( o.o )
      > ^ <
     /|   |\\
    "Oops, my bad!"
    """,
    "working": """
       /\\_/\\
      ( -.- )
       > ^ <
      /|   |\\
     "Fixing it..."
    """,
    "sleepy": """
      /\\_/\\
     ( -.- )  zZ
      > ^ <
     "Taking a nap..."
    """,
}

# Random cat facts to show during loading
CAT_FACTS = [
    "Cats can make over 100 different sounds!",
    "A group of cats is called a 'clowder'.",
    "Cats spend 70% of their lives sleeping.",
    "A cat's purr vibrates at a frequency that promotes healing!",
    "Cats can jump up to 6 times their height!",
    "A cat's nose print is unique, like a human fingerprint.",
    "Cats have 32 muscles in each ear!",
    "The first cat in space was named Félicette.",
    "Cats can rotate their ears 180 degrees!",
    "A cat's whiskers are the same width as its body!",
    "Cats can't taste sweetness - but they love the texture!",
    "The oldest known pet cat was found in a 9,500-year-old grave.",
    "Cats have 5 toes on front paws, but only 4 on back paws!",
    "A cat can run up to 30 mph in short bursts!",
    "Cats sweat through their paw pads!",
]


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
    error_info = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["unknown"])

    result = {
        "title": error_info["title"],
        "user_message": error_info["user_message"],
        "action": error_info["action"],
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


# Easter egg responses for special commands
EASTER_EGG_RESPONSES = {
    "/pet": [
        "😺 *purrs contentedly*",
        "😻 *rubs against your leg*",
        "😽 *happy kneading noises*",
        "🐱 *slow blink of trust*",
        "😸 *rolls over for belly rubs*",
    ],
    "/treat": [
        "😺 *nom nom nom*",
        "🐟 *crunch crunch* Yummy!",
        "😻 *purrs loudly while eating*",
        "🎣 *steals the treat and runs away*",
        "😸 *licks whiskers* More please!",
    ],
    "meow": [
        "😺 Meow!",
        "🐱 *confused head tilt* Meow?",
        "😸 Meow meow!",
        "😻 *happy meowing*",
        "😼 Are you trying to speak my language?",
    ],
    "sudo": [
        "😼 Nice try, hooman!",
        "😺 Sudo make me a sandwich?",
        "🐱 *judges your Linux skills*",
        "😸 Access denied! I'm the admin here!",
        "🙀 *hisses at unauthorized access*",
    ],
    "poke": [
        "😼 Don't poke the cat!",
        "😾 *annoyed ears back*",
        "😺 Fine, you can pet me instead.",
        "🐱 *swats at your finger*",
        "😸 Okay okay, I'm awake!",
    ],
}


def get_easter_egg_response(command: str) -> str | None:
    """Get a random response for easter egg commands"""
    command = command.lower().strip()

    # Handle /pet and /treat commands
    if command == "/pet":
        return random.choice(EASTER_EGG_RESPONSES["/pet"])
    elif command == "/treat":
        return random.choice(EASTER_EGG_RESPONSES["/treat"])
    elif command == "meow" or command == "/meow":
        return random.choice(EASTER_EGG_RESPONSES["meow"])
    elif "sudo" in command:
        return random.choice(EASTER_EGG_RESPONSES["sudo"])
    elif "poke" in command or command == "/poke":
        return random.choice(EASTER_EGG_RESPONSES["poke"])

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
