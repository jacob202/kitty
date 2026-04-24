#!/usr/bin/env python3
"""Kitty CLI - Unified entry point for the Kitty AI project."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so imports work
_project_root = Path(__file__).parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import typer
from src.cli.settings_cli import app as settings_app

app = typer.Typer(
    name="kitty",
    help="Kitty AI - Your AI assistant and settings management",
    no_args_is_help=True,
)

# Register the settings commands as a subcommand group
app.add_typer(settings_app, name="settings", help="Manage Kitty AI settings profiles")

if __name__ == "__main__":
    app()
