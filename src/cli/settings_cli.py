#!/usr/bin/env python3
"""
Kitty Settings CLI - Interactive settings management for Kitty AI
"""

import sys
from pathlib import Path

import questionary
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config.settings_manager import ProfileSettings, SettingsManager

app = typer.Typer(help="Kitty AI Settings Management")
console = Console()

# Global settings manager instance
settings_mgr = SettingsManager()


@app.callback()
def callback():
    """Manage Kitty AI profiles and settings."""
    pass


@app.command("list")
def list_profiles():
    """List all available profiles."""
    profiles = settings_mgr.list_profiles()

    table = Table(
        title="Available Profiles", box=box.ROUNDED, show_header=True, header_style="bold cyan"
    )

    table.add_column("Status", style="bold", width=10)
    table.add_column("Name", style="green", width=25)
    table.add_column("Description", style="white", width=50)

    for profile in profiles:
        status = "[green]● Active" if profile["active"] else "[dim]○"
        table.add_row(status, profile["name"], profile["description"])

    console.print(table)
    console.print("\n[dim]Use 'kitty settings show <profile>' for detailed view[/dim]")


@app.command("show")
def show_profile(profile_name: str | None = typer.Argument(None, help="Profile name to show")):
    """Show detailed profile configuration."""
    if not profile_name:
        profile_name = settings_mgr._active_profile

    try:
        summary = settings_mgr.get_profile_summary(profile_name)
        profile = settings_mgr.load_profile(profile_name)

        # Profile header
        active_marker = " [ACTIVE]" if summary.get("active") else ""
        console.print(
            Panel(
                f"[bold cyan]{profile_name}{active_marker}[/bold cyan]\n"
                f"[dim]{profile.description}[/dim]",
                title="Profile",
                border_style="cyan",
            )
        )

        # Model settings
        model = summary.get("model", {})
        model_table = Table(show_header=False, box=None)
        model_table.add_column("Setting", style="yellow", width=20)
        model_table.add_column("Value", style="white")

        model_table.add_row("Provider", profile.model.provider)
        model_table.add_row("Model", model.get("model_name", "N/A"))
        model_table.add_row("Temperature", str(model.get("temperature", "N/A")))
        model_table.add_row("Max Tokens", str(model.get("max_tokens", "N/A")))
        model_table.add_row("Top-p", str(profile.model.top_p))
        model_table.add_row("Freq Penalty", str(profile.model.frequency_penalty))
        model_table.add_row("Presence Penalty", str(profile.model.presence_penalty))

        console.print(Panel(model_table, title="Model Configuration", border_style="green"))

        # Personality & Style
        style_table = Table(show_header=False, box=None)
        style_table.add_column("Setting", style="yellow", width=20)
        style_table.add_column("Value", style="white")

        style_table.add_row("Personality", profile.personality)
        style_table.add_row("Thinking Style", profile.thinking_style)
        style_table.add_row("Response Format", profile.response_format)
        style_table.add_row("UI Theme", profile.ui_theme)
        style_table.add_row("Animation", profile.animation_speed)

        console.print(Panel(style_table, title="Style & Behavior", border_style="blue"))

        # Tools enabled
        tools = profile.tools
        tools_enabled = []
        if tools.web_search:
            tools_enabled.append("Web Search")
        if tools.code_execution:
            tools_enabled.append("Code Exec")
        if tools.file_operations:
            tools_enabled.append("File Ops")
        if tools.schematic_analysis:
            tools_enabled.append("Schematics")
        if tools.bom_manager:
            tools_enabled.append("BOM Manager")
        if tools.datasheet_lookup:
            tools_enabled.append("Datasheets")
        if tools.vision_analysis:
            tools_enabled.append("Vision")
        if tools.vector_search:
            tools_enabled.append("Vector Search")
        if tools.memory_recall:
            tools_enabled.append("Memory")
        if tools.custom_agents:
            tools_enabled.append("Custom Agents")

        console.print(
            Panel(
                ", ".join(tools_enabled) if tools_enabled else "[dim]None enabled[/dim]",
                title=f"Tools Enabled ({len(tools_enabled)}/10)",
                border_style="magenta",
            )
        )

        # System prompt preview
        prompt_preview = (
            profile.system_prompt[:200] + "..."
            if len(profile.system_prompt) > 200
            else profile.system_prompt
        )
        console.print(
            Panel(
                f"[dim]{prompt_preview}[/dim]",
                title="System Prompt (preview)",
                border_style="yellow",
            )
        )

    except FileNotFoundError:
        console.print(f"[red]Profile '{profile_name}' not found.[/red]")
        raise typer.Exit(1)


@app.command("use")
def use_profile(profile_name: str = typer.Argument(..., help="Profile name to activate")):
    """Activate a profile."""
    if settings_mgr.set_active_profile(profile_name):
        console.print(f"[green]✓ Activated profile: {profile_name}[/green]")

        # Show brief summary
        summary = settings_mgr.get_profile_summary(profile_name)
        console.print(f"[dim]  Model: {summary.get('model', {}).get('model_name')}[/dim]")
        console.print(f"[dim]  Tools: {summary.get('tools_enabled', 0)} enabled[/dim]")
    else:
        console.print(f"[red]✗ Failed to activate profile: {profile_name}[/red]")
        raise typer.Exit(1)


@app.command("create")
def create_profile(
    profile_name: str = typer.Argument(..., help="Name for new profile"),
    base: str | None = typer.Option(None, "--base", "-b", help="Base profile to copy from"),
):
    """Create a new profile."""
    if not base:
        # Interactive selection
        profiles = settings_mgr.list_profiles()
        choices = [p["name"] for p in profiles]

        base = questionary.select("Select a base profile:", choices=choices).ask()

    try:
        settings_mgr.create_profile(profile_name, base)
        console.print(f"[green]✓ Created profile: {profile_name}[/green]")
        console.print(f"[dim]  Based on: {base}[/dim]")
        console.print(f"\n[dim]Use 'kitty settings edit {profile_name}' to customize[/dim]")
    except Exception as e:
        console.print(f"[red]✗ Failed to create profile: {e}[/red]")
        raise typer.Exit(1)


@app.command("edit")
def edit_profile(profile_name: str | None = typer.Argument(None, help="Profile to edit")):
    """Edit a profile interactively."""
    if not profile_name:
        profile_name = settings_mgr._active_profile

    try:
        profile = settings_mgr.load_profile(profile_name)
    except FileNotFoundError:
        console.print(f"[red]Profile '{profile_name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(Panel(f"Editing Profile: [cyan]{profile_name}[/cyan]", border_style="cyan"))

    # Edit menu
    while True:
        choice = questionary.select(
            "What would you like to edit?",
            choices=[
                "Model Settings (temperature, tokens, etc.)",
                "System Prompt",
                "Personality & Style",
                "Tool Availability",
                "Middleware Settings",
                "UI Preferences",
                "Save and Exit",
                "Cancel",
            ],
        ).ask()

        if choice == "Model Settings (temperature, tokens, etc.)":
            profile = _edit_model_settings(profile)
        elif choice == "System Prompt":
            profile = _edit_system_prompt(profile)
        elif choice == "Personality & Style":
            profile = _edit_personality(profile)
        elif choice == "Tool Availability":
            profile = _edit_tools(profile)
        elif choice == "Middleware Settings":
            profile = _edit_middleware(profile)
        elif choice == "UI Preferences":
            profile = _edit_ui(profile)
        elif choice == "Save and Exit":
            if settings_mgr.save_profile(profile_name, profile):
                console.print(f"[green]✓ Saved profile: {profile_name}[/green]")
            break
        elif choice == "Cancel":
            console.print("[dim]Cancelled. No changes saved.[/dim]")
            break


def _edit_model_settings(profile: ProfileSettings) -> ProfileSettings:
    """Interactive model settings editor."""
    console.print("\n[bold]Model Settings[/bold]")

    # Provider
    profile.model.provider = questionary.select(
        "Model Provider:", choices=["claude", "openai", "ollama"], default=profile.model.provider
    ).ask()

    # Model name
    profile.model.model_name = questionary.text(
        "Model Name:", default=profile.model.model_name
    ).ask()

    # Temperature
    temp_str = questionary.text(
        "Temperature (0.0-2.0):", default=str(profile.model.temperature)
    ).ask()
    profile.model.temperature = float(temp_str)

    # Max tokens
    tokens_str = questionary.text(
        "Max Tokens (100-8000):", default=str(profile.model.max_tokens)
    ).ask()
    profile.model.max_tokens = int(tokens_str)

    # Top-p
    top_p_str = questionary.text("Top-p (0.0-1.0):", default=str(profile.model.top_p)).ask()
    profile.model.top_p = float(top_p_str)

    console.print("[green]✓ Model settings updated[/green]\n")
    return profile


def _edit_system_prompt(profile: ProfileSettings) -> ProfileSettings:
    """Interactive system prompt editor."""
    console.print("\n[bold]System Prompt Editor[/bold]")
    console.print("[dim]Current prompt:[/dim]")
    console.print(Syntax(profile.system_prompt, "text", theme="monokai"))

    new_prompt = questionary.text(
        "Enter new system prompt (or press Enter to keep current):",
        default=profile.system_prompt,
        multiline=True,
    ).ask()

    if new_prompt != profile.system_prompt:
        profile.system_prompt = new_prompt
        console.print("[green]✓ System prompt updated[/green]\n")
    else:
        console.print("[dim]No changes made[/dim]\n")

    return profile


def _edit_personality(profile: ProfileSettings) -> ProfileSettings:
    """Interactive personality editor."""
    console.print("\n[bold]Personality & Style Settings[/bold]")

    profile.personality = questionary.select(
        "Personality:",
        choices=[
            "helpful",
            "analytical",
            "precise",
            "creative",
            "technician",
            "teacher",
            "developer",
        ],
        default=profile.personality,
    ).ask()

    profile.thinking_style = questionary.select(
        "Thinking Style:",
        choices=["step-by-step", "direct", "creative"],
        default=profile.thinking_style,
    ).ask()

    profile.response_format = questionary.select(
        "Response Format:",
        choices=["concise", "verbose", "structured"],
        default=profile.response_format,
    ).ask()

    console.print("[green]✓ Personality settings updated[/green]\n")
    return profile


def _edit_tools(profile: ProfileSettings) -> ProfileSettings:
    """Interactive tool availability editor."""
    console.print("\n[bold]Tool Availability[/bold]")

    tools = profile.tools

    tools.web_search = questionary.confirm("Enable Web Search?", default=tools.web_search).ask()
    tools.code_execution = questionary.confirm(
        "Enable Code Execution?", default=tools.code_execution
    ).ask()
    tools.file_operations = questionary.confirm(
        "Enable File Operations?", default=tools.file_operations
    ).ask()
    tools.schematic_analysis = questionary.confirm(
        "Enable Schematic Analysis?", default=tools.schematic_analysis
    ).ask()
    tools.bom_manager = questionary.confirm("Enable BOM Manager?", default=tools.bom_manager).ask()
    tools.datasheet_lookup = questionary.confirm(
        "Enable Datasheet Lookup?", default=tools.datasheet_lookup
    ).ask()
    tools.vision_analysis = questionary.confirm(
        "Enable Vision Analysis?", default=tools.vision_analysis
    ).ask()
    tools.vector_search = questionary.confirm(
        "Enable Vector Search?", default=tools.vector_search
    ).ask()
    tools.memory_recall = questionary.confirm(
        "Enable Memory Recall?", default=tools.memory_recall
    ).ask()
    tools.custom_agents = questionary.confirm(
        "Enable Custom Agents?", default=tools.custom_agents
    ).ask()

    console.print("[green]✓ Tool settings updated[/green]\n")
    return profile


def _edit_middleware(profile: ProfileSettings) -> ProfileSettings:
    """Interactive middleware settings editor."""
    console.print("\n[bold]Middleware Settings[/bold]")

    mw = profile.middleware

    mw.auto_route = questionary.confirm("Enable Auto-Routing?", default=mw.auto_route).ask()

    if mw.auto_route:
        threshold = questionary.text(
            "Max cost per request ($):", default=str(mw.max_cost_per_request)
        ).ask()
        mw.max_cost_per_request = float(threshold)

    console.print("[green]✓ Middleware settings updated[/green]\n")
    return profile


def _edit_ui(profile: ProfileSettings) -> ProfileSettings:
    """Interactive UI settings editor."""
    console.print("\n[bold]UI Preferences[/bold]")

    profile.ui_theme = questionary.select(
        "UI Theme:",
        choices=["hardware", "research", "creative", "developer", "calm", "dark", "light"],
        default=profile.ui_theme,
    ).ask()

    profile.animation_speed = questionary.select(
        "Animation Speed:",
        choices=["slow", "normal", "fast", "none"],
        default=profile.animation_speed,
    ).ask()

    profile.compact_mode = questionary.confirm(
        "Enable Compact Mode?", default=profile.compact_mode
    ).ask()

    console.print("[green]✓ UI preferences updated[/green]\n")
    return profile


@app.command("delete")
def delete_profile(
    profile_name: str = typer.Argument(..., help="Profile to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a profile."""
    if profile_name in SettingsManager.DEFAULT_PROFILES:
        console.print(f"[red]Cannot delete built-in profile: {profile_name}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = questionary.confirm(
            f"Are you sure you want to delete '{profile_name}'?", default=False
        ).ask()

        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            return

    if settings_mgr.delete_profile(profile_name):
        console.print(f"[green]✓ Deleted profile: {profile_name}[/green]")
    else:
        console.print("[red]✗ Failed to delete profile[/red]")
        raise typer.Exit(1)


@app.command("export")
def export_profile(
    profile_name: str = typer.Argument(..., help="Profile to export"),
    output: str = typer.Argument(..., help="Output file path"),
):
    """Export a profile to a file."""
    if settings_mgr.export_profile(profile_name, output):
        console.print(f"[green]✓ Exported {profile_name} to {output}[/green]")
    else:
        console.print("[red]✗ Export failed[/red]")
        raise typer.Exit(1)


@app.command("import")
def import_profile(
    file_path: str = typer.Argument(..., help="Profile file to import"),
    name: str | None = typer.Option(None, "--name", "-n", help="New name for imported profile"),
):
    """Import a profile from a file."""
    imported_name = settings_mgr.import_profile(file_path, name)

    if imported_name:
        console.print(f"[green]✓ Imported profile as: {imported_name}[/green]")
    else:
        console.print("[red]✗ Import failed[/red]")
        raise typer.Exit(1)


@app.command("reset")
def reset_profiles(force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")):
    """Reset all profiles to defaults."""
    if not force:
        confirm = questionary.confirm(
            "This will reset ALL profiles to defaults. Any custom profiles will be lost. Continue?",
            default=False,
        ).ask()

        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            return

    if settings_mgr.reset_to_defaults():
        console.print("[green]✓ All profiles reset to defaults[/green]")
        console.print("[dim]  Active profile set to: repair_technician[/dim]")
    else:
        console.print("[red]✗ Reset failed[/red]")
        raise typer.Exit(1)


@app.command("menu")
def settings_menu():
    """Launch interactive settings menu."""
    console.print(
        Panel.fit(
            "[bold cyan]Kitty AI Settings Menu[/bold cyan]\n"
            "[dim]Customize your Kitty experience[/dim]",
            border_style="cyan",
        )
    )

    while True:
        choice = questionary.select(
            "Settings Menu",
            choices=[
                "List Profiles",
                "Show Current Profile",
                "Switch Profile",
                "Edit Profile",
                "Create New Profile",
                "Import/Export",
                "Exit",
            ],
        ).ask()

        if choice == "List Profiles":
            list_profiles()
        elif choice == "Show Current Profile":
            show_profile()
        elif choice == "Switch Profile":
            profiles = settings_mgr.list_profiles()
            choices = [p["name"] for p in profiles]
            selected = questionary.select("Select profile:", choices=choices).ask()
            use_profile(selected)
        elif choice == "Edit Profile":
            edit_profile()
        elif choice == "Create New Profile":
            name = questionary.text("New profile name:").ask()
            if name:
                create_profile(name)
        elif choice == "Import/Export":
            action = questionary.select(
                "Choose action:", choices=["Import Profile", "Export Profile", "Back"]
            ).ask()

            if action == "Import Profile":
                path = questionary.text("Path to profile file:").ask()
                if path:
                    import_profile(path)
            elif action == "Export Profile":
                profiles = settings_mgr.list_profiles()
                profile = questionary.select(
                    "Select profile to export:", choices=[p["name"] for p in profiles]
                ).ask()
                path = questionary.text("Export to path:").ask()
                if path:
                    export_profile(profile, path)
        elif choice == "Exit":
            break

    console.print("[dim]Goodbye![/dim]")


if __name__ == "__main__":
    app()
