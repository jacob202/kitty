"""
Kitty CLI - Cat-themed terminal output and ASCII art
Because the command line should be delightful too! 🐱
"""

import random

from rich.console import Console

console = Console()

# ═══════════════════════════════════════════════════════════════════════════
# CAT ASCII ART COLLECTION
# ═══════════════════════════════════════════════════════════════════════════

CAT_ASCII = {
    "happy": """
      /\\_/\\
     ( ^.^ )
      > ^ <
     /|   |\\
    "Purrrfect!"
    """,
    "sad": """
      /\\_/\\
     ( T.T )
      > ^ <
     "I'm sorry..."
    """,
    "working": """
       /\\_/\\
      ( -.- )
       > ^ <
      /|   |\\
     "Computing..."
    """,
    "sleepy": """
      /\\_/\\
     ( -.- )  zZ
      > ^ <
     "Nap time..."
    """,
    "surprised": """
      /\\_/\\
     ( O.O )
      > ^ <
     "Oh my!"
    """,
    "celebrating": """
      /\\_/\\
     ( ^o^ )
      > ^ <
     /|   |\\
    / |   | \\
   "Party time!"
    """,
    "judging": """
      /\\_/\\
     ( ¬.¬ )
      > ^ <
     "Really?"
    """,
    "error": """
      /\\_/\\
     ( x.x )
      > ^ <
     "Oops!"
    """,
}

# Box cat variations
BOX_CATS = [
    """
    +-------+
    | /\\_/\\ |
    |( o.o )|
    | > ^ < |
    +-------+
    |  BOX  |
    +-------+
    """,
    """
    ┌─────────┐
    │  /\\_/\\  │
    │ ( ^.^ ) │
    │  > ^ <  │
    └─────────┘
      I fits!
    """,
]

# Sleepy cats
SLEEPY_CATS = [
    """
      /\\_/\\
     ( -.- )
      > ^ <
    zZ
    """,
    """
       /\\_/\\
      ( -.- )
       > ^ <
             zZ
    """,
]

# ═══════════════════════════════════════════════════════════════════════════
# MESSAGES
# ═══════════════════════════════════════════════════════════════════════════

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
    "😼 Sharpening my debugging skills...",
    "😺 Chasing my own tail...",
    "🐱 Waiting for the can opener sound...",
    "😽 Practicing my landing...",
]

SUCCESS_MESSAGES = [
    "🎉 Purrr-fect! Task complete!",
    "✨ Kitty approves! ✓",
    "🐱 Mission accomplished! Time for a nap!",
    "😺 Done! That deserves some cat treats!",
    "🎊 Success! *happy purring noises*",
    "✓ Task finished! Now where's my belly rub?",
    "🌟 All done! You're pawsome!",
    "😸 Complete! That was a good hunt!",
    "🐾 Success! Landing on my feet!",
    "😻 Excellence! Have some head scratches!",
]

ERROR_MESSAGES = [
    "🙀 Oops! Kitty knocked the server off the table!",
    "😿 Purr-oblem detected! Investigating...",
    "😾 Cat-astrophe! But we got this!",
    "🐱 Hiss-terical error occurred!",
    "😺 Oops, I batted that one away by accident!",
]

# ═══════════════════════════════════════════════════════════════════════════
# CAT FACTS
# ═══════════════════════════════════════════════════════════════════════════

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
    "Ancient Egyptians worshipped cats as sacred animals.",
    "Cats have three eyelids!",
    "A cat's meow is specifically for humans - they don't meow at other cats!",
    "Cats can drink seawater - their kidneys can filter out the salt!",
]

# ═══════════════════════════════════════════════════════════════════════════
# EASTER EGG RESPONSES
# ═══════════════════════════════════════════════════════════════════════════

EASTER_EGGS = {
    "pet": [
        "😺 *purrs contentedly*",
        "😻 *rubs against your leg*",
        "😽 *happy kneading noises*",
        "🐱 *slow blink of trust*",
        "😸 *rolls over for belly rubs*",
    ],
    "treat": [
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
}

# ═══════════════════════════════════════════════════════════════════════════
# DISPLAY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def display_cat(mood: str = "happy", show: bool = True) -> str:
    """Display or return cat ASCII art"""
    art = CAT_ASCII.get(mood, CAT_ASCII["happy"])
    if show:
        console.print(art, style="orange3")
    return art


def display_loading(message: str | None = None, show_fact: bool = False, show_cat: bool = True):
    """Display a cute loading message with optional cat fact"""
    if show_cat:
        display_cat("working")

    msg = message or random.choice(LOADING_MESSAGES)
    console.print(f"\n🐾 {msg}", style="bold orange3")

    if show_fact:
        fact = random.choice(CAT_FACTS)
        console.print(f"   💡 Did you know? {fact}", style="dim")


def display_success(message: str | None = None, show_cat: bool = True):
    """Display a cute success message"""
    if show_cat:
        display_cat("celebrating")

    msg = message or random.choice(SUCCESS_MESSAGES)
    console.print(f"\n{msg}", style="bold green")


def display_error(message: str | None = None, show_cat: bool = True):
    """Display a cute error message"""
    if show_cat:
        display_cat("sad")

    msg = message or random.choice(ERROR_MESSAGES)
    console.print(f"\n{msg}", style="bold red")


def get_random_loading_message() -> str:
    """Get a random cat-themed loading message"""
    return random.choice(LOADING_MESSAGES)


def get_random_success_message() -> str:
    """Get a random cat-themed success message"""
    return random.choice(SUCCESS_MESSAGES)


def get_random_error_message() -> str:
    """Get a random cat-themed error message"""
    return random.choice(ERROR_MESSAGES)


def get_random_cat_fact() -> str:
    """Get a random cat fact"""
    return random.choice(CAT_FACTS)


def display_box_cat():
    """Display a cat in a box"""
    box_cat = random.choice(BOX_CATS)
    console.print(box_cat, style="orange3")
    console.print("📦 If I fits, I sits!", style="dim")


def display_sleepy_cat():
    """Display a sleepy cat"""
    sleepy_cat = random.choice(SLEEPY_CATS)
    console.print(sleepy_cat, style="dim")
    console.print("😴 zZz... processing... zZz...", style="dim")


# ═══════════════════════════════════════════════════════════════════════════
# EASTER EGG FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def handle_easter_egg(command: str) -> str | None:
    """Handle easter egg commands"""
    command = command.lower().strip()

    if command in ["/pet", "pet"]:
        response = random.choice(EASTER_EGGS["pet"])
        console.print(f"\n{response}", style="orange3")
        return response

    elif command in ["/treat", "treat"]:
        response = random.choice(EASTER_EGGS["treat"])
        console.print(f"\n{response}", style="orange3")
        display_cat("happy")
        return response

    elif command in ["/meow", "meow"]:
        response = random.choice(EASTER_EGGS["meow"])
        console.print(f"\n{response}", style="orange3")
        return response

    elif "sudo" in command:
        response = random.choice(EASTER_EGGS["sudo"])
        console.print(f"\n{response}", style="red")
        display_cat("judging")
        return response

    return None


def is_caturday() -> bool:
    """Check if today is Caturday (Saturday)"""
    from datetime import datetime

    return datetime.now().weekday() == 5  # Saturday


def display_caturday_message():
    """Display a special Caturday message"""
    console.print("\n" + "=" * 50, style="magenta")
    console.print("🎉 IT'S CATURDAY! 🎉", style="bold magenta", justify="center")
    console.print("Time to relax and knock things over!", style="magenta", justify="center")
    console.print("=" * 50 + "\n", style="magenta")
    display_cat("celebrating")


# ═══════════════════════════════════════════════════════════════════════════
# WELCOME & GOODBYE
# ═══════════════════════════════════════════════════════════════════════════


def display_welcome():
    """Display welcome message with cat art and cheatsheet"""
    welcome_art = """
      /\\_/\
     ( o.o )
      > ^ <
     /|   |\\
    """
    console.print(welcome_art, style="orange3")
    console.print("\n Welcome to Kitty AI!", style="bold orange3")
    console.print("   Your feline assistant is ready to help!\n", style="dim")

    if is_caturday():
        display_caturday_message()

    display_cheatsheet()


def display_cheatsheet():
    """Display quick-start cheatsheet"""
    console.print("\n" + "=" * 60, style="dim")
    console.print("  KITTY AI – COMPOUND ENGINEERING", style="bold cyan")
    console.print("=" * 60 + "\n", style="dim")

    console.print("  [bold]Compound Commands:[/bold]")
    console.print("    [cyan]kitty chat[/cyan]              Chat with Backup Jacob")
    console.print("    [cyan]kitty plan \"task\"[/cyan]       Generate plan → PLAN.md")
    console.print("    [cyan]kitty work[/cyan]               Execute plan with coder")
    console.print("    [cyan]kitty review[/cyan]             Review code output")
    console.print("    [cyan]kitty compound[/cyan]           Extract reusable skill")
    console.print("    [cyan]kitty why[/cyan]                Show swarm reasoning")
    console.print("")
    console.print("  [bold]Swarm AI:[/bold]")
    console.print("    [cyan]kitty agent test[/cyan]        Run UX persona tests")
    console.print("    [cyan]kitty agent bugs[/cyan]        Run bug hunter swarm")
    console.print("    [cyan]kitty agent list[/cyan]        List 8 swarm testers")
    console.print("")
    console.print("  [bold]Server:[/bold]")
    console.print("    [cyan]kitty server start[/cyan]      Start web daemon")
    console.print("    [cyan]kitty server status[/cyan]     Check health")
    console.print("")
    console.print("  [dim]Config: kitty_config.json | Models: Ollama (local)[/dim]")
    console.print("=" * 60 + "\n", style="dim")


def display_goodbye():
    """Display goodbye message"""
    console.print("\n" + "=" * 30, style="dim")
    display_cat("sleepy")
    console.print("   Goodbye! Kitty is taking a nap now...\n", style="dim")


# ═══════════════════════════════════════════════════════════════════════════
# PROGRESS BARS
# ═══════════════════════════════════════════════════════════════════════════


def create_yarn_progress(current: int, total: int, width: int = 40) -> str:
    """Create a yarn ball styled progress bar"""
    percentage = current / total if total > 0 else 0
    filled = int(width * percentage)
    empty = width - filled

    yarn = "🧶" * filled + "⬜" * empty
    return f"[{yarn}] {percentage * 100:.1f}%"


def display_progress(label: str, current: int, total: int):
    """Display a cat-themed progress bar"""
    progress_bar = create_yarn_progress(current, total)
    console.print(f"🐱 {label}: {progress_bar}", style="orange3")


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test all the cat-themed features
    display_welcome()

    console.print("\n[bold]Testing Loading States:[/bold]")
    display_loading(show_fact=True)

    console.print("\n[bold]Testing Success:[/bold]")
    display_success()

    console.print("\n[bold]Testing Error:[/bold]")
    display_error()

    console.print("\n[bold]Testing Easter Eggs:[/bold]")
    handle_easter_egg("/pet")
    handle_easter_egg("/treat")
    handle_easter_egg("sudo make me a sandwich")

    console.print("\n[bold]Testing Box Cat:[/bold]")
    display_box_cat()

    console.print("\n[bold]Testing Progress:[/bold]")
    for i in range(0, 101, 25):
        display_progress("Hunting bugs", i, 100)

    display_goodbye()
