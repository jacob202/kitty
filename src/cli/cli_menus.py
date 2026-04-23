"""Pillar 2: CLI Menus - Interactive command-line menus for Kitty architecture."""


import questionary
from rich.console import Console
from rich.syntax import Syntax

console = Console()


def show_clarity_menu(user_prompt: str, interpretations: list[str]) -> str:
    """
    Show Clarity Menu when Clarity Score < 8.

    Args:
        user_prompt: The original user prompt
        interpretations: List of 3 possible interpretations

    Returns:
        Selected interpretation or user-provided custom interpretation
    """
    options = interpretations.copy()
    options.append("Escape hatch: Type your own")

    choice = questionary.select(
        f'🔍 Your goal: "{user_prompt[:60]}{"..." if len(user_prompt) > 60 else ""}"\n\n'
        "I found multiple interpretations. Which matches your intent?",
        choices=options,
        qmark="►",
        style=questionary.Style(
            [
                ("selected", "fg:cyan bold"),
                ("pointer", "fg:cyan bold"),
            ]
        ),
    ).ask()

    if choice == "Escape hatch: Type your own":
        return questionary.text("Enter your interpretation:", qmark="►").ask()

    return choice


def confirm_action(message: str, syntax_highlight: str | None = None) -> bool:
    """
    Show confirmation menu for destructive actions.

    Args:
        message: Description of the action to confirm
        syntax_highlight: Optional language for syntax highlighting

    Returns:
        True if confirmed, False otherwise
    """
    console.print("\n[bold yellow]⚠️  Destructive Action[/bold yellow]\n")

    if syntax_highlight and "\n" in message:
        syntax = Syntax(message, syntax_highlight, theme="monokai", line_numbers=True)
        console.print(syntax)
    else:
        console.print(f"[white]{message}[/white]")

    console.print()

    response = questionary.confirm(
        "Do you want to proceed?", qmark="►", default=False, auto_enter=False
    ).ask()

    return response


def show_options(options: list[str], title: str = "Options") -> int:
    """
    Show selectable options menu with arrow key navigation.

    Args:
        options: List of option strings
        title: Menu title

    Returns:
        Index of selected option (0-based)
    """
    selected = questionary.select(
        f"📋 {title}",
        choices=options,
        qmark="►",
        style=questionary.Style(
            [
                ("selected", "fg:green bold"),
                ("pointer", "fg:green bold"),
            ]
        ),
    ).ask()

    return options.index(selected)


if __name__ == "__main__":
    result = show_options(["Option 1", "Option 2", "Option 3"], "Test Menu")
    print(f"Selected index: {result}")
